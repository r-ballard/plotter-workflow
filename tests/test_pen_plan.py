import json
from pathlib import Path

import pytest

from logical_layer_contract import (
    InputMode,
    LogicalLayerContract,
    LogicalLayerMetadata,
    inspect_svg_contract,
)
from pen_plan import (
    LogicalAssignment,
    LogicalPenPlanSpec,
    PassSpec,
    PenPlanError,
    PenPlanSpec,
    ResolvedPlotPass,
    format_pen_plan,
    inspect_logical_layers,
    load_pen_plan,
    remap_hpgl_pen_selections,
    resolve_logical_pen_plan,
    resolve_pen_plan,
    write_resolved_pen_plan,
)

ROOT = Path(__file__).resolve().parents[1]
LOGICAL_MULTIPASS_EXAMPLE = (
    ROOT / "examples" / "penplans" / "logical-multipass.penplan.json"
)
PEN_PLAN_SCHEMA = ROOT / "penplan.schema.json"


def write_pen_plan(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "test.penplan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def valid_v2_plan() -> dict[str, object]:
    return {
        "schema_version": 2,
        "passes": [
            {
                "id": "pass-1",
                "assignments": [
                    {"layer_ids": ["orbit"], "physical_slot": 1},
                ],
            }
        ],
        "omitted_layers": [],
        "repeated_layers": [],
    }


MANIFEST_HASH = "a" * 64


def logical_catalog(count: int) -> tuple[LogicalLayerMetadata, ...]:
    return tuple(
        LogicalLayerMetadata(
            id=f"layer-{index}", ordinal=index, label=f"Layer {index}"
        )
        for index in range(1, count + 1)
    )


def logical_spec(
    passes: tuple[PassSpec, ...],
    *,
    omitted_layers: tuple[str, ...] = (),
    repeated_layers: tuple[str, ...] = (),
) -> LogicalPenPlanSpec:
    return LogicalPenPlanSpec(
        schema_version=2,
        passes=passes,
        omitted_layers=omitted_layers,
        repeated_layers=repeated_layers,
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


def test_v1_still_loads_into_existing_numeric_model(tmp_path: Path):
    path = write_pen_plan(
        tmp_path,
        {
            "schema_version": 1,
            "policy": "explicit",
            "assignments": [
                {"logical_layer": 2, "physical_slot": 8},
                {"logical_layer": 4, "physical_slot": 3},
            ],
            "slots": [
                {"slot": 8, "tool": "Micron 01"},
                {"slot": 3, "label": "red technical pen"},
            ],
            "notes": "Keep this legacy plan numeric.",
        },
    )

    plan = load_pen_plan(path)

    assert isinstance(plan, PenPlanSpec)
    assert plan.policy == "explicit"
    assert tuple(item.logical_layer for item in plan.assignments) == (2, 4)
    assert tuple(item.physical_slot for item in plan.assignments) == (8, 3)
    assert tuple(item.slot for item in plan.slots) == (3, 8)
    assert plan.notes == "Keep this legacy plan numeric."


def test_v2_supports_string_ids_merge_and_multiple_passes():
    plan = load_pen_plan(LOGICAL_MULTIPASS_EXAMPLE)

    assert isinstance(plan, LogicalPenPlanSpec)
    assert [plot_pass.id for plot_pass in plan.passes] == ["warm", "cool"]
    assert plan.passes[0].assignments[0].layer_ids == ("orbit", "accent")
    assert plan.passes[0].assignments[0].physical_slot == 1
    assert plan.omitted_layers == ("registration-guide",)
    assert plan.repeated_layers == ("orbit",)


def test_v2_preserves_pass_assignment_and_layer_order(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"] = [
        {
            "id": "second-on-paper",
            "assignments": [
                {"layer_ids": ["zeta", "alpha"], "physical_slot": 7},
                {"layer_ids": ["middle"], "physical_slot": 2},
            ],
        },
        {
            "id": "first-by-name",
            "assignments": [
                {"layer_ids": ["beta"], "physical_slot": 4},
            ],
        },
    ]
    plan = load_pen_plan(write_pen_plan(tmp_path, payload))

    assert isinstance(plan, LogicalPenPlanSpec)
    assert tuple(plot_pass.id for plot_pass in plan.passes) == (
        "second-on-paper",
        "first-by-name",
    )
    assert tuple(
        assignment.physical_slot for assignment in plan.passes[0].assignments
    ) == (7, 2)
    assert plan.passes[0].assignments[0].layer_ids == ("zeta", "alpha")


def test_v2_rejects_duplicate_pass_ids(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"] = [payload["passes"][0], payload["passes"][0]]

    with pytest.raises(PenPlanError, match=r"passes\[1\]\.id.*duplicate"):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_rejects_duplicate_slots_within_a_pass(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"][0]["assignments"].append(
        {"layer_ids": ["accent"], "physical_slot": 1}
    )

    with pytest.raises(
        PenPlanError,
        match=r"passes\[0\]\.assignments\[1\]\.physical_slot.*duplicate",
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_rejects_more_than_eight_assignments_in_a_pass(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"][0]["assignments"] = [
        {"layer_ids": [f"layer-{slot}"], "physical_slot": slot}
        for slot in range(1, 10)
    ]

    with pytest.raises(
        PenPlanError, match=r"passes\[0\]\.assignments.*at most 8"
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


@pytest.mark.parametrize("slot", [0, 9, True, 1.0, "1"])
def test_v2_rejects_invalid_physical_slots(tmp_path: Path, slot: object):
    payload = valid_v2_plan()
    payload["passes"][0]["assignments"][0]["physical_slot"] = slot

    with pytest.raises(
        PenPlanError,
        match=r"passes\[0\]\.assignments\[0\]\.physical_slot",
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_rejects_duplicate_ids_inside_a_merge(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"][0]["assignments"][0]["layer_ids"] = ["orbit", "orbit"]

    with pytest.raises(
        PenPlanError,
        match=r"passes\[0\]\.assignments\[0\]\.layer_ids\[1\].*duplicate",
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_rejects_a_layer_used_twice_in_one_pass(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"][0]["assignments"].append(
        {"layer_ids": ["orbit"], "physical_slot": 2}
    )

    with pytest.raises(
        PenPlanError,
        match=r"passes\[0\]\.assignments\[1\]\.layer_ids\[0\].*already assigned",
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_requires_cross_pass_repetition_to_be_declared(tmp_path: Path):
    payload = valid_v2_plan()
    payload["passes"].append(
        {
            "id": "pass-2",
            "assignments": [{"layer_ids": ["orbit"], "physical_slot": 2}],
        }
    )

    with pytest.raises(
        PenPlanError,
        match=r"passes\[1\]\.assignments\[0\]\.layer_ids\[0\].*repeated_layers",
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_rejects_declared_repetition_that_does_not_repeat(tmp_path: Path):
    payload = valid_v2_plan()
    payload["repeated_layers"] = ["orbit"]

    with pytest.raises(
        PenPlanError, match=r"repeated_layers\[0\].*does not repeat"
    ):
        load_pen_plan(write_pen_plan(tmp_path, payload))


@pytest.mark.parametrize("conflict_field", ["assigned", "repeated"])
def test_v2_rejects_omitted_layer_conflicts(
    tmp_path: Path, conflict_field: str
):
    payload = valid_v2_plan()
    payload["omitted_layers"] = ["orbit"]
    if conflict_field == "repeated":
        payload["passes"].append(
            {
                "id": "pass-2",
                "assignments": [{"layer_ids": ["orbit"], "physical_slot": 2}],
            }
        )
        payload["repeated_layers"] = ["orbit"]

    with pytest.raises(PenPlanError, match=r"omitted_layers\[0\].*orbit"):
        load_pen_plan(write_pen_plan(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("omitted_layers", ["guide", "guide"], r"omitted_layers\[1\].*duplicate"),
        ("omitted_layers", [""], r"omitted_layers\[0\]"),
        ("omitted_layers", [1], r"omitted_layers\[0\]"),
        ("repeated_layers", ["orbit", "orbit"], r"repeated_layers\[1\].*duplicate"),
        ("repeated_layers", ["  "], r"repeated_layers\[0\]"),
        ("repeated_layers", [False], r"repeated_layers\[0\]"),
    ],
)
def test_v2_rejects_duplicate_or_malformed_accounting_ids(
    tmp_path: Path, field: str, value: list[object], message: str
):
    payload = valid_v2_plan()
    payload[field] = value

    with pytest.raises(PenPlanError, match=message):
        load_pen_plan(write_pen_plan(tmp_path, payload))


@pytest.mark.parametrize(
    ("location", "message"),
    [
        ("top", r"unknown top-level field.*surprise"),
        ("pass", r"passes\[0\].*unknown field.*surprise"),
        ("assignment", r"passes\[0\]\.assignments\[0\].*unknown field.*surprise"),
    ],
)
def test_v2_rejects_unknown_fields(
    tmp_path: Path, location: str, message: str
):
    payload = valid_v2_plan()
    if location == "top":
        payload["surprise"] = True
    elif location == "pass":
        payload["passes"][0]["surprise"] = True
    else:
        payload["passes"][0]["assignments"][0]["surprise"] = True

    with pytest.raises(PenPlanError, match=message):
        load_pen_plan(write_pen_plan(tmp_path, payload))


@pytest.mark.parametrize("version", [None, 0, 3, True, "2"])
def test_pen_plan_requires_an_explicit_supported_schema_version(
    tmp_path: Path, version: object
):
    payload = valid_v2_plan()
    if version is None:
        del payload["schema_version"]
    else:
        payload["schema_version"] = version

    with pytest.raises(PenPlanError, match="schema_version"):
        load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_requires_explicit_omission_and_repetition_arrays(tmp_path: Path):
    for field in ("omitted_layers", "repeated_layers"):
        payload = valid_v2_plan()
        del payload[field]
        with pytest.raises(PenPlanError, match=field):
            load_pen_plan(write_pen_plan(tmp_path, payload))


def test_v2_rejects_malformed_pass_and_assignment_fields(tmp_path: Path):
    mutations = [
        ("passes", [], "passes"),
        ("pass id", " ", r"passes\[0\]\.id"),
        ("assignments", [], r"passes\[0\]\.assignments"),
        ("layer_ids", [], r"passes\[0\]\.assignments\[0\]\.layer_ids"),
        ("layer id", "", r"layer_ids\[0\]"),
    ]
    for mutation, value, message in mutations:
        payload = valid_v2_plan()
        if mutation == "passes":
            payload["passes"] = value
        elif mutation == "pass id":
            payload["passes"][0]["id"] = value
        elif mutation == "assignments":
            payload["passes"][0]["assignments"] = value
        elif mutation == "layer_ids":
            payload["passes"][0]["assignments"][0]["layer_ids"] = value
        else:
            payload["passes"][0]["assignments"][0]["layer_ids"][0] = value

        with pytest.raises(PenPlanError, match=message):
            load_pen_plan(write_pen_plan(tmp_path, payload))


def test_legacy_svg_resolver_does_not_interpret_v2_plan(tmp_path: Path):
    svg = write_svg(tmp_path)
    path = svg.with_suffix(".penplan.json")
    path.write_text(json.dumps(valid_v2_plan()), encoding="utf-8")

    with pytest.raises(PenPlanError, match="schema_version=2.*logical-layer"):
        resolve_pen_plan(svg)


def test_pen_plan_schema_declares_strict_v1_v2_discriminated_shapes():
    schema = json.loads(PEN_PLAN_SCHEMA.read_text(encoding="utf-8"))

    assert schema["oneOf"] == [
        {"$ref": "#/$defs/v1"},
        {"$ref": "#/$defs/v2"},
    ]
    v1 = schema["$defs"]["v1"]
    v2 = schema["$defs"]["v2"]
    assert v1["additionalProperties"] is False
    assert v1["properties"]["schema_version"] == {"const": 1}
    assert v2["additionalProperties"] is False
    assert v2["required"] == [
        "schema_version",
        "passes",
        "omitted_layers",
        "repeated_layers",
    ]
    assert v2["properties"]["schema_version"] == {"const": 2}
    passes = v2["properties"]["passes"]
    assert passes["minItems"] == 1
    pass_schema = passes["items"]
    assert pass_schema["additionalProperties"] is False
    assignments = pass_schema["properties"]["assignments"]
    assert assignments["minItems"] == 1
    assert assignments["maxItems"] == 8
    assignment = assignments["items"]
    assert assignment["additionalProperties"] is False
    assert assignment["properties"]["layer_ids"]["minItems"] == 1
    assert assignment["properties"]["layer_ids"]["uniqueItems"] is True
    assert assignment["properties"]["physical_slot"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 8,
    }
    assert v2["properties"]["omitted_layers"]["uniqueItems"] is True
    assert v2["properties"]["repeated_layers"]["uniqueItems"] is True


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


@pytest.mark.parametrize("count", [1, 8])
def test_logical_resolver_preserves_catalog_order(count: int):
    resolved = resolve_logical_pen_plan(
        logical_catalog(count), None, source_manifest_hash=MANIFEST_HASH
    )

    assert len(resolved) == 1
    assert isinstance(resolved[0], ResolvedPlotPass)
    assert resolved[0].id == "preserve"
    assert [assignment.layer_ids for assignment in resolved[0].assignments] == [
        (f"layer-{index}",) for index in range(1, count + 1)
    ]
    assert [assignment.physical_slot for assignment in resolved[0].assignments] == list(
        range(1, count + 1)
    )
    assert resolved[0].source_manifest_hash == MANIFEST_HASH


def test_logical_resolver_accepts_sparse_active_contract_from_inspection(
    tmp_path: Path,
):
    catalog = tuple(
        LogicalLayerMetadata(
            id=f"layer-{index}", ordinal=index, label=f"Layer {index}"
        )
        for index in range(1, 5)
    )
    svg = tmp_path / "imposed.svg"
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg"
  data-viz-layer-contract="viz-logical-layers/v1">
  <g data-viz-layer-id="layer-1" data-viz-layer-ordinal="1"
    data-viz-layer-label="Layer 1"><path d="M0 0L1 1" /></g>
  <g data-viz-layer-id="layer-3" data-viz-layer-ordinal="3"
    data-viz-layer-label="Layer 3"><path d="M1 1L2 2" /></g>
  <g data-viz-layer-id="layer-4" data-viz-layer-ordinal="4"
    data-viz-layer-label="Layer 4"><path d="M2 2L3 3" /></g>
</svg>""",
        encoding="utf-8",
    )
    active_contract = inspect_svg_contract(svg, catalog=catalog)

    resolved = resolve_logical_pen_plan(
        active_contract, None, source_manifest_hash=MANIFEST_HASH
    )

    assert [assignment.layer_ids for assignment in resolved[0].assignments] == [
        ("layer-1",),
        ("layer-3",),
        ("layer-4",),
    ]
    assert [assignment.physical_slot for assignment in resolved[0].assignments] == [
        1,
        2,
        3,
    ]


def test_logical_resolver_requires_explicit_resolution_over_eight_layers():
    with pytest.raises(PenPlanError, match="explicit merge or multiple passes"):
        resolve_logical_pen_plan(
            logical_catalog(9), None, source_manifest_hash=MANIFEST_HASH
        )


def test_logical_resolver_accounts_for_nine_layers_in_ordered_passes():
    spec = logical_spec(
        (
            PassSpec(
                "pass-1",
                tuple(
                    LogicalAssignment((f"layer-{index}",), index)
                    for index in range(1, 9)
                ),
            ),
            PassSpec(
                "pass-2", (LogicalAssignment(("layer-9",), 1),)
            ),
        )
    )

    resolved = resolve_logical_pen_plan(
        logical_catalog(9), spec, source_manifest_hash=MANIFEST_HASH
    )

    assert [plot_pass.id for plot_pass in resolved] == ["pass-1", "pass-2"]
    assert tuple(
        layer_id
        for plot_pass in resolved
        for assignment in plot_pass.assignments
        for layer_id in assignment.layer_ids
    ) == tuple(f"layer-{index}" for index in range(1, 10))


def test_logical_resolver_normalizes_merged_layers_to_catalog_order():
    spec = logical_spec(
        (PassSpec("merged", (LogicalAssignment(("layer-3", "layer-1"), 2),)),),
        omitted_layers=("layer-2",),
    )

    resolved = resolve_logical_pen_plan(
        logical_catalog(3), spec, source_manifest_hash=MANIFEST_HASH
    )

    assert resolved[0].assignments[0].layer_ids == ("layer-1", "layer-3")


def test_logical_resolver_preserves_explicit_omissions():
    spec = logical_spec(
        (PassSpec("selected", (LogicalAssignment(("layer-1",), 1),)),),
        omitted_layers=("layer-2",),
    )

    resolved = resolve_logical_pen_plan(
        logical_catalog(2), spec, source_manifest_hash=MANIFEST_HASH
    )

    assert resolved[0].omitted_layers == ("layer-2",)


def test_logical_resolver_allows_declared_repetition_across_passes():
    spec = logical_spec(
        (
            PassSpec("first", (LogicalAssignment(("layer-1",), 1),)),
            PassSpec("second", (LogicalAssignment(("layer-1",), 2),)),
        ),
        repeated_layers=("layer-1",),
    )

    resolved = resolve_logical_pen_plan(
        logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
    )

    assert [assignment.layer_ids for plot_pass in resolved for assignment in plot_pass.assignments] == [
        ("layer-1",),
        ("layer-1",),
    ]


def test_logical_resolver_rejects_undeclared_repetition():
    spec = logical_spec(
        (
            PassSpec("first", (LogicalAssignment(("layer-1",), 1),)),
            PassSpec("second", (LogicalAssignment(("layer-1",), 2),)),
        )
    )

    with pytest.raises(PenPlanError, match="repeated_layers"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


def test_logical_resolver_rejects_falsely_declared_repetition():
    spec = logical_spec(
        (PassSpec("only", (LogicalAssignment(("layer-1",), 1),)),),
        repeated_layers=("layer-1",),
    )

    with pytest.raises(PenPlanError, match="does not repeat"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


@pytest.mark.parametrize("field", ["assigned", "omitted", "repeated"])
def test_logical_resolver_rejects_unknown_catalog_ids(field: str):
    if field == "assigned":
        spec = logical_spec(
            (PassSpec("bad", (LogicalAssignment(("missing",), 1),)),)
        )
    elif field == "omitted":
        spec = logical_spec(
            (PassSpec("good", (LogicalAssignment(("layer-1",), 1),)),),
            omitted_layers=("missing",),
        )
    else:
        spec = logical_spec(
            (
                PassSpec("first", (LogicalAssignment(("layer-1",), 1),)),
                PassSpec("second", (LogicalAssignment(("layer-1",), 2),)),
            ),
            repeated_layers=("missing",),
        )

    with pytest.raises(PenPlanError, match="missing"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


def test_logical_resolver_rejects_unaccounted_catalog_layers():
    spec = logical_spec(
        (PassSpec("partial", (LogicalAssignment(("layer-1",), 1),)),)
    )

    with pytest.raises(PenPlanError, match="layer-2"):
        resolve_logical_pen_plan(
            logical_catalog(2), spec, source_manifest_hash=MANIFEST_HASH
        )


def test_logical_resolver_defensively_rejects_duplicate_slots_and_overflow():
    duplicate_slots = logical_spec(
        (
            PassSpec(
                "bad-slots",
                (
                    LogicalAssignment(("layer-1",), 1),
                    LogicalAssignment(("layer-2",), 1),
                ),
            ),
        )
    )
    overflow = logical_spec(
        (
            PassSpec(
                "too-many",
                tuple(
                    LogicalAssignment((f"layer-{index}",), index)
                    for index in range(1, 10)
                ),
            ),
        )
    )

    with pytest.raises(PenPlanError, match="duplicate physical slot"):
        resolve_logical_pen_plan(
            logical_catalog(2), duplicate_slots, source_manifest_hash=MANIFEST_HASH
        )
    with pytest.raises(PenPlanError, match="at most 8"):
        resolve_logical_pen_plan(
            logical_catalog(9), overflow, source_manifest_hash=MANIFEST_HASH
        )


def test_logical_resolver_defensively_rejects_programmatic_spec_without_passes():
    spec = logical_spec((), omitted_layers=("layer-1",))

    with pytest.raises(PenPlanError, match="passes.*at least one pass"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


def test_logical_resolver_defensively_rejects_programmatic_empty_pass():
    spec = logical_spec(
        (PassSpec("empty", ()),), omitted_layers=("layer-1",)
    )

    with pytest.raises(PenPlanError, match="assignments.*at least one assignment"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


@pytest.mark.parametrize(
    "assignments",
    [
        (LogicalAssignment(("layer-1", "layer-1"), 1),),
        (
            LogicalAssignment(("layer-1",), 1),
            LogicalAssignment(("layer-1",), 2),
        ),
    ],
)
def test_logical_resolver_defensively_rejects_duplicate_layer_ids(
    assignments: tuple[LogicalAssignment, ...],
):
    spec = logical_spec((PassSpec("duplicate", assignments),))

    with pytest.raises(PenPlanError, match="logical layer"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


@pytest.mark.parametrize("physical_slot", [0, 9, True])
def test_logical_resolver_defensively_rejects_invalid_slots(
    physical_slot: object,
):
    spec = logical_spec(
        (
            PassSpec(
                "bad-slot",
                (LogicalAssignment(("layer-1",), physical_slot),),  # type: ignore[arg-type]
            ),
        )
    )

    with pytest.raises(PenPlanError, match="integer from 1 through 8"):
        resolve_logical_pen_plan(
            logical_catalog(1), spec, source_manifest_hash=MANIFEST_HASH
        )


@pytest.mark.parametrize("source_hash", [None, "A" * 64, "not-a-hash", "0" * 63])
def test_logical_resolver_requires_exact_manifest_hash(source_hash: str | None):
    with pytest.raises(PenPlanError, match="source manifest hash"):
        resolve_logical_pen_plan(
            logical_catalog(1), None, source_manifest_hash=source_hash
        )


def test_logical_resolver_rejects_non_neutral_contract_and_empty_catalog():
    legacy = LogicalLayerContract(mode=InputMode.LEGACY)

    with pytest.raises(PenPlanError, match="neutral"):
        resolve_logical_pen_plan(legacy, None, source_manifest_hash=MANIFEST_HASH)
    with pytest.raises(PenPlanError, match="no active"):
        resolve_logical_pen_plan((), None, source_manifest_hash=MANIFEST_HASH)


def test_logical_resolver_is_deterministic_for_repeated_calls():
    resolved_a = resolve_logical_pen_plan(
        logical_catalog(2), None, source_manifest_hash=MANIFEST_HASH
    )
    resolved_b = resolve_logical_pen_plan(
        logical_catalog(2), None, source_manifest_hash=MANIFEST_HASH
    )

    assert resolved_a == resolved_b
