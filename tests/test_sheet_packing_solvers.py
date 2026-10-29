from dataclasses import replace

import pytest
from imposition.sheet_packing.budget import PackingBudget
from imposition.sheet_packing.geometry import validate_placements
from imposition.sheet_packing.model import (
    ObjectFootprint,
    PackingInstance,
    PolygonRegion,
    RectMM,
    SheetArea,
)
from imposition.sheet_packing.solver import pack


def items(sizes, rotations=(0,)):
    return tuple(
        PackingInstance(
            chr(97 + i), ObjectFootprint(chr(97 + i), (), RectMM(0, 0, w, h), rotations)
        )
        for i, (w, h) in enumerate(sizes)
    )


def sheet(w=420, h=297, margin=3):
    return SheetArea(w, h, RectMM(0, 0, w, h), margins=(margin,) * 4)


def test_two_envelopes_fit_a3_without_rescaling():
    result = pack(items([(412.4, 107.6)] * 2), sheet(), gutter=4)
    assert result.strategy == "grid" and result.sheet_count == 1
    assert [p.front_matrix for p in result.placements] == [
        (1, 0, 0, 1, 3, 3),
        (1, 0, 0, 1, 3, 114.6),
    ]


def test_grid_overflow_and_input_order():
    source = items([(109.1875, 107.6)] * 7)
    result = pack(source, sheet(), gutter=4)
    assert result == pack(tuple(reversed(source)), sheet(), gutter=4)
    assert result.sheet_count == 2
    assert result.placements[2].occupied_bounds.x == 229.375
    assert result.placements[3].occupied_bounds.y == 114.6
    assert result.placements[6].sheet_index == 1
    assert result.placements[6].occupied_bounds.x == result.placements[6].occupied_bounds.y == 3


def test_mixed_free_rectangles_and_short_side_choice():
    result = pack(items([(60, 40), (40, 60), (40, 40)]), sheet(100, 100, 0))
    assert result.strategy == "maxrects" and result.sheet_count == 1
    assert [
        (p.instance_id, p.occupied_bounds.x, p.occupied_bounds.y) for p in result.placements
    ] == [("a", 0, 0), ("b", 60, 0), ("c", 0, 60)]


@pytest.mark.parametrize("strategy", ["grid", "maxrects", "auto"])
def test_rotation_and_no_trailing_gutter(strategy):
    result = pack(items([(60, 30)], (0, 90)), sheet(30, 60, 0), gutter=4, strategy=strategy)
    assert result.placements[0].rotation == 90 and result.sheet_count == 1
    with pytest.raises(ValueError, match="fit"):
        pack(items([(60, 30)]), sheet(30, 60, 0), strategy=strategy)


def test_mixed_requires_maxrects_and_ties_are_stable():
    source = items([(20, 10), (10, 20), (15, 15)], (0, 90))
    a = pack(source, sheet(60, 40, 0), gutter=2)
    assert a == pack(reversed(source), sheet(60, 40, 0), gutter=2)
    with pytest.raises(ValueError, match="grid"):
        pack(source, sheet(60, 40, 0), strategy="grid")
    square = pack(items([(10, 10)], (0, 90)), sheet(20, 20, 0))
    assert square.placements[0].rotation == 0


def test_irregular_negative_bound_is_conservative():
    f = ObjectFootprint(
        "L",
        (PolygonRegion(((0, 0), (20, 0), (20, 5), (5, 5), (5, 20), (0, 20))),),
        RectMM(-3, -3, 26, 26),
        (0, 90),
    )
    source = (PackingInstance("a", f), PackingInstance("b", f))
    result = pack(source, sheet(60, 26, 0), gutter=4, strategy="maxrects")
    assert result.sheet_count == 1
    assert result.placements[0].front_matrix[4:] == (3, 3)
    assert result.placements[1].occupied_bounds.x == 30


@pytest.mark.parametrize(
    "kind,limit", [("instances", 1), ("sheets", 0), ("candidates", 0), ("free_rectangles", 1)]
)
def test_limits_fail_instead_of_partial_results(kind, limit):
    with pytest.raises(ValueError, match=kind):
        pack(
            items([(20, 10), (10, 20)]),
            sheet(100, 100, 0),
            strategy="maxrects",
            budget=PackingBudget(limits={kind: limit}),
        )


def test_validator_rejects_bad_count_overlap_scale_and_sheet():
    source = items([(10, 10)] * 2)
    s = sheet(30, 20, 0)
    valid = pack(source, s)
    a, b = valid.placements
    bad = [
        replace(valid, placements=(a, a)),
        replace(
            valid,
            placements=(
                a,
                replace(b, occupied_bounds=a.occupied_bounds, front_matrix=a.front_matrix),
            ),
        ),
        replace(valid, placements=(replace(a, front_matrix=(2, 0, 0, 1, 0, 0)), b)),
        replace(valid, sheet_count=2),
    ]
    for result in bad:
        with pytest.raises(ValueError):
            validate_placements(source, result, s, 0)


@pytest.mark.parametrize("gutter", [-1, True, "1", float("inf")])
def test_invalid_gutter(gutter):
    with pytest.raises(ValueError):
        pack(items([(10, 10)]), sheet(), gutter=gutter)
