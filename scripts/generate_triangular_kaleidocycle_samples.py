#!/usr/bin/env python3
"""Build three triangular Truchet kaleidocycles through validated handoffs."""

import argparse
import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imposition.artwork_export import write_layout_export
from imposition.artwork_io import check_destination, json_bytes
from imposition.artwork_return import prepare_layout_assets
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state
from imposition.kaleidocycle_impose import write_kaleidocycle
from imposition.sheet_packing.config import load_packing_config
from imposition.sheet_packing.export import pack_impositions

WIDTH_MM = 213.531
STYLES = ("curves", "light-fill", "multiscale")
CATALOG = [
    {"id": "curve", "label": "Truchet curves"},
    {"id": "vertex-fill", "label": "Vertex hatching"},
    {"id": "interstitial-fill", "label": "Interstitial dots"},
]


def build_recipe(style, state, layout):
    if style not in STYLES or state not in "ABCD" or len(state) != 1:
        raise ValueError("unknown triangular kaleidocycle style/state")
    # Bound the map from physical pen radius to composition coordinates for
    # every panel. Affine foreshortening must not shrink the requested clearance.
    norm = 0.0
    for panel in layout.panels:
        a, b, c, d, _, _ = panel.assembled_matrix
        tr = a * a + b * b + c * c + d * d
        det = (a * d - b * c) ** 2
        norm = max(norm, math.sqrt((tr + math.sqrt(max(0, tr * tr - 4 * det))) / 2))
    units = norm / layout.settings["source_unit_mm"]
    index = "ABCD".index(state)
    parameters = {
        "curve_layer_id": "curve",
        "curve_tolerance": 0.08,
        "region_fills": {},
        "seam_margin": 0.15 * units,
    }
    if style == "multiscale":
        algorithm = "truchet-triangular-multiscale"
        parameters.update(base_tile_size=160.0, max_depth=1, split_probability=0.38)
    else:
        algorithm = "truchet-triangular"
        parameters["tile_size"] = 80.0 if style == "curves" else 112.0
    if style == "light-fill":
        parameters["region_fills"] = {
            "vertex": {
                "effect": "parallel-hatch",
                "layer_id": "vertex-fill",
                "parameters": {"spacing": 14.0, "angle": 15.0 + index * 45},
                "pen_width": 0.3 * units,
                "clearance": 0.1 * units,
            },
            "interstitial": {
                "effect": "stroke-dots",
                "layer_id": "interstitial-fill",
                "parameters": {"spacing": 14.0, "mark_length": 2.0, "density": 0.55},
                "pen_width": 0.3 * units,
                "clearance": 0.1 * units,
            },
        }
    return {
        "schema_version": 1,
        "seed": 31 + index * 53 + STYLES.index(style) * 1000,
        "domains": [],
        "passes": [
            {
                "id": "triangles",
                "algorithm": algorithm,
                "target_domain_ids": [],
                "parameters": parameters,
                "logical_layers": copy.deepcopy(CATALOG),
            }
        ],
    }


def generate_samples(output_dir, *, viz_repo, viz_python, overwrite=False):
    viz_repo = Path(viz_repo).resolve()
    viz_python = Path(viz_python).resolve()
    output = check_destination(output_dir, (viz_repo,))
    marker = output / "samples.json"
    if output.exists() and (
        not overwrite
        or not marker.is_file()
        or json.loads(marker.read_text()).get("generator")
        != "triangular-kaleidocycle-samples/v1"
    ):
        raise ValueError("overwrite requires a recognized triangular sample directory")
    output.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(
        json_bytes(
            {"generator": "triangular-kaleidocycle-samples/v1", "status": "building"}
        )
    )
    records = []
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for style in STYLES:
        folder = output / style
        folder.mkdir(exist_ok=True)
        for state in "ABCD":
            layout = resolve_kaleidocycle_state(
                state, width_mm=WIDTH_MM, tetrahedron_count=8
            )
            recipe = build_recipe(style, state, layout)
            recipes = folder / "recipes"
            recipes.mkdir(exist_ok=True)
            template = recipes / (state + ".json")
            template.write_bytes(json_bytes(recipe))
            state_root = folder / state
            export = write_layout_export(
                layout,
                recipe,
                state_root / "export",
                overwrite=overwrite,
                protected_paths=(template,),
            )
            command = [
                str(viz_python),
                "-B",
                "-m",
                "viz_virtualserver.cli.domain_bundle",
                str(export / "artwork-job.json"),
                "--output-dir",
                str(state_root / "producer"),
            ]
            if overwrite:
                command.append("--overwrite")
            subprocess.run(command, cwd=viz_repo, env=env, check=True)
            prepare_layout_assets(
                producer_bundle=state_root / "producer",
                handoff=export / "layout-handoff.json",
                output_dir=state_root / "assets",
                overwrite=overwrite,
            )
        single = {
            "schema_version": 1,
            "sheet_size": "letter",
            "tetrahedron_count": 8,
            "width_mm": WIDTH_MM,
            "margin_mm": 5,
            "position": "top-left",
            "states": {s: f"{s}/assets" for s in "ABCD"},
        }
        config = folder / "kaleidocycle.json"
        config.write_bytes(json_bytes(single))
        sheet = write_kaleidocycle(config, folder / "net", overwrite=overwrite)
        records.append(
            {
                "style": style,
                "net": str(sheet.relative_to(output)),
                "states": {s: f"{style}/{s}/assets" for s in "ABCD"},
            }
        )
    for guides, name in ((False, "sheet-artwork"), (True, "sheet-proof")):
        config = {
            "schema_version": 1,
            "sheet_mm": [279.4, 215.9],
            "margins_mm": [5, 5, 5, 5],
            "gutter_mm": 5,
            "objects": [
                {
                    "id": style,
                    "type": "kaleidocycle",
                    "tetrahedron_count": 8,
                    "quantity": 1,
                    "width_mm": WIDTH_MM,
                    "rotations": [0],
                    "guides": {"cut": guides, "fold": guides},
                    "states": {s: f"{style}/{s}/assets" for s in "ABCD"},
                }
                for style in STYLES
            ],
        }
        config_path = output / (name + ".json")
        config_path.write_bytes(json_bytes(config))
        parsed = load_packing_config(config, base_dir=output)
        pack_impositions(parsed, output_dir=output / name, overwrite=overwrite)
    summary = {
        "generator": "triangular-kaleidocycle-samples/v1",
        "status": "complete",
        "width_mm": WIDTH_MM,
        "net_height_mm": 65.3,
        "sheet_mm": [279.4, 215.9],
        "margins_mm": [5] * 4,
        "gutter_mm": 5,
        "nominal_pen_mm": 0.3,
        "fold_profile_status": "provisional",
        "samples": records,
        "artwork": "sheet-artwork/sheet-001/front/design.svg",
        "proof": "sheet-proof/sheet-001/front/design.svg",
    }
    marker.write_bytes(json_bytes(summary))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viz-repo", type=Path, required=True)
    parser.add_argument("--viz-python", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    python = args.viz_python or args.viz_repo / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    try:
        output = generate_samples(
            args.output_dir,
            viz_repo=args.viz_repo,
            viz_python=python,
            overwrite=args.overwrite,
        )
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(output / "samples.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
