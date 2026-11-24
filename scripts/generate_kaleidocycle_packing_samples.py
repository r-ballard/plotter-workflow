#!/usr/bin/env python3
"""Regenerate the committed Letter 1/2/3-up kaleidocycle diagnostic examples."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imposition.artwork_io import check_destination, json_bytes, read_json
from imposition.sheet_packing.config import load_packing_config
from imposition.sheet_packing.export import pack_impositions
from scripts.generate_kaleidocycle_orientation_fixture import generate_fixture

REPO = Path(__file__).resolve().parents[1]


def generate_samples(output_dir, *, overwrite=False):
    templates = [REPO / f"examples/kaleidocycle/letter-{n}-up.json" for n in (1, 2, 3)]
    output = check_destination(output_dir, templates)
    if output.exists() and (
        not overwrite
        or not (output / "samples.json").is_file()
        or read_json(output / "samples.json").get("generator")
        != "kaleidocycle-letter-packing/v1"
    ):
        raise ValueError(
            "output exists; overwrite requires a recognized sample directory"
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "samples.json").write_bytes(
        json_bytes(
            {
                "generator": "kaleidocycle-letter-packing/v1",
                "schema_version": 1,
                "status": "building",
            }
        )
    )
    # Each physical width has its own matching handoffs and prepared assets.
    for folder, width in (("full-size", 269.4), ("three-up", 213.531)):
        generate_fixture(
            output / folder, width_mm=width, tetrahedron_count=8, overwrite=overwrite
        )
    records = []
    for n, path in enumerate(templates, 1):
        raw = read_json(path)
        variant = "full-size" if n < 3 else "three-up"
        raw["objects"][0]["states"] = {
            s: f"{variant}/panel-orientation/{s}/assets" for s in "ABCD"
        }
        config_path = output / f"letter-{n}-up.json"
        config_path.write_bytes(json_bytes(raw))
        config = replace(
            load_packing_config(raw, base_dir=output), source_path=config_path
        )
        folder = pack_impositions(
            config, output_dir=output / f"letter-{n}-up", overwrite=overwrite
        )
        report = read_json(folder / "packing.json")
        for job in report["jobs"]:
            file = folder / job["design"]
            file.with_suffix(".penplan.json").write_bytes(
                json_bytes(
                    {
                        "schema_version": 3,
                        "policy": "explicit",
                        "passes": [
                            {
                                "id": "proof",
                                "assignments": [
                                    {
                                        "layer_ids": [
                                            v["id"] for v in report["logical_layers"]
                                        ],
                                        "physical_slot": 1,
                                    }
                                ],
                            }
                        ],
                        "slots": [
                            {
                                "slot": 1,
                                "tool": "Diagnostic marking pen",
                                "label": "Packed net proof",
                            }
                        ],
                        "omitted_layers": [],
                        "repeated_layers": [],
                        "notes": "Marking pen only; no cutter/scorer is commanded. Verify loaded pen; force unmanaged.",
                    }
                )
            )
        records.append(
            {
                "copies": n,
                "width_mm": raw["objects"][0]["width_mm"],
                "packing": f"letter-{n}-up/packing.json",
                "config": config_path.name,
            }
        )
    (output / "samples.json").write_bytes(
        json_bytes(
            {
                "generator": "kaleidocycle-letter-packing/v1",
                "schema_version": 1,
                "status": "complete",
                "samples": records,
            }
        )
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/hardware-acceptance/kaleidocycle-letter-packing"),
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = generate_samples(args.output_dir, overwrite=args.overwrite)
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(result / "samples.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
