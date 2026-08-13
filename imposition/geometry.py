"""Shared geometry and orientation primitives for physical imposition."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .model import ObjectPlacement, Point, Polygon


class ImpositionGeometryError(ValueError):
    """Raised when imposition geometry cannot be resolved safely."""


def normalize_vector(vector: Point) -> Point:
    """Return *vector* normalized to unit length.

    The imposition coordinate system follows SVG convention: x increases to the
    right and y increases downward. Normalization itself is coordinate-system
    agnostic, but the convention matters for the rotation helpers below.
    """

    x, y = vector
    if not math.isfinite(x) or not math.isfinite(y):
        raise ImpositionGeometryError(
            "Orientation vectors must contain finite coordinates."
        )
    length = math.hypot(x, y)
    if length <= 1e-12:
        raise ImpositionGeometryError("Orientation vectors must have non-zero length.")
    return x / length, y / length


def clockwise_angle_degrees(source_up: Point, target_up: Point) -> float:
    """Return the clockwise rotation mapping ``source_up`` to ``target_up``.

    SVG uses a y-down coordinate system. With that convention, the ordinary
    two-dimensional rotation matrix has visually clockwise positive angles. The
    result is normalized to ``[0, 360)`` degrees.
    """

    source_x, source_y = normalize_vector(source_up)
    target_x, target_y = normalize_vector(target_up)
    dot = source_x * target_x + source_y * target_y
    cross = source_x * target_y - source_y * target_x
    angle = math.degrees(math.atan2(cross, dot)) % 360.0
    if math.isclose(angle, 360.0, abs_tol=1e-10) or math.isclose(
        angle, 0.0, abs_tol=1e-10
    ):
        return 0.0
    return angle


def rotate_vector_clockwise(vector: Point, degrees: float) -> Point:
    """Rotate a vector clockwise in SVG y-down coordinates."""

    if not math.isfinite(degrees):
        raise ImpositionGeometryError("Rotation must be a finite number of degrees.")
    x, y = vector
    if not math.isfinite(x) or not math.isfinite(y):
        raise ImpositionGeometryError("Vectors must contain finite coordinates.")
    radians = math.radians(degrees)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return x * cosine - y * sine, x * sine + y * cosine


def resolve_orientation_degrees(
    source_up: Point,
    target_up: Point,
    *,
    override_degrees: float | None = None,
) -> float:
    """Resolve source-to-slot rotation, honoring an explicit override.

    Overrides are intentionally generic: an imposition object may use them for
    physically validated exceptions without changing the semantic source or
    target vectors. They are normalized to ``[0, 360)``.
    """

    if override_degrees is not None:
        if not math.isfinite(override_degrees):
            raise ImpositionGeometryError("Orientation override must be finite.")
        result = override_degrees % 360.0
        return 0.0 if math.isclose(result, 0.0, abs_tol=1e-10) else result
    return clockwise_angle_degrees(source_up, target_up)


def map_normalized_polygon(
    polygon: Sequence[Point],
    placement: ObjectPlacement,
) -> Polygon:
    """Map a normalized object polygon into a physical millimetre placement."""

    if placement.width_mm <= 0 or placement.height_mm <= 0:
        raise ImpositionGeometryError(
            "Object placement dimensions must be greater than zero."
        )
    if not all(
        math.isfinite(value)
        for value in (
            placement.x_mm,
            placement.y_mm,
            placement.width_mm,
            placement.height_mm,
        )
    ):
        raise ImpositionGeometryError("Object placement values must be finite.")
    if len(polygon) < 3:
        raise ImpositionGeometryError(
            "Slot polygons must contain at least three points."
        )

    mapped: list[Point] = []
    for x, y in polygon:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ImpositionGeometryError("Slot polygons must contain finite coordinates.")
        mapped.append(
            (
                placement.x_mm + x * placement.width_mm,
                placement.y_mm + y * placement.height_mm,
            )
        )
    return tuple(mapped)
