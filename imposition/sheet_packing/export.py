"""Atomic publication of the entire selected multi-sheet, multi-face job."""

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict

from logical_layer_contract import NEUTRAL_CONTRACT, LogicalLayerMetadata, inspect_svg_contract

from scripts import booklet_impose as booklet

from ..artwork_io import atomic_directory, json_bytes
from ..artwork_layout import MM_TO_PX, _thaw
from .budget import PackingBudget
from .geometry import back_matrix, effective_area, intersection
from .jcard import instances, prepare_objects
from .layers import resolve_catalog
from .model import RectMM
from .render import SVG, _BudgetWriter, render_sheet_face, sheet_metadata
from .solver import pack


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _preview(config, result, budget):
    w, h = config.sheet.width_mm, config.sheet.height_mm
    root = ET.Element(
        SVG + "svg",
        dict(
            width=f"{w}mm",
            height=f"{result.sheet_count * (h + 15)}mm",
            viewBox=f"0 0 {w} {result.sheet_count * (h + 15)}",
            **{"data-packing-diagnostic": "not-for-plotting"},
        ),
    )
    for page in range(result.sheet_count):
        group = ET.SubElement(root, SVG + "g", dict(transform=f"translate(0 {page * (h + 15)})"))
        ET.SubElement(
            group,
            SVG + "rect",
            dict(
                x="0",
                y="0",
                width=str(w),
                height=str(h),
                fill="white",
                stroke="#444",
                **{"stroke-width": "0.3"},
            ),
        )
        for p in result.placements:
            if p.sheet_index != page:
                continue
            b = p.occupied_bounds
            ET.SubElement(
                group,
                SVG + "rect",
                dict(
                    x=str(b.x),
                    y=str(b.y),
                    width=str(b.width),
                    height=str(b.height),
                    fill="#e4eef8",
                    stroke="#b67b20",
                    **{"stroke-width": "0.3"},
                ),
            )
            ET.SubElement(
                group, SVG + "text", dict(x=str(b.x + 2), y=str(b.y + 5), **{"font-size": "3"})
            ).text = f"{p.instance_id} / {p.rotation} deg"
    writer = _BudgetWriter(budget)
    ET.ElementTree(root).write(writer, encoding="utf-8", xml_declaration=True)
    return writer.getvalue()


def _ring_area(ring):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))) / 2


def _check_output(file, config, face):
    lines, read_width, read_height = booklet._read_generic(file, quantization=0.05 * MM_TO_PX)
    actual = lines.bounds()
    if actual is None:
        return None
    # The SVG reader rounds its mm-to-pixel constant. Measure in its resolved
    # physical page frame, rather than treating those pixels as our exact units.
    x0, y0, x1, y1 = actual
    x0, x1 = (v * config.sheet.width_mm / read_width for v in (x0, x1))
    y0, y1 = (v * config.sheet.height_mm / read_height for v in (y0, y1))
    # A line-only job can have zero extent on an axis; do not coerce it to RectMM.
    top, right, bottom, left = config.sheet.margins
    area = intersection(
        config.sheet.usable_front if face == "front" else config.sheet.usable_back,
        RectMM(
            left, top, config.sheet.width_mm - left - right, config.sheet.height_mm - top - bottom
        ),
    )
    if (
        x0 < area.x - 1e-7
        or y0 < area.y - 1e-7
        or x1 > area.right + 1e-7
        or y1 > area.bottom + 1e-7
    ):
        raise ValueError("plotted geometry exceeds selected face usable area")
    return (x0, y0, x1, y1)


