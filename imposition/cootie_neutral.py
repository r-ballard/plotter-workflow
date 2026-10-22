"""Neutral logical-layer Cootie placement using the existing SVG/vector pair."""

import math
import xml.etree.ElementTree as ET

from logical_layer_contract import NEUTRAL_CONTRACT
from scripts import booklet_impose as booklet


def has_neutral_sources(entries):
    for entry in entries:
        try:
            root = ET.parse(entry.source).getroot()
        except ET.ParseError:
            return False  # legacy validator owns malformed input diagnostics
        if root.get("data-viz-layer-contract") is not None or any(
            g.get("data-viz-layer-id") is not None for g in root
        ):
            return True
    return False


def impose_neutral(entries, *, sheet_size, placement, quantization_mm):
    from scripts import cootie_impose as cootie

    if not math.isfinite(quantization_mm) or quantization_mm <= 0:
        raise ValueError("quantization must be positive finite")
    mode, manifest = booklet._inspect_sources(entries)
    if mode != "neutral" or manifest is None:
        raise ValueError("Cootie neutral imposition requires one neutral bundle")
    root = cootie._new_physical_svg_root(sheet_size, placement)
    root.set("data-viz-layer-contract", NEUTRAL_CONTRACT)
    groups = {}
    for layer in manifest.layers:
        groups[layer.id] = ET.SubElement(
            root,
            f"{{{booklet.SVG_NS}}}g",
            {
                "id": f"logical-layer-{layer.ordinal}",
                "data-viz-layer-id": layer.id,
                "data-viz-layer-ordinal": str(layer.ordinal),
                "data-viz-layer-label": layer.label,
                "fill": "none",
                "stroke": "#000000",
            },
        )
    records = []
    count = 0
    for number, entry in enumerate(entries, 1):
        polygon = cootie.panel_polygon_px(entry.slot, placement)
        drawable = cootie.inset_convex_polygon(
            polygon, cootie._mm_to_px(entry.margin_mm)
        )
        for layer_id, g, width, height in booklet._neutral_fragments(
            entry.source, number, cootie._mm_to_px(quantization_mm)
        ):
            g.translate(-width / 2, -height / 2)
            if entry.rotation_degrees:
                g.lines.rotate(math.radians(entry.rotation_degrees))
                g._wrap({"transform": f"rotate({entry.rotation_degrees:.17g})"})
            scale, x, y = cootie.fit_transform(
                drawable,
                source_width=width,
                source_height=height,
                rotation_degrees=entry.rotation_degrees,
                fit=entry.fit,
            )
            g.scale(scale)
            g.translate(x, y)
            g.lines = cootie.clip_line_collection(g.lines, drawable)
            clip_id = f"{g.prefix}-polygon-{g.crop_count}"
            g.crop_count += 1
            g._wrap({"clip-path": f"url(#{clip_id})"})
            clip = ET.SubElement(
                ET.SubElement(g.svg, f"{{{booklet.SVG_NS}}}defs"),
                f"{{{booklet.SVG_NS}}}clipPath",
                {"id": clip_id, "clipPathUnits": "userSpaceOnUse"},
            )
            ET.SubElement(
                clip,
                f"{{{booklet.SVG_NS}}}polygon",
                {"points": " ".join(f"{a:.17g},{b:.17g}" for a, b in drawable)},
            )
            if not booklet._line_collection_empty(g.lines):
                wrapper = ET.SubElement(
                    groups[layer_id],
                    f"{{{booklet.SVG_NS}}}g",
                    {"data-imposed-slot": entry.slot, "data-source": entry.source.name},
                )
                wrapper.append(g.svg)
                count += len(g.lines)
        records.append(
            cootie.RenderedPanel(
                slot=entry.slot,
                kind=entry.kind,
                index=entry.index,
                source=entry.source.name,
                fit=entry.fit,
                margin_mm=entry.margin_mm,
                rotation_degrees=entry.rotation_degrees,
                polygon_normalized=cootie.COOTIE_PANEL_POLYGONS[entry.slot],
                polygon_mm=tuple(
                    (cootie._px_to_mm(x), cootie._px_to_mm(y)) for x, y in polygon
                ),
                orientation_policy=entry.orientation_policy,
                rotation_override_degrees=entry.rotation_override_degrees,
                source_intrinsic_canvas=entry.source_intrinsic_canvas,
                target_up_vector=entry.target_up_vector,
            )
        )
    if count == 0:
        raise ValueError("Cootie-catcher sources produced no plottable vector paths")
    return root, records, "neutral"
