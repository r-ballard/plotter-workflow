#!/usr/bin/env python3
"""Opt-in software-only producer/export/return/imposition validation."""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from imposition.artwork_bindings import apply_layout_bindings
from imposition.artwork_export import SVG_NS, write_layout_export
from imposition.artwork_io import atomic_directory, json_bytes, read_json
from imposition.artwork_layout import resolve_booklet_spread
from imposition.artwork_return import prepare_layout_assets
from imposition.assembled_profiles import load_cootie_assembled_profile
from imposition.objects.cootie_catcher import EXPECTED_SLOTS, LEGACY_ROTATIONS
from logical_layer_contract import (
    inspect_svg_contract,
    load_logical_layer_manifest,
    validate_surface_against_manifest,
)
from scripts import booklet_impose as booklet
from scripts import cootie_impose as cootie


def _blank_surface(path, width, height, domain_id):
    r = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "viewBox": f"0 0 {width:.17g} {height:.17g}",
            "width": str(width),
            "height": str(height),
            "data-viz-layer-contract": "viz-logical-layers/v1",
            "data-viz-canvas-version": "1",
            "data-viz-canvas-shape": "rectangle",
            "data-viz-canvas-coordinate-system": "svg-y-down",
            "data-viz-canvas-up-anchor": "edge:0",
            "data-viz-canvas-up-vector": "0,-1",
            "data-viz-canvas-polygon": f"0,0 {width},0 {width},{height} 0,{height}",
        },
    )
    ET.SubElement(r, f"{{{SVG_NS}}}metadata").text = (
        "Software validation blank; not user artwork: " + domain_id
    )
    path.write_bytes(ET.tostring(r, encoding="utf-8", xml_declaration=True))


def _complete_fixture(prepared, destination, layout):
    shutil.copytree(prepared, destination)
    audit = read_json(destination / "design.json")
    audit["software_validation_fixture"] = True
    records = {r["domain_id"]: r for r in audit["surfaces"]}
    kind = layout.settings["layout"]
    ids = (
        [f"page-{i}" for i in range(1, 9)]
        if kind == "booklet-spread"
        else list(EXPECTED_SLOTS)
    )
    width = layout.panels[0].canvas_polygon[2][0]
    height = layout.panels[0].canvas_polygon[2][1]
    for id in ids:
        if id in records:
            continue
        path = destination / "surfaces" / (id + ".svg")
        _blank_surface(path, width, height, id)
        audit["surfaces"].append(
            {
                "surface_id": id,
                "domain_id": id,
                "path": "surfaces/" + path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "logical_layer_ids": [],
            }
        )
    (destination / "design.json").write_bytes(json_bytes(audit))
    if kind == "booklet-spread":
        payload = {
            "schema_version": 1,
            "pages": [
                {
                    "page": i,
                    "source": f"surfaces/page-{i}.svg",
                    "margin_mm": 0.0,
                    "gutter_mm": 0.0,
                    "fit": "contain",
                }
                for i in range(1, 9)
            ],
        }
    else:
        payload = {
            "schema_version": 1,
            "panels": [
                {
                    "slot": id,
                    "source": f"surfaces/{id}.svg",
                    "fit": "contain",
                    "margin_mm": 0.0,
                    "rotation_degrees": LEGACY_ROTATIONS[id],
                }
                for id in EXPECTED_SLOTS
            ],
        }
    payload = apply_layout_bindings(payload, read_json(destination / "bindings.json"))
    manifest = destination / (
        "booklet.json" if kind == "booklet-spread" else "cootie.json"
    )
    manifest.write_bytes(json_bytes(payload))
    catalog = load_logical_layer_manifest(destination / "design.json")
    for record in audit["surfaces"]:
        validate_surface_against_manifest(destination / record["path"], catalog)
    return manifest


