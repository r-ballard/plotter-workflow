"""Bind layout geometry to a producer-owned artwork recipe."""

import copy
import hashlib
import xml.etree.ElementTree as ET

from .artwork_io import MAX_BYTES, atomic_directory, json_bytes
from .artwork_layout import ID_RE, affine, bounds, layout_dict

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def validate_layout(layout):
    kind = layout.settings.get("layout")
    if kind == "kaleidocycle-state":
        from .kaleidocycle_artwork import validate_kaleidocycle_layout

        validate_kaleidocycle_layout(layout)
    elif kind == "cassette-jcard":
        from .jcard_artwork import validate_jcard_layout

        validate_jcard_layout(layout)


def layout_generation_mode(layout):
    if layout.settings.get("layout") == "cassette-jcard" and layout.settings["mode"] == "independent":
        return "independent"
    return "shared"


def layout_job_geometry(layout, *, mode):
    geometry = {
        "domains": [
            {"id": panel.panel_id, "vertices": [list(point) for point in panel.crop_polygon]}
            for panel in layout.panels
        ],
    }
    if mode == "shared":
        geometry["composition_transforms"] = [
            {"domain_id": panel.panel_id, "matrix": list(panel.assembled_matrix)}
            for panel in layout.panels
        ]
    return geometry


def layout_pass_composition(layout, *, mode):
    intent = {"mode": mode}
    if mode == "shared":
        intent["window"] = dict(zip(("x", "y", "width", "height"), layout.window, strict=True))
    return intent


def validate_artwork_layers(layers):
    if not isinstance(layers, list):
        raise ValueError("logical_layers must be a list")  # noqa: TRY004
    seen = set()
    for layer in layers:
        layer_id = layer.get("id") if isinstance(layer, dict) else None
        if not isinstance(layer_id, str) or not ID_RE.fullmatch(layer_id) or layer_id in seen:
            raise ValueError("template requires unique safe logical layer IDs")
        seen.add(layer_id)


def validate_surface_bindings(layout, surfaces):
    if not isinstance(surfaces, list) or len(surfaces) != len(layout.panels):
        raise ValueError("surfaces differ from layout panels")
    for surface, panel in zip(surfaces, layout.panels, strict=True):
        if not isinstance(surface, dict) or (
            surface.get("id"), surface.get("domain_id")
        ) != (panel.panel_id, panel.panel_id):
            raise ValueError("surface binding differs from layout panel")


def build_artwork_job(layout, template):
    validate_layout(layout)
    if not isinstance(template, dict) or set(template) - {
        "schema_version", "seed", "domains", "surfaces", "groups", "relations",
        "composition_transforms", "passes",
    }:
        raise ValueError("unknown artwork template fields")
    if (
        type(template.get("schema_version")) is not int
        or template["schema_version"] != 1
        or type(template.get("seed")) is not int
    ):
        raise ValueError("artwork template requires schema_version 1 and integer seed")
    job = copy.deepcopy(template)
    mode = layout_generation_mode(layout)
    geometry = layout_job_geometry(layout, mode=mode)
    panel_ids = [panel.panel_id for panel in layout.panels]
    # Producer defaults bind each source domain to its identically named surface.
    if job.get("surfaces") == []:
        del job["surfaces"]
    if "surfaces" in job:
        validate_surface_bindings(layout, job["surfaces"])
    for field, expected in (
        ("domains", geometry["domains"]),
        ("composition_transforms", geometry.get("composition_transforms", [])),
    ):
        supplied = job.pop(field, [])
        if supplied != [] and json_bytes(supplied) != json_bytes(expected):
            raise ValueError(f"template {field} differs from layout geometry")
    job.update(geometry)
    passes = job.get("passes")
    if not isinstance(passes, list) or not passes:
        raise ValueError("template requires artwork passes")
    for design_pass in passes:
        if not isinstance(design_pass, dict):
            raise ValueError("artwork pass must be an object")  # noqa: TRY004
        validate_artwork_layers(design_pass.get("logical_layers", []))
        targets = design_pass.get("target_domain_ids", [])
        if not isinstance(targets, list) or any(not isinstance(t, str) or not t for t in targets):
            raise ValueError("invalid target_domain_ids")
        if not targets:
            targets = panel_ids.copy()
            design_pass["target_domain_ids"] = targets
        derived = set(targets).difference(panel_ids)
        if derived and not design_pass.get("depends_on"):
            raise ValueError("targets outside the layout require a dependency on derived domains")
        if derived and mode == "shared" and derived != set(targets):
            raise ValueError("shared generation cannot mix placed panels and derived domains")
        intent = layout_pass_composition(layout, mode="independent" if derived else mode)
        if "composition" in design_pass:
            declared = design_pass["composition"]
            if declared != {"mode": intent["mode"]} and json_bytes(declared) != json_bytes(intent):
                raise ValueError("pass composition differs from layout generation intent")
        design_pass["composition"] = intent
    if len(json_bytes(job)) > MAX_BYTES:
        raise ValueError("artwork job exceeds size limit")
    return job


