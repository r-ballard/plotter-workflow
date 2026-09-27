# Regression tests for input/resolved pen-plan sidecar naming.

from __future__ import annotations

import json
from pathlib import Path

import pytest

import pen_plan
from pen_plan import (
    default_pen_plan_path,
    default_resolved_pen_plan_path,
    discover_pen_plan,
    discover_resolved_pen_plan_path,
)


def valid_logical_sidecar():
    return {
        "schema_version": 2,
        "kind": "resolved-dpx3300-logical-pass",
        "pass_id": "ink",
        "pass_number": 1,
        "pass_count": 2,
        "source_svg": "drawing.svg",
        "source_svg_sha256": "a" * 64,
        "source_manifest_hash": "b" * 64,
        "assignments": [{"layer_ids": ["orbit", "body"], "physical_slot": 7}],
        "omitted_layers": ["accent"],
        "repeated_layers": ["orbit"],
        "physical_slots": [7],
    }


def test_logical_sidecar_round_trip_is_strict_and_deterministic(tmp_path):
    path = tmp_path / "drawing.ink.resolved.penplan.json"
    payload = valid_logical_sidecar()
    pen_plan.write_resolved_plot_pass(path, payload)
    first = path.read_bytes()
    assert pen_plan.load_resolved_plot_pass(path) == payload
    pen_plan.write_resolved_plot_pass(path, payload)
    assert path.read_bytes() == first
    with pytest.raises(pen_plan.PenPlanError, match="schema_version"):
        pen_plan.load_resolved_pen_plan(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 1),
        ("kind", "resolved-dpx3300-pen-plan"),
        ("pass_number", True),
        ("pass_number", 3),
        ("pass_count", 0),
        ("source_manifest_hash", "wrong"),
        ("source_svg_sha256", ""),
        ("physical_slots", [1]),
        ("omitted_layers", ["orbit"]),
        ("assignments", [{"layer_ids": ["orbit"], "physical_slot": 9}]),
        ("assignments", [{"layer_ids": ["orbit", "orbit"], "physical_slot": 1}]),
    ],
)
def test_logical_sidecar_rejects_ambiguous_or_invalid_payloads(tmp_path, field, value):
    payload = valid_logical_sidecar()
    payload[field] = value
    path = _write_json(tmp_path / "pass.resolved.penplan.json", payload)
    with pytest.raises(pen_plan.PenPlanError):
        pen_plan.load_resolved_plot_pass(path)


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
