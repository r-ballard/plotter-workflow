import math
from dataclasses import FrozenInstanceError

import pytest
from imposition.sheet_packing.budget import PackingBudget
from imposition.sheet_packing.geometry import back_matrix, effective_area, front_matrix, transform
from imposition.sheet_packing.model import ObjectFootprint, PolygonRegion, RectMM, SheetArea


def sheet(**updates):
    return SheetArea(
        **(
            dict(
                width_mm=500,
                height_mm=250,
                usable_front=RectMM(0, 0, 500, 250),
                usable_back=None,
                margins=(0, 0, 0, 0),
                faces="both",
                flip="left-right",
            )
            | updates
        )
    )


def test_native_negative_bounds_retain_trim_datum():
    f = ObjectFootprint("x", (), RectMM(-3, -5, 20, 10), (0, 90))
    assert front_matrix(f, 0, (10, 20)) == (1, 0, 0, 1, 13, 25)
    assert front_matrix(f, 90, (10, 20)) == (0, 1, -1, 0, 15, 23)


@pytest.mark.parametrize(
    "axis,want",
    [
        ("left-right", (1, 0, 0, 1, 73.6, 30)),
        ("top-bottom", (-1, 0, 0, -1, 426.4, 220)),
    ],
)
def test_back_correspondence_recovers_existing_jcard(axis, want):
    assert back_matrix(
        (1, 0, 0, 1, 20, 30), (-1, 0, 0, 1, 406.4, 0), sheet(flip=axis)
    ) == pytest.approx(want)


@pytest.mark.parametrize("angle", [0, 90])
@pytest.mark.parametrize("axis", ["left-right", "top-bottom"])
def test_rotated_native_panel_corners_pair_without_scale(angle, axis):
    f = ObjectFootprint("card", (), RectMM(-3, -3, 26, 16), (0, 90))
    m = front_matrix(f, angle, (40, 50))
    back = back_matrix(m, (-1, 0, 0, 1, 20, 0), sheet(flip=axis))
    assert m[0] * m[3] - m[1] * m[2] == back[0] * back[3] - back[1] * back[2] == 1
    for x, y in ((0, 0), (20, 0), (20, 10), (0, 10)):
        px, py = transform(m, (x, y))
        expected = (500 - px, py) if axis == "left-right" else (px, 250 - py)
        assert transform(back, (20 - x, y)) == pytest.approx(expected)
    assert math.dist(transform(m, (0, 0)), transform(m, (20, 0))) == 20


@pytest.mark.parametrize(
    "axis,want",
    [
        ("left-right", RectMM(400, 20, 80, 100)),
        ("top-bottom", RectMM(20, 130, 80, 100)),
    ],
)
def test_paired_usable_intersection_is_in_front_datum(axis, want):
    assert (
        effective_area(
            sheet(usable_back=RectMM(20, 20, 80, 100), margins=(10, 10, 10, 10), flip=axis)
        )
        == want
    )


@pytest.mark.parametrize(
    "updates",
    [
        dict(usable_front=RectMM(-1, 0, 100, 100)),
        dict(usable_back=RectMM(450, 0, 100, 100)),
        dict(margins=(0, 250, 0, 250)),
        dict(usable_front=RectMM(0, 0, 10, 10), usable_back=RectMM(0, 0, 10, 10)),
    ],
)
def test_invalid_or_empty_drawable_area(updates):
    with pytest.raises(ValueError):
        effective_area(sheet(**updates))


def test_copied_irregular_outline_and_holes_do_not_shrink_bounds():
    points = [[0, 0], [20, 0], [20, 5], [5, 5], [5, 20], [0, 20]]
    region = PolygonRegion(points, [[[1, 1], [2, 1], [2, 2], [1, 2]]])
    f = ObjectFootprint("L", [region], RectMM(-3, -3, 26, 26), [90, 0])
    points[0][0] = 99
    assert region.outer[0] == (0, 0) and f.rotations == (0, 90)
    with pytest.raises(FrozenInstanceError):
        f.object_id = "other"
    with pytest.raises(ValueError):
        ObjectFootprint("bad", [region], RectMM(0, 0, 10, 10), (0,))


@pytest.mark.parametrize("value", [True, "1", None, float("nan"), float("inf"), 10**1000])
def test_bad_numbers_fail_before_geometry(value):
    with pytest.raises(ValueError):
        RectMM(0, 0, value, 10)


@pytest.mark.parametrize("rotations", [(), (True,), (45,), (0, 0), ("90",)])
def test_bad_rotation_policy(rotations):
    with pytest.raises(ValueError):
        ObjectFootprint("x", (), RectMM(0, 0, 20, 10), rotations)


def test_budget_rejects_before_mutation():
    b = PackingBudget(limits=dict(candidates=2))
    b.reserve("candidates", 2)
    with pytest.raises(ValueError, match="candidates"):
        b.reserve("candidates", 1)
    assert b.used["candidates"] == 2
    for count in (-1, True, 1.5):
        with pytest.raises(ValueError):
            b.reserve("candidates", count)


def test_front_area_and_rotation_reject_missing_or_boolean_values():
    with pytest.raises(ValueError):
        sheet(usable_front=None)
    f = ObjectFootprint("x", (), RectMM(0, 0, 10, 10), (0,))
    with pytest.raises(ValueError):
        front_matrix(f, False, (0, 0))