def layout_preview(layout):
    x, y, w, h = layout.window
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": "1000",
            "height": "700",
            "viewBox": f"{x - w * 0.05} {y - h * 0.08} {w * 1.1} {h * 1.16}",
        },
    )
    for panel in layout.panels:
        for polygon, color, dash in (
            (panel.canvas_polygon, "#999", "4 4"),
            (panel.crop_polygon, "#1765a3", "none"),
        ):
            points = [affine(panel.assembled_matrix, p) for p in polygon]
            ET.SubElement(
                root,
                f"{{{SVG_NS}}}polygon",
                {
                    "points": " ".join(f"{a},{b}" for a, b in points),
                    "fill": "none",
                    "stroke": color,
                    "stroke-width": str(max(w, h) / 1000),
                    "stroke-dasharray": dash,
                },
            )
        points = [affine(panel.assembled_matrix, p) for p in panel.canvas_polygon]
        for i, (a, b) in enumerate(points):
            ET.SubElement(
                root,
                f"{{{SVG_NS}}}text",
                {
                    "x": str(a),
                    "y": str(b),
                    "font-size": str(max(w, h) / 70),
                    "fill": "#8a2846",
                },
            ).text = f"{panel.panel_id}:{i}"
        a, b = affine(
            panel.assembled_matrix,
            (
                sum(p[0] for p in panel.crop_polygon) / len(panel.crop_polygon),
                sum(p[1] for p in panel.crop_polygon) / len(panel.crop_polygon),
            ),
        )
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}text",
            {
                "x": str(a),
                "y": str(b),
                "font-size": str(max(w, h) / 60),
                "text-anchor": "middle",
            },
        ).text = panel.panel_id + " up:corner0-1"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_layout_export(
    layout, template, output_dir, *, overwrite=False, protected_paths=()
):
    job = build_artwork_job(layout, template)
    data = json_bytes(job)
    resolved_layout = layout_dict(layout)
    if layout.settings.get("layout") == "kaleidocycle-state":
        # Old profiles remain readable, but every new handoff is explicit.
        resolved_layout["settings"].setdefault("tetrahedron_count", 8)
    report = {
        "schema_version": 2,
        "artifact_type": "assembled-artwork-layout",
        "layout": resolved_layout,
        "job_sha256": hashlib.sha256(data).hexdigest(),
        "template_sha256": hashlib.sha256(json_bytes(template)).hexdigest(),
        "producer_request": job,
        "panels": [
            {
                "panel_id": p.panel_id,
                "source_path": f"surfaces/{p.panel_id}.svg",
                "rebase_offset": list(bounds(p.crop_polygon)[:2]),
                "binding": dict(p.binding),
            }
            for p in layout.panels
        ],
    }

    def write(stage):
        files = {
            "artwork-job.json": data,
            "layout-handoff.json": json_bytes(report),
            "layout-preview.svg": layout_preview(layout),
        }
        if sum(map(len, files.values())) > MAX_BYTES:
            raise ValueError("layout export exceeds size limit")
        for name, content in files.items():
            (stage / name).write_bytes(content)

    return atomic_directory(
        output_dir, write, overwrite=overwrite, protected=protected_paths
    )
