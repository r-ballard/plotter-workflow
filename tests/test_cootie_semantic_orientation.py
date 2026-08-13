from __future__ import annotations

import json
from pathlib import Path

import pytest

import cootie_impose as cootie


def _generic_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
        'viewBox="0 0 100 100"><path d="M 10 10 L 90 90"/></svg>'
    )


def _intrinsic_svg(up_vector: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
        'viewBox="0 0 100 100" '
        'data-viz-canvas-version="1" '
        'data-viz-canvas-shape="triangle" '
        'data-viz-canvas-coordinate-system="svg-y-down" '
        'data-viz-canvas-up-anchor="vertex:0" '
        f'data-viz-canvas-up-vector="{up_vector}" '
        'data-viz-canvas-polygon="50,0 100,100 0,100">'
        '<path d="M 50 5 L 95 95 L 5 95 Z"/></svg>'
    )


def _semantic_manifest(tmp_path: Path) -> Path:
    panels: list[dict[str, object]] = []
    for slot in cootie.EXPECTED_SLOTS:
        filename = f"{slot}.svg"
        source = tmp_path / filename
        if slot == "selector-1":
            source.write_text(
                _intrinsic_svg("0.7071067811865476,-0.7071067811865476"),
                encoding="utf-8",
            )
        elif slot == "selector-3":
            source.write_text(_intrinsic_svg("0,1"), encoding="utf-8")
        else:
            source.write_text(_generic_svg(), encoding="utf-8")

        entry: dict[str, object] = {"slot": slot, "source": filename}
        if slot == "selector-3":
            entry["rotation_degrees"] = 270
        panels.append(entry)

    manifest = tmp_path / "cootie.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "layout": "cootie_catcher",
                "panels": panels,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_manifest_orientation_policy_precedence(tmp_path: Path) -> None:
    manifest = _semantic_manifest(tmp_path)
    entries = cootie.load_manifest(
        tmp_path,
        manifest,
        default_fit="contain",
        default_margin_mm=3.0,
    )
    by_slot = {entry.slot: entry for entry in entries}

    legacy = by_slot["outer-2"]
    assert legacy.orientation_policy == "legacy-default"
    assert legacy.source_intrinsic_canvas is None
    assert legacy.rotation_override_degrees is None
    assert legacy.rotation_degrees == 90

    intrinsic = by_slot["selector-1"]
    assert intrinsic.orientation_policy == "intrinsic-up-vector"
    assert intrinsic.source_intrinsic_canvas is not None
    assert intrinsic.source_intrinsic_canvas.up_anchor == "vertex:0"
    assert intrinsic.target_up_vector == (0.0, -1.0)
    assert intrinsic.rotation_degrees == pytest.approx(315.0)

    override = by_slot["selector-3"]
    assert override.orientation_policy == "explicit-override"
    assert override.source_intrinsic_canvas is not None
    assert override.source_intrinsic_canvas.up_vector == (0.0, 1.0)
    assert override.rotation_override_degrees == 270
    assert override.rotation_degrees == 270
