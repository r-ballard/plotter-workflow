#!/usr/bin/env python3
"""Generate six-cell diagnostics and three distinct ball-and-stick plot samples."""

import argparse
import copy
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
from scripts.generate_kaleidocycle_orientation_fixture import generate_fixture

WIDTH_MM = 161.291
STYLES = ("crystal-lattice", "honeycomb-nodes", "organic-network")
CATALOG = [{"id": "sticks", "label": "Bonds"}, {"id": "balls", "label": "Nodes"}]


def build_recipe(style, state):
    if style not in STYLES or state not in ("A", "B", "C", "D"):
        raise ValueError("unknown sample style/state")
    parameters = {"ball_radius_ratio": 0.21, "curve_tolerance": 0.1}
    if style == "honeycomb-nodes":
        parameters.update(lattice="honeycomb", honeycomb_rows=4, honeycomb_columns=4)
    else:
        parameters.update(lattice="triangular", rows=9, columns=9)
    if style == "crystal-lattice":
        parameters.update(ball_size_mode="seeded", ball_radius_min_ratio=0.12)
    if style == "organic-network":
        parameters.update(
            jitter=0.25,
            attraction=0.2,
            connection_probability=0.18,
            connection_span=2.0,
            max_extra_degree=1,
            exclude_crossing_connections=True,
            deformation={
                "type": "flow",
                "distance": 0.6,
                "step_size": 0.05,
                "field": {"type": "vortex", "center_x": 0.5, "center_y": 0.5},
            },
        )
    return {
        "schema_version": 1,
        "seed": 23 + STYLES.index(style) * 1000 + "ABCD".index(state) * 53,
        "passes": [
            {
                "id": "network",
                "algorithm": "ball-stick",
                "target_domain_ids": [],
                "parameters": parameters,
                "logical_layers": copy.deepcopy(CATALOG),
            }
        ],
    }


def _pack(output, name, objects, guides):
    config = {
        "schema_version": 1,
        "sheet_mm": [279.4, 215.9],
        "margins_mm": [5] * 4,
        "gutter_mm": 5,
        "objects": [
            {
                "id": name,
                "type": "kaleidocycle",
                "tetrahedron_count": 6,
                "width_mm": WIDTH_MM,
                "quantity": 1,
                "rotations": [0],
                "guides": {"cut": guides, "fold": guides},
                "states": states,
            }
            for name, states in objects
        ],
    }
    path = output / (name + ".json")
    path.write_bytes(json_bytes(config))
    return pack_impositions(
        load_packing_config(config, base_dir=output), output_dir=output / name
    )


def _penplan(path, assignments):
    path.write_bytes(
        json_bytes(
            {
                "schema_version": 3,
                "policy": "explicit",
                "passes": [
                    {
                        "id": "sample",
                        "assignments": [
                            {"layer_ids": layers, "physical_slot": slot}
                            for slot, layers in assignments
                        ],
                    }
                ],
                "omitted_layers": [],
                "repeated_layers": [],
            }
        )
    )


def generate_samples(output_dir, *, viz_repo, viz_python):
    viz_repo, viz_python = Path(viz_repo).resolve(), Path(viz_python).resolve()
    output = check_destination(output_dir, (viz_repo,))
    if output.exists():
        raise ValueError(
            "use a new output directory to preserve previous plot artifacts"
        )
    output.mkdir(parents=True)
    (output / "samples.json").write_bytes(json_bytes({"status": "building"}))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    records = []
    for style in STYLES:
        folder = output / style
        for state in "ABCD":
            layout = resolve_kaleidocycle_state(
                state, width_mm=WIDTH_MM, tetrahedron_count=6
            )
            recipe = build_recipe(style, state)
            state_root = folder / state
            export = write_layout_export(layout, recipe, state_root / "export")
            subprocess.run(
                [
                    str(viz_python),
                    "-B",
                    "-m",
                    "viz_virtualserver.cli.domain_bundle",
                    str(export / "artwork-job.json"),
                    "--output-dir",
                    str(state_root / "producer"),
                ],
                cwd=viz_repo,
                env=env,
                check=True,
            )
            prepare_layout_assets(
                producer_bundle=state_root / "producer",
                handoff=export / "layout-handoff.json",
                output_dir=state_root / "assets",
            )
        states = {s: f"{s}/assets" for s in "ABCD"}
        config = folder / "kaleidocycle.json"
        config.write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "tetrahedron_count": 6,
                    "width_mm": WIDTH_MM,
                    "position": "top-left",
                    "states": states,
                }
            )
        )
        write_kaleidocycle(config, folder / "net")
        records.append((style, {s: f"{style}/{s}/assets" for s in "ABCD"}))
    for guides, name in ((False, "sheet-artwork"), (True, "sheet-proof")):
        packed = _pack(output, name, records, guides)
        assignments = [(1, ["sticks"]), (2, ["balls"])]
        if guides:
            assignments.append((3, ["sheet-cut-guides", "sheet-fold-guides"]))
        _penplan(packed / "sheet-001/front/design.penplan.json", assignments)
    generate_fixture(output / "diagnostics", width_mm=WIDTH_MM, tetrahedron_count=6)
    diagnostic_records = [
        (mode, {s: f"diagnostics/{mode}/{s}/assets" for s in "ABCD"})
        for mode in ("panel-orientation", "state-continuity")
    ]
    packed = _pack(output, "diagnostic-sheet", diagnostic_records, True)
    _penplan(
        packed / "sheet-001/front/design.penplan.json",
        [
            (1, ["diagnostic"]),
            (3, ["sheet-cut-guides", "sheet-fold-guides"]),
        ],
    )
    (output / "samples.json").write_bytes(
        json_bytes(
            {
                "generator": "ball-stick-kaleidocycle-samples/v1",
                "status": "complete",
                "tetrahedron_count": 6,
                "width_mm": WIDTH_MM,
                "net_height_mm": 65.3,
                "sheet_mm": [279.4, 215.9],
                "margins_mm": [5] * 4,
                "gutter_mm": 5,
                "styles": list(STYLES),
                "fold_profile_status": "provisional",
                "artwork": "sheet-artwork/sheet-001/front/design.svg",
                "proof": "sheet-proof/sheet-001/front/design.svg",
                "diagnostics": "diagnostic-sheet/sheet-001/front/design.svg",
            }
        )
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viz-repo", type=Path, required=True)
    parser.add_argument("--viz-python", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    python = args.viz_python or args.viz_repo / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    try:
        result = generate_samples(
            args.output_dir, viz_repo=args.viz_repo, viz_python=python
        )
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(result / "samples.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
