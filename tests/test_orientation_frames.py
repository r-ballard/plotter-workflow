from __future__ import annotations

import pytest

from imposition.geometry import (
    ImpositionGeometryError,
    resolve_orientation_frame_degrees,
)
from imposition.model import IntrinsicCanvas, OrientationFrame, OrientationTarget


def test_v1_intrinsic_canvas_promotes_to_orientation_frame() -> None:
    canvas = IntrinsicCanvas(
        version=1,
        shape="triangle",
        coordinate_system="svg-y-down",
        polygon=((50.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        up_anchor="vertex:0",
        up_vector=(0.0, -1.0),
    )

    assert canvas.orientation_frame == OrientationFrame(
        up_vector=(0.0, -1.0),
        anchor="vertex:0",
    )


def test_orientation_target_promotes_to_full_frame() -> None:
    target = OrientationTarget(
        up_vector=(1.0, 0.0),
        validation="provisional",
        right_vector=(0.0, 1.0),
    )

    assert target.frame == OrientationFrame(
        up_vector=(1.0, 0.0),
        right_vector=(0.0, 1.0),
    )


def test_corner_up_square_can_map_diagonal_to_page_up() -> None:
    diagonal = 2**-0.5
    source = OrientationFrame(
        up_vector=(-diagonal, -diagonal),
        anchor="vertex:0",
    )
    target = OrientationFrame(up_vector=(0.0, -1.0))

    assert resolve_orientation_frame_degrees(source, target) == pytest.approx(45.0)


def test_triangle_side_anchor_can_make_apex_point_right() -> None:
    source = OrientationFrame(
        up_vector=(1.0, 0.0),
        anchor="edge:1",
    )
    target = OrientationFrame(up_vector=(0.0, -1.0))

    assert resolve_orientation_frame_degrees(source, target) == pytest.approx(270.0)


def test_full_orientation_frame_validates_secondary_axis() -> None:
    source = OrientationFrame(
        up_vector=(0.0, -1.0),
        right_vector=(1.0, 0.0),
    )
    target = OrientationFrame(
        up_vector=(1.0, 0.0),
        right_vector=(0.0, 1.0),
    )

    assert resolve_orientation_frame_degrees(source, target) == pytest.approx(90.0)


def test_reflected_orientation_frame_is_rejected() -> None:
    source = OrientationFrame(
        up_vector=(0.0, -1.0),
        right_vector=(1.0, 0.0),
    )
    reflected_target = OrientationFrame(
        up_vector=(0.0, -1.0),
        right_vector=(-1.0, 0.0),
    )

    with pytest.raises(ImpositionGeometryError, match="handedness"):
        resolve_orientation_frame_degrees(source, reflected_target)
