"""Compose immutable native fragments with rigid physical placement matrices."""

import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from logical_layer_contract import NEUTRAL_CONTRACT

from scripts import booklet_impose as booklet

from ..artwork_io import json_bytes
from ..artwork_layout import MM_TO_PX, _thaw
from .geometry import back_matrix, compose, sheet_flip, transform

SVG = f"{{{booklet.SVG_NS}}}"


@dataclass(frozen=True)
class RenderedFace:
    svg_bytes: bytes
    audit_bytes: bytes
    catalog: tuple


class _BudgetWriter(io.BytesIO):
    def __init__(self, budget):
        super().__init__()
        self.budget = budget

    def write(self, data):
        self.budget.reserve("svg_bytes", len(data))
        return super().write(data)


def sheet_metadata(sheet):
    w, h = sheet.width_mm, sheet.height_mm
    name = "custom"
    for key, (known_w, known_h) in booklet.SHEET_SIZES_MM.items():
        if abs(w - known_w) < 1e-7 and abs(h - known_h) < 1e-7:
            name = key
            break
        if abs(h - known_w) < 1e-7 and abs(w - known_h) < 1e-7:
            name = key
            break
    return dict(
        name=name, orientation="landscape" if w >= h else "portrait", width_mm=w, height_mm=h
    )


def render_sheet_face(config, prepared_objects, result, sheet_index, face, catalog, budget):
    metadata = sheet_metadata(config.sheet)
    w, h = config.sheet.width_mm, config.sheet.height_mm
    root = ET.Element(
        SVG + "svg",
        {
            "width": f"{w:.17g}mm",
            "height": f"{h:.17g}mm",
            "viewBox": f"0 0 {w * MM_TO_PX:.17g} {h * MM_TO_PX:.17g}",
            booklet.LAYOUT_MARKER_ATTRIBUTE: booklet.LAYOUT_MARKER_VALUE,
            "data-plotter-workflow-page-size": metadata["name"],
            "data-plotter-workflow-orientation": metadata["orientation"],
            "data-viz-layer-contract": NEUTRAL_CONTRACT,
        },
    )
    groups = {}
    for layer in catalog.catalog:
        groups[layer["id"]] = ET.SubElement(
            root,
            SVG + "g",
            {
                "id": f"logical-layer-{layer['ordinal']}",
                "data-viz-layer-id": layer["id"],
                "data-viz-layer-ordinal": str(layer["ordinal"]),
                "data-viz-layer-label": layer["label"],
                "fill": "none",
                "stroke": "black",
            },
        )
    lookup = {
        f"{obj.object_id}-{n:04}": obj
        for obj in prepared_objects
        for n in range(1, obj.quantity + 1)
    }
    records = []
    pending_raw_bytes = 0
    for p in result.placements:
        if p.sheet_index != sheet_index:
            continue
        obj = lookup[p.instance_id]
        native = dict(obj.faces)[face]
        matrix = (
            p.front_matrix
            if face == "front"
            else back_matrix(p.front_matrix, obj.native_back_to_front, config.sheet)
        )
        a, b, c, d, e, f = matrix
        px_matrix = f"matrix({a} {b} {c} {d} {e * MM_TO_PX:.17g} {f * MM_TO_PX:.17g})"
        layer_map = catalog.maps[(obj.object_id, face)]
        for index, fragment in enumerate(native.fragments):
            budget.reserve("vertices", fragment.vertices)
            pending_raw_bytes += len(fragment.svg_bytes)
            if pending_raw_bytes + budget.used.get("svg_bytes", 0) > budget.limits["svg_bytes"]:
                raise ValueError(
                    "sheet packing svg_bytes budget exceeded before fragment duplication"
                )
            geometry = ET.fromstring(fragment.svg_bytes)
            prefix = f"i-{p.instance_id.encode().hex()}-{face}-{index}"
            booklet._namespace_neutral_fragment(geometry, prefix, obj.object_id)
            for node in geometry.iter():
                path_id = node.get("data-viz-path-id")
                if path_id is not None:
                    node.set("data-source-viz-path-id", path_id)
                    node.set("data-viz-path-id", f"{prefix}:{path_id}")
            wrapper = ET.SubElement(
                groups[layer_map[fragment.layer_id]],
                SVG + "g",
                {
                    "data-imposed-instance": p.instance_id,
                    "data-imposed-slot": fragment.panel_id,
                    "data-source-layer-id": fragment.layer_id,
                    "transform": px_matrix,
                },
            )
            wrapper.append(geometry)
        guide_matrix = (
            p.front_matrix if face == "front" else compose(sheet_flip(config.sheet), p.front_matrix)
        )
        for guide in obj.physical_guides:
            budget.reserve("vertices", len(guide.points))
            points = [transform(guide_matrix, v) for v in guide.points]
            path = "M " + " L ".join(f"{x * MM_TO_PX:.17g},{y * MM_TO_PX:.17g}" for x, y in points)
            if guide.closed:
                path += " Z"
            ET.SubElement(
                groups[dict(catalog.guide_ids)[guide.kind]],
                SVG + "path",
                {"d": path, "data-imposed-instance": p.instance_id},
            )
        records.append(
            dict(
                instance_id=p.instance_id,
                object_id=obj.object_id,
                profile=obj.profile,
                face_matrix_mm=matrix,
                native_back_to_front=obj.native_back_to_front,
                native_source=_thaw(native.provenance),
                panels=[_thaw(v) for v in native.panel_audit],
            )
        )
    writer = _BudgetWriter(budget)
    ET.ElementTree(root).write(writer, encoding="utf-8", xml_declaration=True)
    svg = writer.getvalue()
    audit = dict(
        schema_version=1,
        sheet=metadata,
        sheet_index=sheet_index,
        face=face,
        flip=config.sheet.flip,
        logical_layer_contract=NEUTRAL_CONTRACT,
        logical_layers=[_thaw(v) for v in catalog.catalog],
        instances=records,
        requires_preserved_layout=True,
    )
    return RenderedFace(svg, json_bytes(audit), catalog.catalog)
