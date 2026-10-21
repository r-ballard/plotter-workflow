"""Restore producer-rebased crops into honest full-canvas derivative bundles."""

import copy
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from logical_layer_contract import (
    load_logical_layer_manifest,
    validate_surface_against_manifest,
)
from .source import inspect_svg_source
from .artwork_layout import parse_layout, bounds, rect, layout_dict
from .artwork_io import (
    read_json,
    json_bytes,
    atomic_directory,
    MAX_BYTES,
    check_destination,
)
from .artwork_export import build_artwork_job, SVG_NS


def _subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and _subset(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_subset(x, y) for x, y in zip(expected, actual))
        )
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    return expected == actual


def _load_handoff(path):
    report = read_json(path)
    required = {
        "schema_version",
        "artifact_type",
        "layout",
        "job_sha256",
        "template_sha256",
        "producer_request",
        "panels",
    }
    if (
        not isinstance(report, dict)
        or set(report) != required
        or type(report["schema_version"]) is not int
        or report["schema_version"] != 1
        or report["artifact_type"] != "assembled-artwork-layout"
    ):
        raise ValueError("unsupported layout handoff schema")
    layout = parse_layout(report["layout"])
    request = report["producer_request"]
    if (
        build_artwork_job(layout, request) != request
        or hashlib.sha256(json_bytes(request)).hexdigest() != report["job_sha256"]
    ):
        raise ValueError("handoff request/hash differs from resolved layout")
    expected = [
        dict(
            panel_id=p.panel_id,
            source_path=f"surfaces/{p.panel_id}.svg",
            rebase_offset=list(bounds(p.crop_polygon)[:2]),
            binding=dict(p.binding),
        )
        for p in layout.panels
    ]
    if json_bytes(expected) != json_bytes(report["panels"]):
        raise ValueError("handoff panel mapping/rebase offset differs from layout")
    return report, layout


def _restore_svg(data, panel, source):
    if (
        len(data) > MAX_BYTES
        or b"<!DOCTYPE" in data.upper()
        or b"<!ENTITY" in data.upper()
    ):
        raise ValueError("unsupported or oversized SVG input")
    from scripts.booklet_impose import _validate_neutral_renderables

    root = ET.fromstring(data)
    _validate_neutral_renderables(root, source)
    canvas = inspect_svg_source(source)
    x0, y0, x1, y1 = bounds(panel.crop_polygon)
    cw = x1 - x0
    ch = y1 - y0
    expected = rect(0.0, 0.0, cw, ch)
    if (
        canvas is None
        or len(canvas.polygon) != 4
        or any(
            abs(a - b) > 1e-7
            for p, q in zip(canvas.polygon, expected)
            for a, b in zip(p, q)
        )
    ):
        raise ValueError("producer intrinsic canvas does not match rebased layout crop")
    view = root.get("viewBox", "").split()
    if len(view) != 4 or any(
        abs(float(a) - b) > 1e-7 for a, b in zip(view, (0, 0, cw, ch))
    ):
        raise ValueError("producer viewport differs from expected crop")
    cx0, cy0, cx1, cy1 = bounds(panel.canvas_polygon)
    width = cx1 - cx0
    height = cy1 - cy0
    root.set("viewBox", f"{cx0:.17g} {cy0:.17g} {width:.17g} {height:.17g}")
    root.set("width", f"{width:.17g}")
    root.set("height", f"{height:.17g}")
    root.set("data-viz-canvas-shape", "rectangle")
    root.set(
        "data-viz-canvas-polygon",
        " ".join(f"{x:.17g},{y:.17g}" for x, y in panel.canvas_polygon),
    )
    ids = {e.get("id") for e in root.iter()}
    clip_id = "layout-full-canvas"
    while clip_id in ids:
        clip_id += "-1"
    root.set("data-viz-canvas-clip-id", clip_id)
    defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
    clip = ET.SubElement(
        defs,
        f"{{{SVG_NS}}}clipPath",
        {"id": clip_id, "clipPathUnits": "userSpaceOnUse"},
    )
    ET.SubElement(
        clip,
        f"{{{SVG_NS}}}rect",
        {"x": str(cx0), "y": str(cy0), "width": str(width), "height": str(height)},
    )
    for group in list(root):
        if group.get("data-viz-layer-id") is None:
            continue
        original_attrs = {
            k: group.attrib.pop(k)
            for k in ("transform", "clip-path")
            if k in group.attrib
        }
        content = list(group)
        for child in content:
            group.remove(child)
        group.set("clip-path", f"url(#{clip_id})")
        translation = ET.SubElement(
            group, f"{{{SVG_NS}}}g", {"transform": f"translate({x0:.17g},{y0:.17g})"}
        )
        original = ET.SubElement(translation, f"{{{SVG_NS}}}g", original_attrs)
        for child in content:
            original.append(child)
    metadata = ET.SubElement(
        root, f"{{{SVG_NS}}}metadata", {"id": "layout-return-provenance"}
    )
    metadata.text = json_bytes(
        dict(
            adapter="plotter-workflow/assembled-artwork-assets/v1",
            panel_id=panel.panel_id,
            source_sha256=hashlib.sha256(data).hexdigest(),
            restored_offset=[x0, y0],
        )
    ).decode()
    result = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(result) > MAX_BYTES:
        raise ValueError("prepared surface exceeds size limit")
    return result