def pack_impositions(config, *, output_dir, overwrite=False):
    budget = PackingBudget()
    objects = prepare_objects(config, budget)
    result = pack(instances(objects), config.sheet, config.gutter_mm, config.strategy, budget)
    catalog = resolve_catalog(objects, config.logical_layers)
    by_id = {o.object_id: o for o in objects}
    lookup = {f"{o.object_id}-{n:04}": o for o in objects for n in range(1, o.quantity + 1)}
    protected = tuple(
        path
        for obj in config.objects
        for f in obj.faces
        for path in (f.request.assets, f.request.template)
    )
    if config.source_path is not None:
        protected += (config.source_path,)
    faces = ("front", "back") if config.sheet.faces == "both" else ("front",)

    def write(stage):
        jobs = []
        for page in range(result.sheet_count):
            for face in faces:
                rendered = render_sheet_face(config, objects, result, page, face, catalog, budget)
                folder = stage / f"sheet-{page + 1:03}" / face
                folder.mkdir(parents=True)
                file = folder / "design.svg"
                file.write_bytes(rendered.svg_bytes)
                inspect_svg_contract(
                    file,
                    catalog=tuple(
                        LogicalLayerMetadata(v["id"], v["ordinal"], v["label"])
                        for v in catalog.catalog
                    ),
                )
                actual = _check_output(file, config, face)
                audit = json.loads(rendered.audit_bytes)
                audit.update(
                    plotted_bounds_mm=actual,
                    design_sha256=_hash(rendered.svg_bytes),
                    surfaces=[
                        dict(
                            surface_id=face,
                            domain_id=face,
                            path="design.svg",
                            sha256=_hash(rendered.svg_bytes),
                            logical_layer_ids=[v["id"] for v in catalog.catalog],
                        )
                    ],
                )
                manifest = json_bytes(audit)
                (folder / "design.json").write_bytes(manifest)
                sidecar = json_bytes(
                    dict(
                        schema_version=1,
                        source_mode="neutral",
                        logical_layer_contract=NEUTRAL_CONTRACT,
                        source_manifest_path="design.json",
                        source_manifest_sha256=_hash(manifest),
                        logical_layers=audit["logical_layers"],
                        logical_layer_ids=[v["id"] for v in catalog.catalog],
                        sheet=audit["sheet"],
                        requires_preserved_layout=True,
                    )
                )
                (folder / "design.imposition.json").write_bytes(sidecar)
                jobs.append(
                    dict(
                        sheet=page + 1,
                        face=face,
                        design=f"sheet-{page + 1:03}/{face}/design.svg",
                        manifest=f"sheet-{page + 1:03}/{face}/design.json",
                        imposition_audit=f"sheet-{page + 1:03}/{face}/design.imposition.json",
                        design_sha256=_hash(rendered.svg_bytes),
                        manifest_sha256=_hash(manifest),
                        imposition_audit_sha256=_hash(sidecar),
                    )
                )
        area = effective_area(config.sheet)
        reserved = sum(
            p.occupied_bounds.width * p.occupied_bounds.height for p in result.placements
        )
        (stage / "placement-preview.svg").write_bytes(_preview(config, result, budget))
        summary = dict(
            schema_version=1,
            sheet=sheet_metadata(config.sheet),
            sheet_count=result.sheet_count,
            requested_strategy=config.strategy,
            resolved_strategy=result.strategy,
            faces=config.sheet.faces,
            flip=config.sheet.flip,
            margins_mm=config.sheet.margins,
            gutter_mm=config.gutter_mm,
            usable_front_mm=asdict(config.sheet.usable_front),
            usable_back_mm=None
            if config.sheet.usable_back is None
            else asdict(config.sheet.usable_back),
            effective_front_mm=asdict(area),
            reserved_area_mm2=reserved,
            trim_area_mm2=sum(
                o.quantity
                * sum(
                    _ring_area(r.outer) - sum(_ring_area(h) for h in r.holes)
                    for r in o.footprint.trim_regions
                )
                for o in objects
            ),
            unused_area_mm2=area.width * area.height * result.sheet_count - reserved,
            work=dict(budget.used),
            logical_layers=[_thaw(v) for v in catalog.catalog],
            placements=[
                dict(
                    instance_id=p.instance_id,
                    sheet=p.sheet_index + 1,
                    rotation=p.rotation,
                    front_matrix_mm=p.front_matrix,
                    back_matrix_mm=back_matrix(
                        p.front_matrix, lookup[p.instance_id].native_back_to_front, config.sheet
                    )
                    if config.sheet.faces == "both"
                    else None,
                    occupied_bounds_mm=asdict(p.occupied_bounds),
                )
                for p in result.placements
            ],
            jobs=jobs,
            sources=[
                dict(
                    object_id=o.object_id,
                    profile=o.profile,
                    quantity=o.quantity,
                    native_back_to_front=by_id[o.object_id].native_back_to_front,
                    native_occupied_bounds_mm=asdict(by_id[o.object_id].footprint.occupied_bounds),
                    rotations=o.rotations,
                    bleed_allowance_mm=o.bleed_allowance_mm,
                    guides=o.guides,
                    faces=[
                        dict(
                            face=f.face,
                            assets=str(f.request.assets),
                            template=str(f.request.template),
                            template_sha256=_hash(f.request.template.read_bytes()),
                            mode=f.request.mode,
                            blank_panels=f.request.blank_panels,
                            layer_map=f.layer_map,
                        )
                        for f in o.faces
                    ],
                )
                for o in config.objects
            ],
            config_sha256=_hash(config.source_path.read_bytes())
            if config.source_path is not None
            else None,
        )
        (stage / "packing.json").write_bytes(json_bytes(summary))

    return atomic_directory(output_dir, write, overwrite=overwrite, protected=protected)
