#!/usr/bin/env python3
"""Impose four prepared kaleidocycle state bundles onto a cut-and-fold net."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from imposition.kaleidocycle_impose import write_kaleidocycle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = write_kaleidocycle(
            args.config, args.output_dir, overwrite=args.overwrite
        )
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    print(output / "design.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
