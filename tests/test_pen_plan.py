import json
from pathlib import Path

import pytest

from pen_plan import (
    PenPlanError,
    format_pen_plan,
    inspect_logical_layers,
    load_pen_plan,
    remap_hpgl_pen_selections,
    resolve_pen_plan,
    write_resolved_pen_plan,
)


def write_svg(tmp_path: Path) -> Path:
    path = tmp_path / "drawing.svg"
    path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg">
<g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#111111">
  <g data-generation="0"></g>
</g>
<g id="pen-2" data-pen="2" data-generations="1" fill="none" stroke="#222222">
  <g data-generation="1"><path d="M0 0L1 1"/></g>
</g>
<g id="pen-4" data-pen="4" data-generations="2,3" fill="none" stroke="#444444">
  <g data-generation="2"><path d="M1 1L2 2"/></g>
  <g data-generation="3"><path d="M2 2L3 3"/></g>
</g>
</svg>""",
        encoding="utf-8",
    )
    return path


def test_inspect_logical_layers_distinguishes_empty_layer(tmp_path: Path):
    svg = write_svg(tmp_path)
    layers = inspect_logical_layers(svg)
    assert tuple(layer.logical_layer for layer in layers) == (1, 2, 4)
    assert tuple(layer.active for layer in layers) == (False, True, True)


def test_preserve_keeps_active_logical_slot_numbers(tmp_path: Path):
    plan = resolve_pen_plan(write_svg(tmp_path))
    assert plan.logical_pens == (2, 4)
    assert plan.physical_pens == (2, 4)
    assert plan.inactive_logical_pens == (1,)


def test_compact_uses_lowest_physical_slots(tmp_path: Path):
    plan = resolve_pen_plan(write_svg(tmp_path), cli_policy="compact")
    assert plan.logical_pens == (2, 4)
    assert plan.physical_pens == (1, 2)


def test_explicit_json_assigns_and_documents_slots(tmp_path: Path):
    svg = write_svg(tmp_path)
    plan_path = tmp_path / "drawing.penplan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy": "explicit",
                "assignments": [
                    {"logical_layer": 2, "physical_slot": 8},
                    {"logical_layer": 4, "physical_slot": 3},
                ],
                "slots": [
                    {"slot": 8, "tool": "Micron 01", "color": "black"},
                    {"slot": 3, "label": "red technical pen"},
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = resolve_pen_plan(svg)
    assert plan.physical_pens == (8, 3)
    assert plan.assignments[0].tool == "Micron 01"
    assert plan.assignments[1].label == "red technical pen"


def test_explicit_plan_must_cover_every_active_layer(tmp_path: Path):
    svg = write_svg(tmp_path)
    plan_path = tmp_path / "drawing.penplan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy": "explicit",
                "assignments": [{"logical_layer": 2, "physical_slot": 1}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PenPlanError, match="missing active logical layers: 4"):
        resolve_pen_plan(svg)


def test_duplicate_physical_slots_are_rejected(tmp_path: Path):
    path = tmp_path / "drawing.penplan.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy": "explicit",
                "assignments": [
                    {"logical_layer": 2, "physical_slot": 1},
                    {"logical_layer": 4, "physical_slot": 1},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PenPlanError, match="Duplicate physical_slot"):
        load_pen_plan(path)


def test_hpgl_remap_is_collision_safe(tmp_path: Path):
    svg = write_svg(tmp_path)
    pen_map = "2:4,4:2"
    plan = resolve_pen_plan(svg, cli_policy="explicit", cli_pen_map=pen_map)
    hpgl = tmp_path / "drawing.hpgl"
    hpgl.write_text("IN;SP2;PU0,0;PD1,1;SP4;PU2,2;PD3,3;SP0;", encoding="ascii")
    remap_hpgl_pen_selections(hpgl, plan)
    assert hpgl.read_text(encoding="ascii") == (
        "IN;SP4;PU0,0;PD1,1;SP2;PU2,2;PD3,3;SP0;"
    )


def test_resolved_sidecar_records_inactive_layers_and_physical_slots(tmp_path: Path):
    plan = resolve_pen_plan(write_svg(tmp_path), cli_policy="compact")
    out = tmp_path / "drawing.penplan.json"
    write_resolved_pen_plan(out, plan)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["policy"] == "compact"
    assert payload["logical_layers"][0]["active"] is False
    assert [item["physical_slot"] for item in payload["assignments"]] == [1, 2]
    assert payload["unused_physical_slots"] == [3, 4, 5, 6, 7, 8]


def test_human_preflight_shows_mapping_and_undocumented_tools(tmp_path: Path):
    plan = resolve_pen_plan(write_svg(tmp_path), cli_policy="compact")
    text = format_pen_plan(plan)
    assert "2" in text
    assert "DPX slot" in text
    assert "<not documented>" in text
    assert "Inactive logical layers" in text


def test_resolved_sidecar_can_be_verified_against_hpgl(tmp_path: Path):
    plan = resolve_pen_plan(write_svg(tmp_path), cli_policy="compact")
    sidecar = tmp_path / "drawing.penplan.json"
    write_resolved_pen_plan(sidecar, plan)
    hpgl = tmp_path / "drawing.hpgl"
    hpgl.write_text("IN;SP1;PU0,0;PD1,1;SP2;PU2,2;PD3,3;SP0;", encoding="ascii")

    from pen_plan import validate_resolved_pen_plan_for_hpgl

    loaded = validate_resolved_pen_plan_for_hpgl(hpgl)
    assert loaded.physical_pens == (1, 2)


def test_resolved_sidecar_rejects_hpgl_pen_order_mismatch(tmp_path: Path):
    plan = resolve_pen_plan(write_svg(tmp_path), cli_policy="compact")
    sidecar = tmp_path / "drawing.penplan.json"
    write_resolved_pen_plan(sidecar, plan)
    hpgl = tmp_path / "drawing.hpgl"
    hpgl.write_text("IN;SP2;PU0,0;PD1,1;SP1;PU2,2;PD3,3;SP0;", encoding="ascii")

    from pen_plan import validate_resolved_pen_plan_for_hpgl

    with pytest.raises(PenPlanError, match="does not match"):
        validate_resolved_pen_plan_for_hpgl(hpgl)
