"""Algorithm-neutral resolved layout export with a small Truchet job adapter."""

import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from .artwork_io import atomic_directory, json_bytes, MAX_BYTES
from .artwork_layout import layout_dict, bounds, affine, ID_RE

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def build_artwork_job(layout, template):
    if not isinstance(template, dict) or set(template) - {
        "schema_version",
        "seed",
        "domains",
        "surfaces",
        "groups",
        "relations",
        "composition_transforms",
        "passes",
    }:
        raise ValueError("unknown artwork template fields")
    if (
        type(template.get("schema_version")) is not int
        or template["schema_version"] != 1
        or type(template.get("seed")) is not int
    ):
        raise ValueError("artwork template requires schema_version1 and integer seed")
    if template.get("groups") or template.get("relations"):
        raise ValueError("template cannot retain stale groups/relations")
    passes = template.get("passes")
    if not isinstance(passes, list) or len(passes) != 1:
        raise ValueError("template requires exactly one pass")
    p = copy.deepcopy(passes[0])
    if not isinstance(p, dict) or set(p) - {
        "id",
        "algorithm",
        "target_domain_ids",
        "parameters",
        "logical_layers",
        "depends_on",
        "group_context_ids",
        "relation_context_ids",
    }:
        raise ValueError("invalid template pass fields")
    if p.get("algorithm") not in (
        "truchet",
        "truchet-multiscale",
    ) or not ID_RE.fullmatch(p.get("id", "")):
        raise ValueError("template requires Truchet pass with safe ID")
    if any(
        p.get(k) for k in ("depends_on", "group_context_ids", "relation_context_ids")
    ):
        raise ValueError("template cannot retain pass dependencies")
    parameters = p.get("parameters")
    if (
        not isinstance(parameters, dict)
        or not isinstance(parameters.get("region_fills"), dict)
        or not parameters.get("curve_layer_ids")
    ):
        raise ValueError(
            "template requires structured region_fills and curve_layer_ids"
        )
    if (
        parameters.get("coordinate_frame", "composition") != "composition"
        or parameters.get("composition_mode", "continuous") != "continuous"
    ):
        raise ValueError("template requires continuous composition")
    layers = p.get("logical_layers")
    if (
        not isinstance(layers, list)
        or not layers
        or any(
            not isinstance(v, dict) or not ID_RE.fullmatch(v.get("id", ""))
            for v in layers
        )
        or len({v["id"] for v in layers}) != len(layers)
    ):
        raise ValueError("template requires unique safe logical layer IDs")
    x, y, w, h = layout.window
    parameters.update(
        coordinate_frame="composition",
        composition_mode="continuous",
        composition_window=dict(x=x, y=y, width=w, height=h),
    )
    p["target_domain_ids"] = [v.panel_id for v in layout.panels]
    job = dict(
        schema_version=1,
        seed=template["seed"],
        domains=[
            dict(id=v.panel_id, vertices=[list(q) for q in v.crop_polygon])
            for v in layout.panels
        ],
        composition_transforms=[
            dict(domain_id=v.panel_id, matrix=list(v.assembled_matrix))
            for v in layout.panels
        ],
        passes=[p],
    )
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
                (panel.canvas_polygon[0][0] + panel.canvas_polygon[2][0]) / 2,
                (panel.canvas_polygon[0][1] + panel.canvas_polygon[2][1]) / 2,
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
    report = dict(
        schema_version=1,
        artifact_type="assembled-artwork-layout",
        layout=layout_dict(layout),
        job_sha256=hashlib.sha256(data).hexdigest(),
        template_sha256=hashlib.sha256(json_bytes(template)).hexdigest(),
        producer_request=job,
        panels=[
            dict(
                panel_id=p.panel_id,
                source_path=f"surfaces/{p.panel_id}.svg",
                rebase_offset=list(bounds(p.crop_polygon)[:2]),
                binding=dict(p.binding),
            )
            for p in layout.panels
        ],
    )

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
