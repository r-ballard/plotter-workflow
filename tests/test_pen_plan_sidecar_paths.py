"""Only current resolved audit suffix/schema is accepted; no stale fallback."""

import hashlib
import json

import pytest

from pen_plan import (
    default_pen_plan_path,
    default_resolved_pen_plan_path,
    discover_pen_plan,
    discover_resolved_pen_plan_path,
    validate_resolved_sidecar_for_hpgl,
)
from pen_plan_io import (
    load_resolved_plot_pass,
    parse_resolved,
    resolved_payload,
    write_resolved_plot_pass,
)
from pen_plan_models import Assignment, ResolvedPlotPass


def current(tmp_path):
    hpgl = tmp_path / "drawing.hpgl"
    hpgl.write_text("IN;SP7;PU0,0;PD1,1;PU;SP0;")
    plan = ResolvedPlotPass(
        "drawing.svg",
        "a" * 64,
        "b" * 64,
        "ink",
        1,
        2,
        "explicit",
        (Assignment(("orbit", "body"), 7),),
        (7,),
        ("accent",),
        ("orbit",),
        (),
        hashlib.sha256(hpgl.read_bytes()).hexdigest(),
        None,
    )
    return hpgl, plan


def test_round_trip_is_strict_and_deterministic(tmp_path):
    hpgl, plan = current(tmp_path)
    path = default_resolved_pen_plan_path(hpgl)
    write_resolved_plot_pass(path, plan)
    first = path.read_bytes()
    assert load_resolved_plot_pass(path) == plan
    write_resolved_plot_pass(path, plan)
    assert first == path.read_bytes()
    assert validate_resolved_sidecar_for_hpgl(hpgl, path) == plan


def test_hash_and_pen_order_both_checked(tmp_path):
    hpgl, plan = current(tmp_path)
    path = default_resolved_pen_plan_path(hpgl)
    write_resolved_plot_pass(path, plan)
    hpgl.write_text("IN;SP3;PU0,0;PD1,1;PU;SP0;")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_resolved_sidecar_for_hpgl(hpgl, path)
    raw = resolved_payload(plan)
    raw["hpgl_sha256"] = hashlib.sha256(hpgl.read_bytes()).hexdigest()
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="pen order"):
        validate_resolved_sidecar_for_hpgl(hpgl, path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 1),
        ("schema_version", 2),
        ("schema_version", True),
        ("kind", "resolved-dpx3300-logical-pass"),
        ("pass_number", 0),
        ("pass_count", 0),
        ("source_manifest_hash", "bad"),
        ("source_svg_sha256", None),
        ("physical_slots", [8]),
        ("physical_slots", None),
        ("assignments", []),
        ("slots", [{"slot": 1}]),
        ("omitted_layers", ["orbit"]),
        ("pen_force", {}),
        ("unknown", 1),
    ],
)
def test_malformed_or_stale_resolved_payloads_fail(tmp_path, field, value):
    hpgl, plan = current(tmp_path)
    raw = resolved_payload(plan)
    raw[field] = value
    with pytest.raises(ValueError):
        parse_resolved(raw)


def test_authored_and_resolved_suffixes_remain_distinct_and_old_fallback_is_retired(tmp_path):
    svg = tmp_path / "drawing.svg"
    hpgl = tmp_path / "drawing.hpgl"
    authored = default_pen_plan_path(svg)
    resolved = default_resolved_pen_plan_path(hpgl)
    assert authored == tmp_path / "drawing.penplan.json"
    assert resolved == tmp_path / "drawing.resolved.penplan.json"
    authored.write_text(json.dumps({"schema_version": 1, "kind": "resolved-dpx3300-pen-plan"}))
    assert discover_resolved_pen_plan_path(hpgl) == resolved
    # A stale file at an authored path is found and rejected, not silently ignored.
    assert discover_pen_plan(svg) == authored
    from pen_plan_io import load_pen_plan

    with pytest.raises(ValueError, match="migrate"):
        load_pen_plan(authored)
    with pytest.raises(ValueError):
        validate_resolved_sidecar_for_hpgl(hpgl, resolved)


def test_missing_explicit_authored_file_fails(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        discover_pen_plan(tmp_path / "drawing.svg", tmp_path / "absent.json")
