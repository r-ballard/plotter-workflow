"""Shared geometry and orientation primitives for physical imposition."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .model import ObjectPlacement, OrientationFrame, Point, Polygon


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


def _normalized_frame(frame: OrientationFrame) -> tuple[Point, Point | None]:
    """Normalize and validate an orientation frame."""

    up = normalize_vector(frame.up_vector)
    if frame.right_vector is None:
        return up, None

    right = normalize_vector(frame.right_vector)
    dot = up[0] * right[0] + up[1] * right[1]
    if not math.isclose(dot, 0.0, abs_tol=1e-7):
        raise ImpositionGeometryError(
            "Orientation frame up/right vectors must be perpendicular."
        )
    return up, right


def resolve_orientation_frame_degrees(
    source_frame: OrientationFrame,
    target_frame: OrientationFrame,
    *,
    override_degrees: float | None = None,
) -> float:
    """Resolve a source frame into a target frame using rotation only.

    The v1 intrinsic-canvas contract supplies only an ``up_vector`` and is
    therefore fully supported. When both frames also provide ``right_vector``,
    the secondary axis is checked after rotation. A mismatch indicates that the
    two frames differ by reflection/handedness and cannot be satisfied by a
    rotation-only imposition transform.
    """

    if override_degrees is not None:
        return resolve_orientation_degrees(
            source_frame.up_vector,
            target_frame.up_vector,
            override_degrees=override_degrees,
        )

    source_up, source_right = _normalized_frame(source_frame)
    target_up, target_right = _normalized_frame(target_frame)
    resolved = clockwise_angle_degrees(source_up, target_up)

    if source_right is not None and target_right is not None:
        rotated_right = normalize_vector(
            rotate_vector_clockwise(source_right, resolved)
        )
        if not (
            math.isclose(rotated_right[0], target_right[0], abs_tol=1e-7)
            and math.isclose(rotated_right[1], target_right[1], abs_tol=1e-7)
        ):
            raise ImpositionGeometryError(
                "Orientation frames differ in handedness; rotation alone cannot "
                "map source right-vector to target right-vector."
            )

    return resolved


def rotated_rectangle_size(
    width: float,
    height: float,
    rotation_degrees: float,
) -> tuple[float, float]:
    """Return the axis-aligned bounds of a rectangle after center rotation."""

    if width <= 0 or height <= 0:
        raise ImpositionGeometryError("Rectangle dimensions must be greater than zero.")
    if not all(math.isfinite(value) for value in (width, height, rotation_degrees)):
        raise ImpositionGeometryError(
            "Rectangle dimensions and rotation must be finite."
        )

    radians = math.radians(rotation_degrees)
    cosine = abs(math.cos(radians))
    sine = abs(math.sin(radians))
    rotated_width = width * cosine + height * sine
    rotated_height = width * sine + height * cosine
    return rotated_width, rotated_height


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
