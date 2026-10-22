#!/usr/bin/env python3
"""Restore exported layout crops to full-canvas neutral imposition assets."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from imposition.artwork_return import prepare_layout_assets


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--producer-bundle", type=Path, required=True)
    p.add_argument("--handoff", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    try:
        result = prepare_layout_assets(
            producer_bundle=a.producer_bundle,
            handoff=a.handoff,
            output_dir=a.output_dir,
            overwrite=a.overwrite,
        )
    except (ValueError, OSError, TypeError, KeyError) as e:
        p.error(str(e))
    print(result / "design.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
