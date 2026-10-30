"""Validated immutable native J-card fragments, independent of sheet placement."""

import copy
import hashlib
import io
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from scripts import booklet_impose as booklet

from .artwork_io import json_bytes, read_json
from .artwork_layout import MM_TO_PX, _freeze, bounds, layout_dict
from .artwork_return import _load_handoff, _subset
from .jcard_artwork import build_jcard_artwork_job, resolve_jcard_layout
from .jcard_profiles import get_jcard_profile
from .source import inspect_svg_source


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class NativeFaceRequest:
    profile: str
    face: str
    assets: Path
    template: Path
    mode: str
    blank_panels: tuple = ()

    def __post_init__(self):
        p = get_jcard_profile(self.profile)
        if self.face not in ("front", "back") or self.mode not in ("independent", "continuous"):
            raise ValueError("invalid native face/mode")
        if (
            not isinstance(self.blank_panels, (tuple, list))
            or any(not isinstance(v, str) for v in self.blank_panels)
            or len(set(self.blank_panels)) != len(self.blank_panels)
            or any(
                v not in {f"{self.face}-panel-{i}" for i in range(1, p.panel_count + 1)}
                for v in self.blank_panels
            )
        ):
            raise ValueError("invalid native blank panels")
        object.__setattr__(self, "blank_panels", tuple(self.blank_panels))
        object.__setattr__(self, "assets", Path(self.assets).resolve())
        object.__setattr__(self, "template", Path(self.template).resolve())


@dataclass(frozen=True)
class NativeFragment:
    layer_id: str
    panel_id: str
    svg_bytes: bytes
    vertices: int


@dataclass(frozen=True)
class PreparedNativeFace:
    profile: str
    face: str
    width_mm: float
    height_mm: float
    catalog: tuple
    fragments: tuple
    panel_audit: tuple
    provenance: object


def _validate_viewport(source, expected):
    root = ET.parse(source).getroot()
    try:
        width, height = float(root.get("width", "")), float(root.get("height", ""))
        view = tuple(float(v) for v in root.get("viewBox", "").split())
    except ValueError as exc:
        raise ValueError("Source viewport requires canonical native pixel dimensions") from exc
    x0, y0, x1, y1 = expected
    want = (x0, y0, x1 - x0, y1 - y0)
    if (
        len(view) != 4
        or not all(math.isfinite(v) for v in (width, height, *view))
        or abs(width - want[2]) / MM_TO_PX > 1e-6
        or abs(height - want[3]) / MM_TO_PX > 1e-6
        or any(abs(a - b) / MM_TO_PX > 1e-6 for a, b in zip(view, want))
    ):
        raise ValueError("Source viewport differs from exact panel size")


def _retained_vertices(geometry, width, height):
    """Count copied paths, including off-viewport and definition geometry.

    Presence lines have already been cropped. The XML retains the full paths,
    so counting those lines alone would undercharge repeated output copies.
    This separate count does not change the artwork or its clipping.
    """
    namespace = f"{{{booklet.SVG_NS}}}"
    root = ET.Element(namespace + "svg", width=str(width), height=str(height))
    fragment = copy.deepcopy(geometry.svg)
    for node in fragment.iter():
        if node.tag.rsplit("}", 1)[-1] in ("defs", "clipPath"):
            node.tag = namespace + "g"
        for key in ("clip-path", "display", "visibility", "opacity", "style"):
            node.attrib.pop(key, None)
    root.append(fragment)
    lines, _, _ = booklet._require_vpype().read_svg(
        io.StringIO(ET.tostring(root, encoding="unicode")),
        quantization=0.05 * MM_TO_PX,
        crop=False,
    )
    return max(sum(len(line) for line in lines), sum(len(line) for line in geometry.lines))


