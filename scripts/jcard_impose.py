#!/usr/bin/env python3
"""Impose selected cassette faces as separate exact-scale SVG plot inputs."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imposition.artwork_io import check_destination, read_json
from imposition.jcard_config import load_jcard_config
from imposition.jcard_impose import impose_jcard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--front-assets", type=Path)
    parser.add_argument("--back-assets", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_jcard_config(read_json(args.config), base_dir=args.config.resolve().parent)
        check_destination(args.output_dir, (args.config,))
        assets = {
            face: getattr(args, f"{face}_assets")
            for face in ("front", "back")
            if getattr(args, f"{face}_assets") is not None
        }
        result = impose_jcard(
            config, assets_by_face=assets, output_dir=args.output_dir, overwrite=args.overwrite
        )
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    for face in config.selected_faces:
        print(result / face / "design.svg")
    print(result / "jcard-jobs.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