def run_validation(*, viz_repo, viz_python, output_dir, overwrite=False):
    viz_repo = Path(viz_repo).resolve()
    viz_python = Path(viz_python).resolve()
    if (
        not (viz_repo / "viz_virtualserver/cli/domain_bundle.py").is_file()
        or not viz_python.is_file()
    ):
        raise ValueError(
            "explicit producer checkout and Python executable are required"
        )
    examples = Path(__file__).resolve().parents[1] / "examples/assembled-artwork"
    recipe = read_json(examples / "truchet-recipe.json")
    layouts = [
        resolve_booklet_spread(
            sheet_size="letter", pages=(8, 1), margin_mm=3.0, gutter_mm=2.0
        ),
        load_cootie_assembled_profile(
            read_json(examples / "illustrative-folded-outer.json"), square_size_mm=100.0
        ),
    ]

    def build(stage):
        summary = []
        for name, layout in zip(("booklet", "cootie"), layouts):
            case = stage / name
            case.mkdir()
            write_layout_export(layout, recipe, case / "export")
            result = subprocess.run(
                [
                    str(viz_python),
                    "-B",
                    "-m",
                    "viz_virtualserver.cli.domain_bundle",
                    str(case / "export/artwork-job.json"),
                    "--output-dir",
                    str(case / "producer"),
                ],
                check=False,
                cwd=viz_repo,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            (case / "producer.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            if result.returncode:
                raise ValueError(f"{name}: producer failed: " + result.stderr[-2000:])
            prepare_layout_assets(
                producer_bundle=case / "producer",
                handoff=case / "export/layout-handoff.json",
                output_dir=case / "prepared",
            )
            manifest = _complete_fixture(case / "prepared", case / "fixture", layout)
            if name == "booklet":
                entries = booklet.load_manifest(
                    case / "fixture",
                    manifest,
                    default_fit="contain",
                    default_margin_mm=0.0,
                    default_gutter_mm=0.0,
                )
                sheet, audit, _ = booklet.render_booklet(
                    entries,
                    case / "sheet.svg",
                    sheet_name="letter",
                    quantization_mm=0.05,
                    write_guides=False,
                    overwrite=False,
                )
                audit_payload = read_json(audit)
                published_fixture = Path(output_dir).resolve() / name / "fixture"
                audit_payload["source_directory"] = str(published_fixture)
                audit_payload["source_manifest_path"] = str(published_fixture / "design.json")
                audit_payload["validation_paths_rebased_for_atomic_publication"] = True
                audit.write_bytes(json_bytes(audit_payload))
            else:
                entries = cootie.load_manifest(
                    case / "fixture", manifest, default_margin_mm=0.0
                )
                placement = cootie.square_placement(
                    "letter", position="center", square_size_mm=100.0
                )
                root, records, mode = cootie.impose(
                    entries,
                    sheet_size="letter",
                    placement=placement,
                    quantization_mm=0.05,
                )
                sheet = case / "sheet.svg"
                E = ET.ElementTree(root)
                E.write(sheet, encoding="utf-8", xml_declaration=True)
                (case / "sheet.imposition.json").write_bytes(
                    json_bytes(
                        cootie.build_audit_payload(
                            sheet_size="letter",
                            placement=placement,
                            rendered=records,
                            mode=mode,
                            quantization_mm=0.05,
                        )
                    )
                )
            contract = inspect_svg_contract(sheet)
            if contract.mode.value != "neutral":
                raise ValueError("imposition lost neutral layers")
            summary.append(
                {
                    "case": name,
                    "profile_id": layout.profile_id,
                    "validation_status": layout.validation_status,
                    "prepared_assets": len(layout.panels),
                    "fixture_only_blank_assets": len(entries) - len(layout.panels),
                    "layer_ids": [v.id for v in contract.layers],
                }
            )
        (stage / "validation.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "software_only": True,
                    "physical_acceptance_performed": False,
                    "cases": summary,
                }
            )
        )

    return atomic_directory(
        output_dir, build, overwrite=overwrite, protected=(viz_repo, viz_python)
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--viz-repo", type=Path, required=True)
    p.add_argument("--viz-python", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    try:
        result = run_validation(
            viz_repo=a.viz_repo,
            viz_python=a.viz_python,
            output_dir=a.output_dir,
            overwrite=a.overwrite,
        )
    except (ValueError, OSError) as e:
        p.error(str(e))
    print(result / "validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
