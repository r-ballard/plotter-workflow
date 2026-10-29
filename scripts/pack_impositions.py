#!/usr/bin/env python3
"""Pack exact-scale prepared J-card objects into separate sheet/face plot jobs."""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imposition.artwork_io import check_destination, read_json
from imposition.sheet_packing.config import load_packing_config
from imposition.sheet_packing.export import pack_impositions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_destination(args.output_dir, (args.config,))
        config = replace(
            load_packing_config(read_json(args.config), base_dir=args.config.resolve().parent),
            source_path=args.config.resolve(),
        )
        out = pack_impositions(config, output_dir=args.output_dir, overwrite=args.overwrite)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    print(out / "packing.json")
    for job in json.loads((out / "packing.json").read_bytes())["jobs"]:
        print(out / job["design"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