def prepare_native_face(request):
    face = request.face
    recipe = SimpleNamespace(
        template=request.template, mode=request.mode, blank_panels=request.blank_panels
    )
    config = SimpleNamespace(
        profile=request.profile, selected_faces=(face,), **{f"{face}_artwork": recipe}
    )
    bundle = request.assets
    bundle = Path(bundle).resolve()
    report, layout = _load_handoff(bundle / "layout-handoff.json")
    expected = resolve_jcard_layout(config, face)
    if json_bytes(layout_dict(layout)) != json_bytes(layout_dict(expected)):
        raise ValueError("Prepared face/profile differs from selected native layout")
    recipe = getattr(config, f"{face}_artwork")
    if (
        build_jcard_artwork_job(expected, read_json(recipe.template), mode=recipe.mode)
        != report["producer_request"]
    ):
        raise ValueError("Prepared artwork is stale relative to selected recipe")
    entries = [SimpleNamespace(source=bundle / f"surfaces/{p.panel_id}.svg") for p in layout.panels]
    mode, manifest = booklet._inspect_sources(entries)
    if mode != "neutral" or manifest is None:
        raise ValueError("J-card requires a prepared neutral bundle")
    provenance = manifest.raw.get("adapter_provenance", {})
    if (
        manifest.raw.get("schema") != "plotter-workflow/assembled-artwork-assets/v1"
        or provenance.get("handoff_sha256") != digest(bundle / "layout-handoff.json")
        or provenance.get("producer_design_sha256") != digest(bundle / "producer-design.json")
    ):
        raise ValueError("Prepared bundle provenance/hash mismatch")
    producer = read_json(bundle / "producer-design.json")
    if (
        not _subset(report["producer_request"], producer)
        or producer.get("logical_layers") != manifest.raw["logical_layers"]
    ):
        raise ValueError("Producer recipe/catalog differs from prepared bundle")
    if {r["domain_id"] for r in manifest.raw["surfaces"]} != {
        p.panel_id for p in layout.panels
    } or len(manifest.raw["surfaces"]) != len(layout.panels):
        raise ValueError("Prepared bundle requires exactly the selected profile's panels")
    records = []
    fragments = []
    for number, (panel, entry) in enumerate(zip(layout.panels, entries), 1):
        source = entry.source
        intrinsic = inspect_svg_source(source)
        expected_bounds = bounds(panel.canvas_polygon)
        if (
            intrinsic is None
            or len(intrinsic.polygon) != 4
            or any(
                abs(v - q) / MM_TO_PX > 1e-6
                for point, expected_point in zip(intrinsic.polygon, panel.canvas_polygon)
                for v, q in zip(point, expected_point)
            )
        ):
            raise ValueError("Source canvas dimensions differ from exact panel size")
        x0, y0, x1, y1 = expected_bounds
        _validate_viewport(source, expected_bounds)
        for layer_id, geometry, width, height in booklet._neutral_fragments(
            source, number, 0.05 * MM_TO_PX
        ):
            if (
                abs(width - (x1 - x0)) / MM_TO_PX > 1e-6
                or abs(height - (y1 - y0)) / MM_TO_PX > 1e-6
            ):
                raise ValueError("Source viewport differs from exact panel size")
            geometry.crop(x0, y0, x1, y1)
            if panel.panel_id in recipe.blank_panels:
                continue
            geometry.translate(panel.assembled_matrix[4], panel.assembled_matrix[5])
            if not booklet._line_collection_empty(geometry.lines):
                fragments.append(
                    NativeFragment(
                        layer_id,
                        panel.panel_id,
                        ET.tostring(geometry.svg, encoding="utf-8"),
                        _retained_vertices(geometry, width, height),
                    )
                )
        records.append(
            {
                "slot": panel.panel_id,
                "physical_panel_id": panel.binding["physical_panel_id"],
                "source": f"surfaces/{panel.panel_id}.svg",
                "source_sha256": digest(source),
                "blank": panel.panel_id in recipe.blank_panels,
                "native_matrix_px": list(panel.assembled_matrix),
            }
        )
    profile = get_jcard_profile(request.profile)
    w, h = profile.trim_size_mm
    return PreparedNativeFace(
        request.profile,
        face,
        w,
        h,
        tuple(_freeze(v) for v in manifest.raw["logical_layers"]),
        tuple(fragments),
        tuple(_freeze(v) for v in records),
        _freeze(
            dict(
                source_manifest_sha256=digest(bundle / "design.json"),
                handoff_sha256=digest(bundle / "layout-handoff.json"),
                producer_design_sha256=digest(bundle / "producer-design.json"),
            )
        ),
    )
