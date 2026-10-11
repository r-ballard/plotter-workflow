"""Schema-3 physical plans: strict parsing, complete accounting and source adapters."""

import json
from pathlib import Path

import pytest

from pen_plan import inspect_plan_layers, remap_hpgl_pen_selections, source_plan
from pen_plan_io import parse_pen_plan
from pen_plan_models import Assignment, LayerInfo, PassSpec, PenPlanError, PenPlanSpec
from pen_plan_resolution import resolve_plot_passes

ROOT = Path(__file__).resolve().parents[1]


def write_svg(tmp_path):
    p = tmp_path / "drawing.svg"
    p.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        + "".join(
            f'<g id="pen-{n}" data-pen="{n}" data-generations="0" fill="none" stroke="black">'
            '<g data-generation="0">' + ("" if n == 1 else '<path d="M0 0L1 1"/>') + "</g></g>"
            for n in (1, 2, 4)
        )
        + "</svg>"
    )
    return p


def layers(n):
    return tuple(LayerInfo(f"layer-{i}", True, i) for i in range(1, n + 1))


def explicit(passes, **kwargs):
    return PenPlanSpec("explicit", tuple(passes), **kwargs)


def test_inspection_keeps_empty_layers_and_source_identity(tmp_path):
    result = inspect_plan_layers(write_svg(tmp_path))
    assert [x.id for x in result] == ["pen-1", "pen-2", "pen-4"]
    assert [x.active for x in result] == [False, True, True]


@pytest.mark.parametrize("policy,expected", [("preserve", (2, 4)), ("compact", (1, 2))])
def test_source_policy_uses_only_active_layers(tmp_path, policy, expected):
    spec, passes = source_plan(write_svg(tmp_path), cli_policy=policy)
    assert tuple(a.physical_slot for a in passes[0].assignments) == expected
    assert tuple(a.layer_ids for a in passes[0].assignments) == (("pen-2",), ("pen-4",))


def test_authored_explicit_mapping_preserves_tool_metadata(tmp_path):
    p = write_svg(tmp_path)
    p.with_suffix(".penplan.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "policy": "explicit",
                "passes": [
                    {
                        "id": "plot",
                        "assignments": [
                            {"layer_ids": ["pen-2"], "physical_slot": 8},
                            {"layer_ids": ["pen-4"], "physical_slot": 3},
                        ],
                    }
                ],
                "slots": [
                    {"slot": 8, "tool": "Micron 01"},
                    {"slot": 3, "label": "red technical pen"},
                ],
            }
        )
    )
    spec, passes = source_plan(p)
    assert tuple(a.physical_slot for a in passes[0].assignments) == (8, 3)
    assert spec.slots[0].label == "red technical pen" and spec.slots[1].tool == "Micron 01"
    with pytest.raises(PenPlanError, match="conflicts"):
        source_plan(p, cli_policy="compact")


@pytest.mark.parametrize("count", [1, 2, 8])
def test_auto_resolution_preserves_catalog_order(count):
    result = resolve_plot_passes(layers(count), PenPlanSpec("compact"))
    assert [a.layer_ids for a in result[0].assignments] == [
        (f"layer-{i}",) for i in range(1, count + 1)
    ]
    assert [a.physical_slot for a in result[0].assignments] == list(range(1, count + 1))


def test_over_eight_layers_require_explicit_merge_or_multiple_passes():
    with pytest.raises(PenPlanError, match="eight"):
        resolve_plot_passes(layers(9), PenPlanSpec("compact"))
    spec = explicit(
        (
            PassSpec("first", tuple(Assignment((f"layer-{i}",), i) for i in range(1, 9))),
            PassSpec("second", (Assignment(("layer-9",), 3),)),
        )
    )
    result = resolve_plot_passes(layers(9), spec)
    assert len(result) == 2 and result[1].assignments[0].physical_slot == 3


def test_merge_omission_repetition_and_determinism():
    spec = explicit(
        (
            PassSpec("first", (Assignment(("layer-3", "layer-1"), 7),)),
            PassSpec("second", (Assignment(("layer-1", "layer-4"), 2),)),
        ),
        omitted_layers=("layer-2",),
        repeated_layers=("layer-1",),
    )
    result = resolve_plot_passes(layers(4), spec)
    assert result[0].assignments[0].layer_ids == ("layer-1", "layer-3")
    assert result == resolve_plot_passes(layers(4), spec)


