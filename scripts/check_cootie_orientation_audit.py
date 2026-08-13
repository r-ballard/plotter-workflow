#!/usr/bin/env python3
"""Validate that a cootie diagnostic job actually used semantic orientation."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

# These utilities are executable directly from scripts/ in an unpackaged uv project.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPECTED_SLOTS = importlib.import_module(
    "imposition.objects.cootie_catcher"
).EXPECTED_SLOTS


class OrientationAuditError(ValueError):
    """Raised when an imposition sidecar is unsuitable for physical validation."""


def validate_audit_payload(payload: dict[str, Any]) -> dict[str, int]:
    if payload.get("layout") != "cootie_catcher":
        raise OrientationAuditError("Audit sidecar is not a cootie_catcher imposition.")

    panels = payload.get("panels")
    if not isinstance(panels, list):
        raise OrientationAuditError("Audit sidecar must contain a panels list.")

    by_slot: dict[str, dict[str, Any]] = {}
    for raw in panels:
        if not isinstance(raw, dict) or not isinstance(raw.get("slot"), str):
            raise OrientationAuditError("Every panel audit entry must have a string slot.")
        slot = raw["slot"]
        if slot in by_slot:
            raise OrientationAuditError(f"Duplicate panel audit entry for {slot}.")
        by_slot[slot] = raw

    expected = set(EXPECTED_SLOTS)
    actual = set(by_slot)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise OrientationAuditError(
            f"Audit slots do not match the 20-slot contract; missing={missing}, extra={extra}."
        )

    triangle_count = 0
    for slot in EXPECTED_SLOTS:
        panel = by_slot[slot]
        if panel.get("orientation_policy") != "intrinsic-up-vector":
            raise OrientationAuditError(
                f"{slot}: expected orientation_policy='intrinsic-up-vector', got "
                f"{panel.get('orientation_policy')!r}."
            )
        if panel.get("rotation_override_degrees") is not None:
            raise OrientationAuditError(
                f"{slot}: diagnostic fixture must not contain a rotation override."
            )

        canvas = panel.get("source_intrinsic_canvas")
        if not isinstance(canvas, dict):
            raise OrientationAuditError(f"{slot}: missing source_intrinsic_canvas audit data.")
        if canvas.get("up_vector") not in ([0.0, -1.0], [0, -1], (0.0, -1.0), (0, -1)):
            raise OrientationAuditError(
                f"{slot}: expected canonical source up_vector [0,-1], got {canvas.get('up_vector')!r}."
            )
        if panel.get("target_up_vector") is None:
            raise OrientationAuditError(f"{slot}: missing target_up_vector audit data.")

        family = slot.split("-", 1)[0]
        expected_shape = "triangle" if family in {"selector", "reveal"} else "square"
        if canvas.get("shape") != expected_shape:
            raise OrientationAuditError(
                f"{slot}: expected intrinsic canvas shape {expected_shape!r}, got "
                f"{canvas.get('shape')!r}."
            )
        if expected_shape == "triangle":
            triangle_count += 1

    return {"panels": len(by_slot), "triangular_panels": triangle_count}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sidecar", type=Path, help="Generated *.imposition.json sidecar")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.sidecar.read_text(encoding="utf-8"))
    summary = validate_audit_payload(payload)
    print(
        "PASS: semantic orientation is active for "
        f"{summary['panels']} panels ({summary['triangular_panels']} triangular)."
    )


if __name__ == "__main__":
    main()
