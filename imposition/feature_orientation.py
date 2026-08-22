"""Resolve polygon features into semantic reader orientation frames."""

from __future__ import annotations

import math
import re

from .geometry import (
    ImpositionGeometryError,
    clockwise_angle_degrees,
    normalize_vector,
    rotate_vector_clockwise,
)
from .model import OrientationFrame, Point, Polygon

_FEATURE_RE = re.compile(r"^(vertex|edge):(\d+)$")
_ALIGNMENT_TOLERANCE = 1e-7


def polygon_centroid(polygon: Polygon) -> Point:
    """Return the area centroid of a non-degenerate simple polygon."""

    if len(polygon) < 3:
        raise ImpositionGeometryError(
            "Feature orientation requires a polygon with at least three vertices."
        )

    area2 = 0.0
    x_numerator = 0.0
    y_numerator = 0.0

    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        x1, y1 = first
        x2, y2 = second
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            raise ImpositionGeometryError(
                "Feature orientation polygons must contain finite coordinates."
            )
        cross = x1 * y2 - x2 * y1
        area2 += cross
        x_numerator += (x1 + x2) * cross
        y_numerator += (y1 + y2) * cross

    if math.isclose(area2, 0.0, abs_tol=1e-12):
        raise ImpositionGeometryError(
            "Feature orientation requires a non-degenerate polygon."
        )

    return (
        x_numerator / (3.0 * area2),
        y_numerator / (3.0 * area2),
    )


def feature_direction(polygon: Polygon, anchor: str) -> Point:
    """Return the outward semantic direction associated with a polygon feature.

    Vertex directions run from polygon centroid to the selected vertex. Edge
    directions are the edge normal that points away from the polygon centroid.
    This definition is independent of clockwise/counter-clockwise vertex order.
    """

    match = _FEATURE_RE.fullmatch(anchor)
    if match is None:
        raise ImpositionGeometryError(
            f"Feature anchor {anchor!r} must use vertex:N or edge:N syntax."
        )

    feature_kind = match.group(1)
    index = int(match.group(2))
    if index >= len(polygon):
        raise ImpositionGeometryError(
            f"Feature anchor {anchor!r} is outside a {len(polygon)}-vertex polygon."
        )

    centroid = polygon_centroid(polygon)

    if feature_kind == "vertex":
        vertex = polygon[index]
        return normalize_vector(
            (vertex[0] - centroid[0], vertex[1] - centroid[1])
        )

    first = polygon[index]
    second = polygon[(index + 1) % len(polygon)]
    edge = (second[0] - first[0], second[1] - first[1])
    if math.isclose(math.hypot(*edge), 0.0, abs_tol=1e-12):
        raise ImpositionGeometryError(
            f"Feature anchor {anchor!r} references a zero-length edge."
        )

    midpoint = ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)
    away = (midpoint[0] - centroid[0], midpoint[1] - centroid[1])

    normal_a = normalize_vector((-edge[1], edge[0]))
    normal_b = (-normal_a[0], -normal_a[1])
    dot_a = normal_a[0] * away[0] + normal_a[1] * away[1]
    dot_b = normal_b[0] * away[0] + normal_b[1] * away[1]

    if math.isclose(dot_a, dot_b, abs_tol=1e-12):
        raise ImpositionGeometryError(
            f"Cannot determine an outward normal for feature anchor {anchor!r}."
        )
    return normal_a if dot_a > dot_b else normal_b


def resolve_feature_orientation_degrees(
    polygon: Polygon,
    *,
    top_anchor: str,
    right_anchor: str,
    target_frame: OrientationFrame,
) -> float:
    """Rotate polygon features into a destination reader frame.

    ``top_anchor`` is aligned exactly with ``target_frame.up_vector``.
    ``right_anchor`` is then checked after that rotation and must land in the
    positive half-plane defined by ``target_frame.right_vector``. The right
    feature therefore disambiguates handedness without requiring top/right
    source features themselves to be perpendicular.
    """

    if target_frame.right_vector is None:
        raise ImpositionGeometryError(
            "Feature orientation requires a target right-vector."
        )

    target_up = normalize_vector(target_frame.up_vector)
    target_right = normalize_vector(target_frame.right_vector)
    dot = target_up[0] * target_right[0] + target_up[1] * target_right[1]
    if not math.isclose(dot, 0.0, abs_tol=_ALIGNMENT_TOLERANCE):
        raise ImpositionGeometryError(
            "Feature-orientation target up/right vectors must be perpendicular."
        )

    top_direction = feature_direction(polygon, top_anchor)
    right_direction = feature_direction(polygon, right_anchor)
    resolved = clockwise_angle_degrees(top_direction, target_up)

    rotated_right = normalize_vector(
        rotate_vector_clockwise(right_direction, resolved)
    )
    right_alignment = (
        rotated_right[0] * target_right[0]
        + rotated_right[1] * target_right[1]
    )
    if right_alignment <= _ALIGNMENT_TOLERANCE:
        raise ImpositionGeometryError(
            f"Right feature {right_anchor!r} does not land in the target "
            "reader-right half-plane after aligning the top feature."
        )

    return resolved
