#!/usr/bin/env python3
"""Generate a deterministic physical-orientation fixture for the cootie catcher.

The generated SVGs are vector-only and declare the v1 intrinsic-canvas contract.
Every source uses canonical SVG-up ``(0,-1)`` and contains asymmetric markers so
rotation and reflection remain observable after physical folding.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

# These utilities are executable directly from scripts/ in an unpackaged uv project.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_model = importlib.import_module("imposition.model")
_cootie = importlib.import_module("imposition.objects.cootie_catcher")
IntrinsicCanvas = _model.IntrinsicCanvas
COOTIE_CATCHER = _cootie.COOTIE_CATCHER
EXPECTED_SLOTS = _cootie.EXPECTED_SLOTS

SVG_NS = "http://www.w3.org/2000/svg"
CANVAS_SIZE = 100
CANONICAL_UP = (0.0, -1.0)

SQUARE_FEATURE_MAP: dict[str, dict[str, str]] = {
    "vertices": {
        "A": "vertex:0",
        "B": "vertex:1",
        "C": "vertex:2",
        "D": "vertex:3",
    },
    "edges": {
        "AB": "edge:0",
        "BC": "edge:1",
        "CD": "edge:2",
        "DA": "edge:3",
    },
}
TRIANGLE_FEATURE_MAP: dict[str, dict[str, str]] = {
    "vertices": {
        "A": "vertex:0",
        "B": "vertex:1",
        "C": "vertex:2",
    },
    "edges": {
        "AB": "edge:0",
        "BC": "edge:1",
        "CA": "edge:2",
    },
}

_SEGMENTS: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    "0": ((0, 0, 8, 0), (8, 0, 8, 8), (8, 8, 8, 16), (0, 16, 8, 16), (0, 8, 0, 16), (0, 0, 0, 8)),
    "1": ((8, 0, 8, 8), (8, 8, 8, 16)),
    "2": ((0, 0, 8, 0), (8, 0, 8, 8), (0, 8, 8, 8), (0, 8, 0, 16), (0, 16, 8, 16)),
    "3": ((0, 0, 8, 0), (8, 0, 8, 8), (0, 8, 8, 8), (8, 8, 8, 16), (0, 16, 8, 16)),
    "4": ((0, 0, 0, 8), (0, 8, 8, 8), (8, 0, 8, 8), (8, 8, 8, 16)),
    "5": ((0, 0, 8, 0), (0, 0, 0, 8), (0, 8, 8, 8), (8, 8, 8, 16), (0, 16, 8, 16)),
    "6": ((0, 0, 8, 0), (0, 0, 0, 8), (0, 8, 8, 8), (0, 8, 0, 16), (8, 8, 8, 16), (0, 16, 8, 16)),
    "7": ((0, 0, 8, 0), (8, 0, 8, 8), (8, 8, 8, 16)),
    "8": ((0, 0, 8, 0), (8, 0, 8, 8), (8, 8, 8, 16), (0, 16, 8, 16), (0, 8, 0, 16), (0, 0, 0, 8), (0, 8, 8, 8)),
    "O": ((0, 0, 8, 0), (8, 0, 8, 16), (8, 16, 0, 16), (0, 16, 0, 0)),
    "S": ((8, 0, 0, 0), (0, 0, 0, 8), (0, 8, 8, 8), (8, 8, 8, 16), (8, 16, 0, 16)),
    "R": ((0, 16, 0, 0), (0, 0, 8, 0), (8, 0, 8, 8), (8, 8, 0, 8), (0, 8, 8, 16)),
    "A": ((0, 16, 4, 0), (4, 0, 8, 16), (2, 8, 6, 8)),
    "B": (
        (0, 0, 0, 16),
        (0, 0, 6, 0),
        (6, 0, 8, 2),
        (8, 2, 8, 6),
        (8, 6, 6, 8),
        (0, 8, 6, 8),
        (6, 8, 8, 10),
        (8, 10, 8, 14),
        (8, 14, 6, 16),
        (0, 16, 6, 16),
    ),
    "C": (
        (8, 0, 2, 0),
        (2, 0, 0, 2),
        (0, 2, 0, 14),
        (0, 14, 2, 16),
        (2, 16, 8, 16),
    ),
    "D": (
        (0, 0, 0, 16),
        (0, 0, 5, 0),
        (5, 0, 8, 3),
        (8, 3, 8, 13),
        (8, 13, 5, 16),
        (0, 16, 5, 16),
    ),
}


def _glyph_path(char: str, x: float, y: float, scale: float = 1.0) -> str:
    try:
        segments = _SEGMENTS[char]
    except KeyError as exc:
        raise ValueError(f"Unsupported validation glyph {char!r}") from exc
    commands: list[str] = []
    for x1, y1, x2, y2 in segments:
        commands.append(
            f"M {x + x1 * scale:.3f} {y + y1 * scale:.3f} "
            f"L {x + x2 * scale:.3f} {y + y2 * scale:.3f}"
        )
    return " ".join(commands)


def _identifier_path(slot: str, *, triangle: bool) -> str:
    family, raw_index = slot.split("-", 1)
    family_glyph = {"outer": "O", "selector": "S", "reveal": "R"}[family]
    index_glyph = str(int(raw_index))
    y = 54.0 if triangle else 58.0
    return " ".join(
        (
            _glyph_path(family_glyph, 38.0, y, 0.8),
            _glyph_path(index_glyph, 53.0, y, 0.8),
        )
    )


def _feature_label_elements(*, triangle: bool) -> str:
    """Return vector-only vertex labels for physical orientation annotation."""

    positions = (
        {
            "A": (46.0, 5.0),
            "B": (89.0, 87.0),
            "C": (7.0, 87.0),
        }
        if triangle
        else {
            "A": (7.0, 7.0),
            "B": (89.0, 7.0),
            "C": (89.0, 88.0),
            "D": (7.0, 88.0),
        }
    )
    return "\n".join(
        f'    <path data-validation-feature="vertex:{label}" '
        f'stroke-width="1" d="{_glyph_path(label, x, y, 0.4)}"/>'
        for label, (x, y) in positions.items()
    )


def _asymmetric_markers(*, triangle: bool) -> str:
    """Return paths whose handedness is obvious after a reflection."""

    if triangle:
        border = "M 50 3 L 96 96 L 4 96 Z"
        arrow = "M 50 48 L 50 15 M 42 24 L 50 15 L 58 24"
        left = "M 20 76 L 28 68 L 28 84 Z"
        right = "M 72 68 L 82 68 L 82 78 L 72 78 Z M 74 82 L 84 82"
    else:
        border = "M 4 4 L 96 4 L 96 96 L 4 96 Z"
        arrow = "M 50 50 L 50 14 M 42 23 L 50 14 L 58 23"
        left = "M 16 78 L 25 69 L 25 87 Z"
        right = "M 73 69 L 84 69 L 84 80 L 73 80 Z M 76 85 L 87 85"
    return f"{border} {arrow} {left} {right}"


def source_svg(slot: str) -> str:
    """Return one canonical-up vector diagnostic SVG for *slot*."""

    family = slot.split("-", 1)[0]
    triangle = family in {"selector", "reveal"}
    if triangle:
        feature_map = TRIANGLE_FEATURE_MAP
        shape = "triangle"
        polygon = "50,0 100,100 0,100"
        up_anchor = "vertex:0"
    else:
        feature_map = SQUARE_FEATURE_MAP
        shape = "square"
        polygon = "0,0 100,0 100,100 0,100"
        up_anchor = "edge:0"

    paths = (
        f"{_asymmetric_markers(triangle=triangle)} "
        f"{_identifier_path(slot, triangle=triangle)}"
    )
    vertex_map = ";".join(
        f"{label}={anchor}" for label, anchor in feature_map["vertices"].items()
    )
    edge_map = ";".join(
        f"{label}={anchor}" for label, anchor in feature_map["edges"].items()
    )
    feature_labels = _feature_label_elements(triangle=triangle)

    return (
        f'<svg xmlns="{SVG_NS}" width="{CANVAS_SIZE}" height="{CANVAS_SIZE}" '
        f'viewBox="0 0 {CANVAS_SIZE} {CANVAS_SIZE}" '
        'data-viz-canvas-version="1" '
        f'data-viz-canvas-shape="{shape}" '
        'data-viz-canvas-coordinate-system="svg-y-down" '
        f'data-viz-canvas-up-anchor="{up_anchor}" '
        'data-viz-canvas-up-vector="0,-1" '
        f'data-viz-canvas-polygon="{polygon}" '
        f'data-validation-vertex-map="{vertex_map}" '
        f'data-validation-edge-map="{edge_map}" '
        f'data-validation-slot="{slot}">\n'
        '  <g fill="none" stroke="#000000" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">\n'
        f'    <path d="{paths}"/>\n'
        f'{feature_labels}\n'
        '  </g>\n'
        '</svg>\n'
    )

def _canonical_canvas(slot: str) -> IntrinsicCanvas:
    family = slot.split("-", 1)[0]
    if family in {"selector", "reveal"}:
        return IntrinsicCanvas(
            version=1,
            shape="triangle",
            coordinate_system="svg-y-down",
            polygon=((50.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
            up_anchor="vertex:0",
            up_vector=CANONICAL_UP,
        )
    return IntrinsicCanvas(
        version=1,
        shape="square",
        coordinate_system="svg-y-down",
        polygon=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        up_anchor="edge:0",
        up_vector=CANONICAL_UP,
    )


def expected_orientation_payload() -> dict[str, object]:
    """Describe the software-resolved orientation used by this physical fixture."""

    slots: list[dict[str, object]] = []
    for slot in EXPECTED_SLOTS:
        resolution = COOTIE_CATCHER.resolve_orientation(
            slot,
            source_canvas=_canonical_canvas(slot),
        )
        slots.append(
            {
                "slot": slot,
                "family": slot.split("-", 1)[0],
                "source_up_vector": list(CANONICAL_UP),
                "target_up_vector": list(resolution.target_up_vector),
                "orientation_policy": resolution.policy,
                "resolved_rotation_degrees": resolution.resolved_degrees,
            }
        )
    return {
        "schema_version": 1,
        "layout": "cootie_catcher",
        "validation_status": "provisional",
        "slots": slots,
    }


def observation_template() -> dict[str, object]:
    slots: list[dict[str, object]] = []
    for slot in EXPECTED_SLOTS:
        family = slot.split("-", 1)[0]
        shape = "triangle" if family in {"selector", "reveal"} else "square"
        slots.append(
            {
                "slot": slot,
                "family": family,
                "shape": shape,
                "desired_top_feature": None,
                "desired_right_feature": None,
                "observed_top_feature_after_fold": None,
                "observed_right_feature_after_fold": None,
                "mirrored_after_fold": None,
                "pairing_correct": None,
                "notes": "",
            }
        )
    return {
        "schema_version": 2,
        "layout": "cootie_catcher",
        "validation_status": "not-performed",
        "feature_maps": {
            "square": SQUARE_FEATURE_MAP,
            "triangle": TRIANGLE_FEATURE_MAP,
        },
        "physical_job": {
            "sheet_size": "letter",
            "square_position": "left",
            "plotter": "DPX-3300",
            "date": None,
        },
        "slots": slots,
        "overall_notes": "",
    }

def generate_fixture(output_dir: Path, *, overwrite: bool = False) -> None:
    """Create source SVGs, manifest, expected orientation, and observation template."""

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    panels_dir = output_dir / "panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    panels: list[dict[str, object]] = []
    for slot in EXPECTED_SLOTS:
        relative = Path("panels") / f"{slot}.svg"
        destination = output_dir / relative
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing fixture source: {destination}")
        destination.write_text(source_svg(slot), encoding="utf-8", newline="\n")
        panels.append(
            {
                "slot": slot,
                "source": relative.as_posix(),
                "fit": "contain",
                "margin_mm": 2.0,
            }
        )

    files = {
        "cootie.json": {
            "schema_version": 1,
            "layout": "cootie_catcher",
            "panels": panels,
        },
        "expected_orientation.json": expected_orientation_payload(),
        "physical_validation.template.json": observation_template(),
    }
    for filename, payload in files.items():
        path = output_dir / filename
        if path.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing fixture file: {path}")
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/cootie_orientation_validation"),
        help="Fixture directory. Default: output/cootie_orientation_validation",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_fixture(args.output_dir, overwrite=args.overwrite)
    print(f"Generated cootie orientation fixture: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
