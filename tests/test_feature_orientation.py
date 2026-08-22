from __future__ import annotations

import json
from pathlib import Path

import pytest

from imposition.feature_orientation import (
    feature_direction,
    polygon_centroid,
    resolve_feature_orientation_degrees,
)
from imposition.geometry import ImpositionGeometryError
from imposition.model import OrientationFrame
from imposition.objects.cootie_catcher import COOTIE_CATCHER, EXPECTED_SLOTS

SQUARE = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
TRIANGLE = ((50.0, 0.0), (100.0, 100.0), (0.0, 100.0))
READER_FRAME = OrientationFrame(
    up_vector=(0.0, -1.0),
    right_vector=(1.0, 0.0),
)
SPEC = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "imposition"
    / "cootie_catcher"
    / "orientation_validation"
    / "desired_orientation.json"
)


def test_polygon_centroid_supports_square_and_triangle() -> None:
    assert polygon_centroid(SQUARE) == pytest.approx((50.0, 50.0))
    assert polygon_centroid(TRIANGLE) == pytest.approx((50.0, 200.0 / 3.0))


def test_feature_directions_are_geometry_based() -> None:
    diagonal = 2**-0.5

    assert feature_direction(SQUARE, "vertex:2") == pytest.approx(
        (diagonal, diagonal)
    )
    assert feature_direction(SQUARE, "vertex:3") == pytest.approx(
        (-diagonal, diagonal)
    )

    # Triangle edge directions are outward normals, not edge tangents.
    assert feature_direction(TRIANGLE, "edge:1") == pytest.approx((0.0, 1.0))


@pytest.mark.parametrize(
    ("polygon", "top_anchor", "right_anchor", "expected_degrees"),
    [
        (SQUARE, "vertex:2", "vertex:3", 225.0),
        (TRIANGLE, "edge:2", "edge:0", 63.43494882292201),
        (TRIANGLE, "edge:0", "edge:1", 296.565051177078),
        (TRIANGLE, "vertex:1", "edge:1", 236.30993247402023),
        (TRIANGLE, "vertex:2", "vertex:0", 123.69006752597974),
    ],
)
def test_feature_orientation_supports_desired_cootie_patterns(
    polygon,
    top_anchor: str,
    right_anchor: str,
    expected_degrees: float,
) -> None:
    assert resolve_feature_orientation_degrees(
        polygon,
        top_anchor=top_anchor,
        right_anchor=right_anchor,
        target_frame=READER_FRAME,
    ) == pytest.approx(expected_degrees)


def test_right_feature_rejects_wrong_handedness() -> None:
    with pytest.raises(ImpositionGeometryError, match="reader-right half-plane"):
        resolve_feature_orientation_degrees(
            SQUARE,
            top_anchor="vertex:2",
            right_anchor="vertex:1",
            target_frame=READER_FRAME,
        )


def test_committed_desired_spec_resolves_all_twenty_reader_frames() -> None:
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    by_slot = {item["slot"]: item for item in payload["slots"]}
    feature_maps = payload["feature_maps"]

    assert tuple(by_slot) == EXPECTED_SLOTS

    for slot_id in EXPECTED_SLOTS:
        item = by_slot[slot_id]
        shape = item["shape"]
        polygon = TRIANGLE if shape == "triangle" else SQUARE
        feature_map = feature_maps[shape]
        anchors = feature_map["vertices"] | feature_map["edges"]

        degrees = resolve_feature_orientation_degrees(
            polygon,
            top_anchor=anchors[item["desired_top_feature"]],
            right_anchor=anchors[item["desired_right_feature"]],
            target_frame=COOTIE_CATCHER.slot(slot_id).target_orientation.frame,
        )

        assert 0.0 <= degrees < 360.0
