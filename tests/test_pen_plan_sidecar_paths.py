# Regression tests for input/resolved pen-plan sidecar naming.

from __future__ import annotations

import json
from pathlib import Path

from pen_plan import (
    default_pen_plan_path,
    default_resolved_pen_plan_path,
    discover_pen_plan,
    discover_resolved_pen_plan_path,
)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_input_and_resolved_paths_are_distinct(tmp_path: Path) -> None:
    svg = tmp_path / "drawing.svg"
    hpgl = tmp_path / "drawing.hpgl"

    assert default_pen_plan_path(svg) == tmp_path / "drawing.penplan.json"
    assert default_resolved_pen_plan_path(hpgl) == (
        tmp_path / "drawing.resolved.penplan.json"
    )


def test_input_discovery_accepts_user_plan(tmp_path: Path) -> None:
    svg = tmp_path / "drawing.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    plan = _write_json(
        default_pen_plan_path(svg),
        {"schema_version": 1, "policy": "preserve"},
    )

    assert discover_pen_plan(svg) == plan


def test_input_discovery_ignores_legacy_resolved_output(tmp_path: Path) -> None:
    svg = tmp_path / "drawing.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    _write_json(
        default_pen_plan_path(svg),
        {"schema_version": 1, "kind": "resolved-dpx3300-pen-plan"},
    )

    assert discover_pen_plan(svg) is None


def test_resolved_discovery_prefers_new_filename(tmp_path: Path) -> None:
    hpgl = tmp_path / "drawing.hpgl"
    preferred = _write_json(
        default_resolved_pen_plan_path(hpgl),
        {"schema_version": 1, "kind": "resolved-dpx3300-pen-plan"},
    )
    _write_json(
        hpgl.with_suffix(".penplan.json"),
        {"schema_version": 1, "kind": "resolved-dpx3300-pen-plan"},
    )

    assert discover_resolved_pen_plan_path(hpgl) == preferred


def test_resolved_discovery_uses_only_valid_legacy_resolved_plan(
    tmp_path: Path,
) -> None:
    hpgl = tmp_path / "drawing.hpgl"
    legacy = hpgl.with_suffix(".penplan.json")
    _write_json(legacy, {"schema_version": 1, "policy": "preserve"})

    assert discover_resolved_pen_plan_path(hpgl) == (
        tmp_path / "drawing.resolved.penplan.json"
    )

    _write_json(
        legacy,
        {"schema_version": 1, "kind": "resolved-dpx3300-pen-plan"},
    )
    assert discover_resolved_pen_plan_path(hpgl) == legacy