def prepare_layout_assets(*, producer_bundle, handoff, output_dir, overwrite=False):
    bundle = Path(producer_bundle).resolve()
    handoff = Path(handoff).resolve()
    check_destination(output_dir, (bundle, handoff))
    report, layout = _load_handoff(handoff)
    audit_path = bundle / "design.json"
    audit = read_json(audit_path)
    audit_data = audit_path.read_bytes()
    if not _subset(report["producer_request"], audit):
        raise ValueError("producer geometry/recipe differs from exported request")
    manifest = load_logical_layer_manifest(audit_path)
    records = manifest.raw.get("surfaces")
    expected_ids = {p.panel_id for p in layout.panels}
    if (
        len(records) != len(expected_ids)
        or {r.get("domain_id") for r in records} != expected_ids
        or {r.get("surface_id") for r in records} != expected_ids
    ):
        raise ValueError("producer surfaces do not map one-to-one to layout panels")
    surfaces = {r["domain_id"]: r for r in records}
    prepared = []
    total = len(audit_data) + len(json_bytes(report))
    for panel in layout.panels:
        record = surfaces[panel.panel_id]
        relative = f"surfaces/{panel.panel_id}.svg"
        if record["path"] != relative:
            raise ValueError(
                "producer surface path differs from explicit panel binding"
            )
        source = (bundle / relative).resolve()
        if (
            not source.is_relative_to(bundle)
            or not source.is_file()
            or source.stat().st_size > MAX_BYTES
        ):
            raise ValueError("unsafe/oversized producer surface")
        validate_surface_against_manifest(source, manifest)
        data = _restore_svg(source.read_bytes(), panel, source)
        total += len(data)
        if total > 64 * 1024 * 1024:
            raise ValueError("prepared bundle exceeds cumulative size limit")
        new_record = copy.deepcopy(record)
        new_record["sha256"] = hashlib.sha256(data).hexdigest()
        prepared.append((relative, data, new_record))
    derivative = dict(
        schema="plotter-workflow/assembled-artwork-assets/v1",
        schema_version=1,
        logical_layer_contract=manifest.raw["logical_layer_contract"],
        logical_layers=manifest.raw["logical_layers"],
        surfaces=[r for _, _, r in prepared],
        adapter_provenance=dict(
            producer_design_sha256=hashlib.sha256(audit_data).hexdigest(),
            handoff_sha256=hashlib.sha256(handoff.read_bytes()).hexdigest(),
            layout_profile=layout.profile_id,
            validation_status=layout.validation_status,
        ),
    )

    def write(stage):
        (stage / "surfaces").mkdir()
        for name, data, _ in prepared:
            (stage / name).write_bytes(data)
        (stage / "producer-design.json").write_bytes(audit_data)
        (stage / "layout-handoff.json").write_bytes(json_bytes(report))
        (stage / "design.json").write_bytes(json_bytes(derivative))
        staged_manifest = load_logical_layer_manifest(stage / "design.json")
        for name, _, _ in prepared:
            validate_surface_against_manifest(stage / name, staged_manifest)
            inspect_svg_source(stage / name)

    return atomic_directory(
        output_dir, write, overwrite=overwrite, protected=(bundle, handoff)
    )
