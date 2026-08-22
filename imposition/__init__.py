"""Shared imposition models and source-SVG inspection utilities."""

from .geometry import (
    ImpositionGeometryError,
    clockwise_angle_degrees,
    map_normalized_polygon,
    normalize_vector,
    resolve_orientation_degrees,
    resolve_orientation_frame_degrees,
    rotate_vector_clockwise,
    rotated_rectangle_size,
)
from .model import (
    Guide,
    ImpositionObject,
    IntrinsicCanvas,
    ObjectPlacement,
    OrientationFrame,
    OrientationResolution,
    OrientationTarget,
    Point,
    Polygon,
    SheetSpec,
    Slot,
)
from .source import ImpositionSourceError, inspect_svg_source, parse_intrinsic_canvas

__all__ = [
    "Guide",
    "ImpositionGeometryError",
    "ImpositionObject",
    "ImpositionSourceError",
    "IntrinsicCanvas",
    "ObjectPlacement",
    "OrientationFrame",
    "OrientationResolution",
    "OrientationTarget",
    "Point",
    "Polygon",
    "SheetSpec",
    "Slot",
    "clockwise_angle_degrees",
    "inspect_svg_source",
    "map_normalized_polygon",
    "normalize_vector",
    "parse_intrinsic_canvas",
    "resolve_orientation_degrees",
    "resolve_orientation_frame_degrees",
    "rotate_vector_clockwise",
    "rotated_rectangle_size",
]
