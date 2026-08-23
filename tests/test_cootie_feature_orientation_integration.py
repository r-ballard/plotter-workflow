from __future__ import annotations

import pytest

from imposition.model import IntrinsicCanvas
from imposition.objects.cootie_catcher import COOTIE_CATCHER

SQUARE = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
TRIANGLE = ((50.0, 0.0), (100.0, 100.0), (0.0, 100.0))

EXPECTED_FEATURE_ANCHORS = {
    **{
        f"outer-{index}": ("vertex:2", "vertex:3")
        for index in range(1, 5)
    },
    **{
        f"selector-{index}": (
            ("edge:2", "edge:0") if index % 2 else ("edge:0", "edge:1")
        )
        for index in range(1, 9)
    },
    **{
        f"reveal-{index}": (
            ("vertex:1", "edge:1") if index % 2 else ("vertex:2", "vertex:0")
        )
        for index in range(1, 9)
    },
}

EXPECTED_ROTATIONS = {
    "outer-1": 225.0,
    "outer-2": 315.0,
    "outer-3": 45.0,
    "outer-4": 135.0,
    "selector-1": 63.43494882292201,
    "selector-2": 296.565051177078,
    "selector-3": 153.43494882292202,
    "selector-4": 26.565051177077976,
    "selector-5": 243.43494882292202,
    "selector-6": 116.56505117707798,
    "selector-7": 333.434948822922,
    "selector-8": 206.56505117707798,
    "reveal-1": 236.30993247402023,
    "reveal-2": 123.69006752597974,
    "reveal-3": 326.30993247402023,
    "reveal-4": 213.69006752597974,
    "reveal-5": 56.30993247402023,
    "reveal-6": 303.69006752597977,
    "reveal-7": 146.30993247402023,
    "reveal-8": 33.69006752597977,
}


def _canvas(slot_id: str) -> IntrinsicCanvas:
    family = slot_id.rsplit("-", 1)[0]
    if family == "outer":
        return IntrinsicCanvas(
            version=1,
            shape="square",
            coordinate_system="svg-y-down",
            polygon=SQUARE,
            up_anchor="edge:0",
            up_vector=(0.0, -1.0),
        )
    return IntrinsicCanvas(
        version=1,
        shape="triangle",
        coordinate_system="svg-y-down",
        polygon=TRIANGLE,
        up_anchor="vertex:0",
        up_vector=(0.0, -1.0),
    )


def test_cootie_slots_expose_physically_annotated_feature_targets() -> None:
    for slot in COOTIE_CATCHER.slots:
        expected_top, expected_right = EXPECTED_FEATURE_ANCHORS[slot.slot_id]
        assert slot.target_orientation.top_feature_anchor == expected_top
        assert slot.target_orientation.right_feature_anchor == expected_right


def test_feature_orientation_resolves_all_twenty_desired_targets() -> None:
    for slot_id, expected_degrees in EXPECTED_ROTATIONS.items():
        resolved = COOTIE_CATCHER.resolve_orientation(
            slot_id,
            source_canvas=_canvas(slot_id),
            use_feature_orientation=True,
        )

        assert resolved.policy == "feature-frame"
        assert resolved.resolved_degrees == pytest.approx(expected_degrees)


def test_feature_orientation_is_opt_in_during_transition() -> None:
    resolved = COOTIE_CATCHER.resolve_orientation(
        "selector-3",
        source_canvas=_canvas("selector-3"),
    )

    assert resolved.policy == "intrinsic-up-vector"
    assert resolved.resolved_degrees == pytest.approx(90.0)


def test_explicit_override_precedes_feature_orientation() -> None:
    resolved = COOTIE_CATCHER.resolve_orientation(
        "reveal-1",
        source_canvas=_canvas("reveal-1"),
        override_degrees=17.5,
        use_feature_orientation=True,
    )

    assert resolved.policy == "explicit-override"
    assert resolved.resolved_degrees == pytest.approx(17.5)