@pytest.mark.parametrize(
    "spec",
    [
        explicit((PassSpec("a", (Assignment(("layer-1",), 1),)),)),
        explicit((PassSpec("a", (Assignment(("missing",), 1),)),)),
        explicit((PassSpec("a", (Assignment(("layer-1",), 1), Assignment(("layer-2",), 1))),)),
        explicit(
            (PassSpec("a", (Assignment(("layer-1", "layer-1"), 1), Assignment(("layer-2",), 2))),)
        ),
        explicit(
            (
                PassSpec("a", (Assignment(("layer-1",), 1),)),
                PassSpec("b", (Assignment(("layer-1", "layer-2"), 2),)),
            )
        ),
        explicit(
            (PassSpec("a", (Assignment(("layer-1", "layer-2"), 1),)),), repeated_layers=("layer-1",)
        ),
        explicit(
            (PassSpec("a", (Assignment(("layer-1", "layer-2"), 1),)),), omitted_layers=("layer-1",)
        ),
        PenPlanSpec("explicit"),
        explicit((PassSpec("a", ()),)),
    ],
)
def test_resolver_rejects_incomplete_ambiguous_and_false_accounting(spec):
    with pytest.raises(PenPlanError):
        resolve_plot_passes(layers(2), spec)


@pytest.mark.parametrize("slot", [True, False, 0, 9, 1.0, "1", None])
def test_programmatic_invalid_slots_are_not_coerced(slot):
    with pytest.raises(PenPlanError):
        resolve_plot_passes(
            layers(1), explicit((PassSpec("a", (Assignment(("layer-1",), slot),)),))
        )


@pytest.mark.parametrize(
    "damage",
    [
        {"policy": "unknown"},
        {"schema_version": 1},
        {"schema_version": 2},
        {"schema_version": True},
        {"schema_version": 3.0},
        {"extra": 1},
        {"passes": []},
        {"slots": None},
        {"slots": [{"slot": True}]},
        {"omitted_layers": None},
        {"omitted_layers": ["a", "a"]},
        {"repeated_layers": ["a"]},
        {"notes": ""},
    ],
)
def test_authored_schema_is_strict(damage):
    with pytest.raises(PenPlanError):
        parse_pen_plan({"schema_version": 3, "policy": "compact", **damage})


@pytest.mark.parametrize(
    "damage",
    [
        {"id": ""},
        {"id": True},
        {"assignments": []},
        {"assignments": [{"layer_ids": ["a", "a"], "physical_slot": 1}]},
        {"assignments": [{"layer_ids": [], "physical_slot": 1}]},
        {"assignments": [{"layer_ids": ["a"], "physical_slot": True}]},
        {"assignments": [{"layer_ids": ["a"], "physical_slot": 1, "unknown": 0}]},
        {"unknown": 0},
    ],
)
def test_explicit_pass_fields_are_strict(damage):
    entry = {"id": "a", "assignments": [{"layer_ids": ["a"], "physical_slot": 1}], **damage}
    with pytest.raises(PenPlanError):
        parse_pen_plan({"schema_version": 3, "policy": "explicit", "passes": [entry]})


def test_duplicate_pass_id_and_slot_metadata_rejected():
    entry = {"id": "a", "assignments": [{"layer_ids": ["a"], "physical_slot": 1}]}
    with pytest.raises(PenPlanError, match="duplicate"):
        parse_pen_plan({"schema_version": 3, "policy": "explicit", "passes": [entry, entry]})
    with pytest.raises(PenPlanError, match="duplicate"):
        parse_pen_plan(
            {"schema_version": 3, "policy": "compact", "slots": [{"slot": 1}, {"slot": 1}]}
        )


@pytest.mark.parametrize("mapping", [{1: 2, 2: 1}, {1: 8, 2: 3}])
def test_hpgl_remapping_is_collision_safe_and_label_aware(tmp_path, mapping):
    path = tmp_path / "plot.hpgl"
    path.write_text("IN;DT$;LBSP1;SP2;$SP1;PU0,0;PD1,1;PU;SP2;PD2,2;PU;SP0;")
    remap_hpgl_pen_selections(path, mapping)
    out = path.read_text()
    assert "LBSP1;SP2;$" in out
    assert f"$SP{mapping[1]};" in out and f"PU;SP{mapping[2]};" in out


def test_formal_schema_has_only_version3():
    schema = json.loads((ROOT / "penplan.schema.json").read_text())
    assert schema["properties"]["schema_version"] == {"const": 3}
    assert schema["additionalProperties"] is False
    assert {"policy", "schema_version"} <= set(schema["required"])
