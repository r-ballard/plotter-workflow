"""Return prepared state artwork to the physical net without reapplying views."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from logical_layer_contract import NEUTRAL_CONTRACT
from scripts import booklet_impose as booklet
from scripts.cootie_impose import clip_line_collection

from .artwork_export import SVG_NS
from .artwork_io import atomic_directory, json_bytes, read_json
from .artwork_layout import MM_TO_PX, bounds
from .artwork_return import _load_handoff
from .geometry import map_normalized_polygon
from .kaleidocycle_artwork import validate_kaleidocycle_layout
from .model import SheetSpec
from .native_artwork import _validate_viewport
from .objects.kaleidocycle import Kaleidocycle
from .source import inspect_svg_source


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sheet_root(sheet):
    return ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": f"{sheet.width_mm:.17g}mm",
            "height": f"{sheet.height_mm:.17g}mm",
            "viewBox": f"0 0 {sheet.width_mm * MM_TO_PX:.17g} {sheet.height_mm * MM_TO_PX:.17g}",
            booklet.LAYOUT_MARKER_ATTRIBUTE: booklet.LAYOUT_MARKER_VALUE,
            "data-plotter-workflow-page-size": sheet.name,
            "data-plotter-workflow-orientation": sheet.orientation,
            "data-imposition-layout": "kaleidocycle",
        },
    )


def resolve_state_paths(states, base_dir):
    result = {}
    for state, relative in states.items():
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
        ):
            raise ValueError("state asset directories must be relative to config")
        bundle = (Path(base_dir) / relative).resolve()
        if not bundle.is_relative_to(Path(base_dir).resolve()):
            raise ValueError("state asset directory escapes config directory")
        result[state] = bundle
    return result


def render_kaleidocycle(states, placement):
    """Validate and render one net in a supplied physical frame, in memory."""
    sheet = placement.sheet
    obj = Kaleidocycle()
    root = _sheet_root(sheet)
    root.set("data-viz-layer-contract", NEUTRAL_CONTRACT)
    groups, catalog, records, protected = {}, None, [], []
    slots = {s.slot_id: s for s in obj.slots}
    for state, path in states.items():
        bundle = Path(path).resolve()
        protected.append(bundle)
        _, layout = _load_handoff(bundle / "layout-handoff.json")
        validate_kaleidocycle_layout(layout)
        if (
            layout.settings["state"] != state
            or abs(layout.settings["width_mm"] - placement.width_mm) > 1e-7
        ):
            raise ValueError("state or physical width differs from prepared artwork")
        entries = []
        for panel in layout.panels:
            source = (bundle / "surfaces" / f"{panel.panel_id}.svg").resolve()
            if not source.is_relative_to(bundle):
                raise ValueError("source escapes state bundle")
            entries.append(SimpleNamespace(source=source))
        mode, manifest = booklet._inspect_sources(entries)
        if mode != "neutral":
            raise ValueError("kaleidocycle requires prepared neutral artwork")
        provenance = manifest.raw.get("adapter_provenance", {})
        if (
            manifest.raw.get("schema") != "plotter-workflow/assembled-artwork-assets/v1"
            or not isinstance(provenance, dict)
            or provenance.get("handoff_sha256")
            != _digest(bundle / "layout-handoff.json")
            or provenance.get("producer_design_sha256")
            != _digest(bundle / "producer-design.json")
            or provenance.get("layout_profile") != layout.profile_id
        ):
            raise ValueError("prepared bundle provenance differs from state handoff")
        if {s.path for s in manifest.surfaces} != {
            f"surfaces/{p.panel_id}.svg" for p in layout.panels
        }:
            raise ValueError("state bundle requires exactly eight panel assignments")
        current = manifest.raw["logical_layers"]
        if catalog is None:
            catalog = current
            for layer in manifest.layers:
                groups[layer.id] = ET.SubElement(
                    root,
                    f"{{{SVG_NS}}}g",
                    {
                        "id": f"logical-layer-{layer.ordinal}",
                        "data-viz-layer-id": layer.id,
                        "data-viz-layer-ordinal": str(layer.ordinal),
                        "data-viz-layer-label": layer.label,
                        "fill": "none",
                        "stroke": "black",
                    },
                )
        elif catalog != current:
            raise ValueError(
                "state bundles must share exactly the same logical layer catalog"
            )
        for panel, entry in zip(layout.panels, entries):
            source = entry.source
            intrinsic = inspect_svg_source(source)
            if (
                intrinsic is None
                or len(intrinsic.polygon) != 4
                or any(
                    abs(a - b) > 1e-7
                    for p, q in zip(intrinsic.polygon, panel.canvas_polygon)
                    for a, b in zip(p, q)
                )
            ):
                raise ValueError("source canvas differs from prepared panel")
            slot = slots[panel.panel_id]
            _validate_viewport(source, bounds(panel.canvas_polygon))
            polygon_mm = map_normalized_polygon(slot.polygon, placement)
            polygon_px = tuple((x * MM_TO_PX, y * MM_TO_PX) for x, y in polygon_mm)
            tx, ty = bounds(polygon_px)[:2]
            for layer_id, geometry, width, height in booklet._neutral_fragments(
                source, len(records) + 1, 0.05 * MM_TO_PX
            ):
                x0, y0, x1, y1 = bounds(panel.canvas_polygon)
                if abs(width - (x1 - x0)) > 1e-7 or abs(height - (y1 - y0)) > 1e-7:
                    raise ValueError("source viewport differs from prepared panel")
                local_width = max(x for x, y in polygon_px) - min(
                    x for x, y in polygon_px
                )
                geometry.scale(local_width / width)
                geometry.translate(tx, ty)
                geometry.lines = clip_line_collection(geometry.lines, polygon_px)
                clip_id = geometry.prefix + "-net-triangle"
                geometry._wrap({"clip-path": f"url(#{clip_id})"})
                clip = ET.SubElement(
                    ET.SubElement(geometry.svg, f"{{{SVG_NS}}}defs"),
                    f"{{{SVG_NS}}}clipPath",
                    {"id": clip_id, "clipPathUnits": "userSpaceOnUse"},
                )
                ET.SubElement(
                    clip,
                    f"{{{SVG_NS}}}polygon",
                    {"points": " ".join(f"{x:.17g},{y:.17g}" for x, y in polygon_px)},
                )
                # Retain explicit empty layers and all original path metadata.
                wrapper = ET.SubElement(
                    groups[layer_id],
                    f"{{{SVG_NS}}}g",
                    {"data-imposed-slot": panel.panel_id},
                )
                wrapper.append(geometry.svg)
            records.append(
                {
                    "slot": panel.panel_id,
                    "state": state,
                    "source_sha256": _digest(source),
                    "polygon_mm": polygon_mm,
                    "source_manifest_sha256": _digest(bundle / "design.json"),
                    "handoff_sha256": _digest(bundle / "layout-handoff.json"),
                }
            )
    return root, catalog, records, protected


def write_kaleidocycle(config_path, output_dir, *, overwrite=False):
    config_path = Path(config_path).resolve()
    config = read_json(config_path)
    if (
        not isinstance(config, dict)
        or set(config)
        - {
            "schema_version",
            "width_mm",
            "sheet_size",
            "margin_mm",
            "states",
            "position",
        }
        or type(config.get("schema_version")) is not int
        or config["schema_version"] != 1
        or not isinstance(config.get("states"), dict)
        or set(config["states"]) != set("ABCD")
    ):
        raise ValueError("expected version 1 config with exactly states A-D")
    name = config.get("sheet_size", "letter")
    if name not in booklet.SHEET_SIZES_MM:
        raise ValueError("unsupported sheet size")
    sheet = SheetSpec(name, *booklet.SHEET_SIZES_MM[name], "landscape")
    obj = Kaleidocycle()
    placement = obj.resolve_placement(
        sheet,
        {k: config[k] for k in ("width_mm", "margin_mm", "position") if k in config},
    )
    root, catalog, records, protected = render_kaleidocycle(
        resolve_state_paths(config["states"], config_path.parent), placement
    )
    protected.append(config_path)
    guides = _sheet_root(sheet)
    guides.set("data-imposition-artifact", "construction-guides")
    for guide in obj.guides(placement):
        # Glue polygons are diagnostic outlines; cut/fold lines remain separate.
        group = ET.SubElement(guides, f"{{{SVG_NS}}}g", {"data-guide-kind": guide.kind})
        ET.SubElement(
            group,
            f"{{{SVG_NS}}}path",
            {
                "d": "M "
                + " L ".join(
                    f"{x * MM_TO_PX:.17g},{y * MM_TO_PX:.17g}" for x, y in guide.points
                )
                + (" Z" if guide.closed else ""),
                "fill": "none",
                "stroke": "black",
            },
        )
    audit = {
        "schema_version": 1,
        "object_id": obj.object_id,
        "validation_status": "provisional",
        "placement_mm": [
            placement.x_mm,
            placement.y_mm,
            placement.width_mm,
            placement.height_mm,
        ],
        "panels": records,
        "requires_preserved_layout": True,
    }

    def write(stage):
        (stage / "design.svg").write_bytes(
            ET.tostring(root, encoding="utf-8", xml_declaration=True)
        )
        (stage / "guides.svg").write_bytes(
            ET.tostring(guides, encoding="utf-8", xml_declaration=True)
        )
        preview = _sheet_root(sheet)
        preview.set("data-imposition-artifact", "diagnostic-not-for-plotting")
        colors = dict(zip("ABCD", ("#bdbdbd", "#71c8df", "#149bc4", "#146590")))
        for slot in obj.slots:
            points = map_normalized_polygon(slot.polygon, placement)
            ET.SubElement(
                preview,
                f"{{{SVG_NS}}}polygon",
                {
                    "points": " ".join(
                        f"{x * MM_TO_PX:.17g},{y * MM_TO_PX:.17g}" for x, y in points
                    ),
                    "fill": colors[slot.family],
                    "stroke": "black",
                    "stroke-width": ".4",
                },
            )
            x = sum(p[0] for p in points) / 3 * MM_TO_PX
            y = sum(p[1] for p in points) / 3 * MM_TO_PX
            ET.SubElement(
                preview,
                f"{{{SVG_NS}}}text",
                {
                    "x": str(x),
                    "y": str(y),
                    "text-anchor": "middle",
                    "font-size": "5",
                    "fill": "black",
                    "data-slot-label": slot.slot_id,
                },
            ).text = slot.slot_id + " ↑R"
        for guide in guides:
            preview.append(ET.fromstring(ET.tostring(guide)))
        (stage / "net-preview.svg").write_bytes(
            ET.tostring(preview, encoding="utf-8", xml_declaration=True)
        )
        (stage / "design.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "logical_layer_contract": NEUTRAL_CONTRACT,
                    "logical_layers": catalog,
                    "requires_preserved_layout": True,
                    "surfaces": [
                        {
                            "surface_id": "net",
                            "domain_id": "net",
                            "path": "design.svg",
                            "sha256": _digest(stage / "design.svg"),
                            "logical_layer_ids": [v["id"] for v in catalog],
                        }
                    ],
                    "source_config_sha256": _digest(config_path),
                    "imposition": audit,
                }
            )
        )
        (stage / "design.imposition.json").write_bytes(
            json_bytes(
                {
                    **audit,
                    "source_mode": "neutral",
                    "logical_layer_contract": NEUTRAL_CONTRACT,
                    "source_manifest_path": "design.json",
                    "source_manifest_sha256": _digest(stage / "design.json"),
                    "logical_layers": catalog,
                    "logical_layer_ids": [v["id"] for v in catalog],
                    "sheet": {
                        "name": sheet.name,
                        "orientation": sheet.orientation,
                        "width_mm": sheet.width_mm,
                        "height_mm": sheet.height_mm,
                    },
                }
            )
        )

    return atomic_directory(output_dir, write, overwrite=overwrite, protected=protected)
