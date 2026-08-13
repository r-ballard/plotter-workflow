from __future__ import annotations

import pytest

from imposition.geometry import (
    ImpositionGeometryError,
    clockwise_angle_degrees,
    map_normalized_polygon,
    normalize_vector,
    resolve_orientation_degrees,
    rotate_vector_clockwise,
    rotated_rectangle_size,
)
from imposition.model import ObjectPlacement, SheetSpec


def test_clockwise_angle_uses_svg_y_down_convention() -> None:
    assert clockwise_angle_degrees((0.0, -1.0), (1.0, 0.0)) == pytest.approx(
        90.0
    )
    assert clockwise_angle_degrees((1.0, 0.0), (0.0, 1.0)) == pytest.approx(
        90.0
    )
    assert clockwise_angle_degrees((0.0, -1.0), (-1.0, 0.0)) == pytest.approx(
        270.0
    )


def test_orientation_normalizes_non_unit_vectors() -> None:
    assert normalize_vector((0.0, -12.0)) == pytest.approx((0.0, -1.0))
    assert clockwise_angle_degrees((0.0, -12.0), (5.0, 0.0)) == pytest.approx(
        90.0
    )


def test_rotate_vector_clockwise_matches_angle_convention() -> None:
    assert rotate_vector_clockwise((0.0, -1.0), 90.0) == pytest.approx((1.0, 0.0))
    assert rotate_vector_clockwise((0.0, -1.0), 180.0) == pytest.approx(
        (0.0, 1.0)
    )


def test_explicit_orientation_override_wins() -> None:
    assert resolve_orientation_degrees(
        (0.0, -1.0),
        (1.0, 0.0),
        override_degrees=450.0,
    ) == pytest.approx(90.0)


def test_zero_length_orientation_vector_is_rejected() -> None:
    with pytest.raises(ImpositionGeometryError, match="non-zero"):
        clockwise_angle_degrees((0.0, 0.0), (0.0, -1.0))


def test_map_normalized_polygon_to_physical_placement() -> None:
    placement = ObjectPlacement(
        sheet=SheetSpec("test", 300.0, 200.0, "landscape"),
        x_mm=10.0,
        y_mm=20.0,
        width_mm=200.0,
        height_mm=100.0,
    )
    polygon = ((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0))

    expected = ((10.0, 20.0), (110.0, 20.0), (110.0, 120.0), (10.0, 120.0))
    actual = map_normalized_polygon(polygon, placement)
    for actual_point, expected_point in zip(actual, expected, strict=True):
        assert actual_point == pytest.approx(expected_point)


def test_map_normalized_polygon_rejects_invalid_placement() -> None:
    with pytest.raises(ImpositionGeometryError, match="greater than zero"):
        map_normalized_polygon(
            ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
            ObjectPlacement(
                sheet=SheetSpec("test", 300.0, 200.0, "landscape"),
                x_mm=0.0,
                y_mm=0.0,
                width_mm=0.0,
                height_mm=100.0,
            ),
        )


def test_rotated_rectangle_size_supports_arbitrary_angles() -> None:
    width, height = rotated_rectangle_size(100.0, 50.0, 45.0)
    expected = 75.0 * 2**0.5
    assert width == pytest.approx(expected)
    assert height == pytest.approx(expected)


def test_rotated_rectangle_size_preserves_quarter_turn_contract() -> None:
    assert rotated_rectangle_size(100.0, 50.0, 0.0) == pytest.approx((100.0, 50.0))
    assert rotated_rectangle_size(100.0, 50.0, 90.0) == pytest.approx((50.0, 100.0))
