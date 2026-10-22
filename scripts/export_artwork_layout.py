#!/usr/bin/env python3
"""Export resolved reading/folded layouts as continuous artwork job requests."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from imposition.artwork_export import write_layout_export
from imposition.artwork_io import read_json
from imposition.artwork_layout import resolve_booklet_spread
from imposition.assembled_profiles import load_cootie_assembled_profile


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--layout", choices=["booklet-spread", "cootie-folded-outer"], required=True
    )
    p.add_argument("--sheet-size")
    p.add_argument("--spread", nargs=2, type=int)
    p.add_argument("--margin-mm", type=float)
    p.add_argument("--gutter-mm", type=float)
    p.add_argument("--square-size-mm", type=float)
    p.add_argument("--profile", type=Path)
    p.add_argument("--job-template", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.layout == "booklet-spread":
            if a.profile is not None or a.square_size_mm is not None:
                raise ValueError("profile/square size require folded layout")
            if a.spread is None:
                raise ValueError("booklet export requires --spread LEFT RIGHT")
            layout = resolve_booklet_spread(
                sheet_size=a.sheet_size or "letter",
                pages=tuple(a.spread),
                margin_mm=a.margin_mm if a.margin_mm is not None else 0.0,
                gutter_mm=a.gutter_mm if a.gutter_mm is not None else 0.0,
            )
        else:
            if any(
                v is not None
                for v in (a.sheet_size, a.spread, a.margin_mm, a.gutter_mm)
            ):
                raise ValueError("booklet controls are inactive for folded layout")
            if a.profile is None or a.square_size_mm is None:
                raise ValueError(
                    "folded export requires explicit --profile and --square-size-mm"
                )
            layout = load_cootie_assembled_profile(
                read_json(a.profile), square_size_mm=a.square_size_mm
            )
        result = write_layout_export(
            layout,
            read_json(a.job_template),
            a.output_dir,
            overwrite=a.overwrite,
            protected_paths=[a.job_template] + ([a.profile] if a.profile else []),
        )
    except (ValueError, OSError, TypeError) as e:
        p.error(str(e))
    print(result / "artwork-job.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
