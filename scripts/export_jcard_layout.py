#!/usr/bin/env python3
"""Export selected cassette J-card face requests without running a generator."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imposition.artwork_io import check_destination, read_json
from imposition.jcard_artwork import write_jcard_export
from imposition.jcard_config import load_jcard_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_jcard_config(read_json(args.config), base_dir=args.config.resolve().parent)
        check_destination(args.output_dir, (args.config,))
        result = write_jcard_export(config, args.output_dir, overwrite=args.overwrite)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    for face in config.selected_faces:
        print(result / face / "artwork-job.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
