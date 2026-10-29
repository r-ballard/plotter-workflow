"""Exact-scale native-face rendering and atomic paired job publication."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from logical_layer_contract import NEUTRAL_CONTRACT, LogicalLayerMetadata, inspect_svg_contract

from scripts import booklet_impose as booklet

from .artwork_io import atomic_directory, json_bytes
from .artwork_layout import MM_TO_PX, _thaw
from .jcard_native import NativeFaceRequest, prepare_native_face
from .jcard_placement import resolve_jcard_placement


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_face(config, face, bundle, placement):
    recipe = getattr(config, f"{face}_artwork")
    native = prepare_native_face(
        NativeFaceRequest(
            config.profile, face, bundle, recipe.template, recipe.mode, recipe.blank_panels
        )
    )
    bundle = Path(bundle).resolve()
    layers = tuple(
        SimpleNamespace(id=v["id"], ordinal=v["ordinal"], label=v["label"]) for v in native.catalog
    )
    reserved = {
        "cut": "jcard-cut-guides",
        "fold": "jcard-fold-guides",
        "registration": "jcard-registration",
    }
    if {reserved[k] for k in config.guides} & {layer.id for layer in layers}:
        raise ValueError("Enabled guide ID collides with artwork layer")
    sheet = config.sheet
    root = ET.Element(
        f"{{{booklet.SVG_NS}}}svg",
        {
            "width": f"{sheet.width_mm:.17g}mm",
            "height": f"{sheet.height_mm:.17g}mm",
            "viewBox": f"0 0 {sheet.width_mm * MM_TO_PX:.17g} {sheet.height_mm * MM_TO_PX:.17g}",
            booklet.LAYOUT_MARKER_ATTRIBUTE: booklet.LAYOUT_MARKER_VALUE,
            "data-plotter-workflow-page-size": sheet.name,
            "data-plotter-workflow-orientation": sheet.orientation,
            "data-viz-layer-contract": NEUTRAL_CONTRACT,
        },
    )
    catalog = [_thaw(v) for v in native.catalog]
    groups = {}
    for layer in layers:
        groups[layer.id] = ET.SubElement(
            root,
            f"{{{booklet.SVG_NS}}}g",
            {
                "id": f"logical-layer-{layer.ordinal}",
                "data-viz-layer-id": layer.id,
                "data-viz-layer-ordinal": str(layer.ordinal),
                "data-viz-layer-label": layer.label,
                "fill": "none",
                "stroke": "black",
            },
        )
    matrix = placement.face_matrix(face)
    a, _, _, d, tx, ty = matrix
    records = [_thaw(v) for v in native.panel_audit]
    for fragment in native.fragments:
        wrapper = ET.SubElement(
            groups[fragment.layer_id],
            f"{{{booklet.SVG_NS}}}g",
            {
                "data-imposed-slot": fragment.panel_id,
                "transform": f"matrix({a} 0 0 {d} {tx * MM_TO_PX:.17g} {ty * MM_TO_PX:.17g})",
            },
        )
        wrapper.append(ET.fromstring(fragment.svg_bytes))
    next_ordinal = max(layer.ordinal for layer in layers) + 1
    for kind in ("cut", "fold", "registration"):
        if kind not in config.guides:
            continue
        layer_id = reserved[kind]
        group = ET.SubElement(
            root,
            f"{{{booklet.SVG_NS}}}g",
            {
                "id": layer_id,
                "data-viz-layer-id": layer_id,
                "data-viz-layer-ordinal": str(next_ordinal),
                "data-viz-layer-label": layer_id,
                "fill": "none",
                "stroke": "black",
            },
        )
        catalog.append({"id": layer_id, "ordinal": next_ordinal, "label": layer_id})
        next_ordinal += 1
        for guide in placement.face_guides(face):
            if guide.kind == kind:
                path = (
                    "M "
                    + " L ".join(
                        f"{x * MM_TO_PX:.17g},{y * MM_TO_PX:.17g}" for x, y in guide.points
                    )
                    + (" Z" if guide.closed else "")
                )
                ET.SubElement(group, f"{{{booklet.SVG_NS}}}path", {"d": path})
    svg = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    audit = {
        "schema_version": 1,
        "profile": config.profile,
        "face": face,
        "flip": config.flip,
        "sheet": {
            "name": sheet.name,
            "orientation": sheet.orientation,
            "width_mm": sheet.width_mm,
            "height_mm": sheet.height_mm,
        },
        "face_matrix_mm": matrix,
        "logical_layer_contract": NEUTRAL_CONTRACT,
        "logical_layers": catalog,
        "source_manifest_sha256": digest(bundle / "design.json"),
        "handoff_sha256": digest(bundle / "layout-handoff.json"),
        "producer_design_sha256": digest(bundle / "producer-design.json"),
        "panels": records,
        "requires_preserved_layout": True,
        "design_sha256": hashlib.sha256(svg).hexdigest(),
        "surfaces": [
            {
                "surface_id": face,
                "domain_id": face,
                "path": "design.svg",
                "sha256": hashlib.sha256(svg).hexdigest(),
                "logical_layer_ids": [v["id"] for v in catalog],
            }
        ],
    }
    return svg, json_bytes(audit), catalog


def impose_jcard(config, *, assets_by_face, output_dir, overwrite=False):
    if set(assets_by_face) != set(config.selected_faces):
        raise ValueError("Asset directories must match selected faces exactly")
    placement = resolve_jcard_placement(config)

    def write(stage):
        faces = []
        for face in config.selected_faces:
            svg, audit, catalog = render_face(config, face, assets_by_face[face], placement)
            folder = stage / face
            folder.mkdir()
            (folder / "design.svg").write_bytes(svg)
            (folder / "design.json").write_bytes(audit)
            payload = json.loads(audit)
            (folder / "design.imposition.json").write_bytes(
                json_bytes(
                    {
                        "schema_version": 1,
                        "source_mode": "neutral",
                        "logical_layer_contract": NEUTRAL_CONTRACT,
                        "source_manifest_path": "design.json",
                        "source_manifest_sha256": digest(folder / "design.json"),
                        "logical_layers": catalog,
                        "logical_layer_ids": [v["id"] for v in catalog],
                        "sheet": payload["sheet"],
                        "requires_preserved_layout": True,
                    }
                )
            )
            inspect_svg_contract(
                folder / "design.svg",
                catalog=tuple(
                    LogicalLayerMetadata(item["id"], item["ordinal"], item["label"])
                    for item in catalog
                ),
            )
            faces.append(
                {
                    "face": face,
                    "design": f"{face}/design.svg",
                    "design_sha256": digest(folder / "design.svg"),
                    "manifest": f"{face}/design.json",
                    "manifest_sha256": digest(folder / "design.json"),
                    "imposition_audit": f"{face}/design.imposition.json",
                    "imposition_audit_sha256": digest(folder / "design.imposition.json"),
                }
            )
        p = placement.front_reference
        (stage / "jcard-jobs.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "profile": config.profile,
                    "flip": config.flip,
                    "sheet": {
                        "name": config.sheet.name,
                        "width_mm": config.sheet.width_mm,
                        "height_mm": config.sheet.height_mm,
                    },
                    "front_reference_mm": [p.x_mm, p.y_mm, p.width_mm, p.height_mm],
                    "faces": faces,
                }
            )
        )

    return atomic_directory(
        output_dir,
        write,
        overwrite=overwrite,
        protected=tuple(assets_by_face.values())
        + tuple(getattr(config, f"{face}_artwork").template for face in config.selected_faces),
    )
