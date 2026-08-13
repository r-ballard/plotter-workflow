"""Shared validation and intrinsic-canvas inspection for imposition SVG sources."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .model import IntrinsicCanvas, Point, Polygon

UNSUPPORTED_SVG_TAGS = {"foreignObject", "image", "text", "use"}
CANVAS_PREFIX = "data-viz-canvas-"
CANVAS_VERSION = 1
CANVAS_COORDINATE_SYSTEM = "svg-y-down"
_ANCHOR_RE = re.compile(r"^(edge|vertex):(\d+)$")
_REQUIRED_CANVAS_ATTRIBUTES = (
    "data-viz-canvas-version",
    "data-viz-canvas-shape",
    "data-viz-canvas-coordinate-system",
    "data-viz-canvas-up-anchor",
    "data-viz-canvas-up-vector",
    "data-viz-canvas-polygon",
)


class ImpositionSourceError(ValueError):
    """Raised when a source SVG cannot be safely interpreted for imposition."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def inspect_svg_source(path: Path) -> IntrinsicCanvas | None:
    """Validate a vector SVG and return its intrinsic canvas when declared.

    Generic vector SVGs remain valid and return ``None``. If any intrinsic-canvas
    metadata is present, the complete v1 semantic contract must be valid.
    """

    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ImpositionSourceError(f"Invalid SVG/XML in {path}: {exc}") from exc

    if _local_name(root.tag) != "svg":
        raise ImpositionSourceError(f"Expected an SVG root element in {path}")

    unsupported = sorted(
        {_local_name(element.tag) for element in root.iter()} & UNSUPPORTED_SVG_TAGS
    )
    if unsupported:
        raise ImpositionSourceError(
            f"{path}: unsupported SVG elements for imposition: "
            f"{', '.join(unsupported)}. Convert raster images and live text to "
            "plotter-ready vector paths first."
        )

    return parse_intrinsic_canvas(root, source=path)


def parse_intrinsic_canvas(
    root: ET.Element,
    *,
    source: Path | str = "SVG root",
) -> IntrinsicCanvas | None:
    """Parse the ``data-viz-canvas-*`` contract from an SVG root element."""

    canvas_attributes = {
        key: value for key, value in root.attrib.items() if key.startswith(CANVAS_PREFIX)
    }
    if not canvas_attributes:
        return None

    missing = [key for key in _REQUIRED_CANVAS_ATTRIBUTES if not root.get(key)]
    if missing:
        raise ImpositionSourceError(
            f"{source}: incomplete intrinsic canvas metadata; missing "
            + ", ".join(missing)
        )

    raw_version = root.get("data-viz-canvas-version", "")
    try:
        version = int(raw_version)
    except ValueError as exc:
        raise ImpositionSourceError(
            f"{source}: invalid data-viz-canvas-version={raw_version!r}"
        ) from exc
    if version != CANVAS_VERSION:
        raise ImpositionSourceError(
            f"{source}: unsupported intrinsic canvas version {version}; "
            f"expected {CANVAS_VERSION}"
        )

    coordinate_system = root.get("data-viz-canvas-coordinate-system", "")
    if coordinate_system != CANVAS_COORDINATE_SYSTEM:
        raise ImpositionSourceError(
            f"{source}: unsupported intrinsic canvas coordinate system "
            f"{coordinate_system!r}; expected {CANVAS_COORDINATE_SYSTEM!r}"
        )

    shape = root.get("data-viz-canvas-shape", "").strip()
    if not shape:
        raise ImpositionSourceError(f"{source}: intrinsic canvas shape cannot be empty")

    polygon = _parse_polygon(root.get("data-viz-canvas-polygon", ""), source=source)
    up_vector = _parse_point(
        root.get("data-viz-canvas-up-vector", ""),
        field="data-viz-canvas-up-vector",
        source=source,
    )
    _validate_unit_vector(up_vector, source=source)

    up_anchor = root.get("data-viz-canvas-up-anchor", "")
    _validate_anchor(up_anchor, polygon=polygon, source=source)

    clip_id = root.get("data-viz-canvas-clip-id")
    if clip_id is not None:
        clip_id = clip_id.strip() or None

    return IntrinsicCanvas(
        version=version,
        shape=shape,
        coordinate_system=coordinate_system,
        polygon=polygon,
        up_anchor=up_anchor,
        up_vector=up_vector,
        clip_id=clip_id,
    )


def _parse_polygon(raw: str, *, source: Path | str) -> Polygon:
    tokens = raw.split()
    if len(tokens) < 3:
        raise ImpositionSourceError(
            f"{source}: data-viz-canvas-polygon must contain at least three points"
        )
    return tuple(
        _parse_point(token, field="data-viz-canvas-polygon", source=source)
        for token in tokens
    )


def _parse_point(raw: str, *, field: str, source: Path | str) -> Point:
    parts = raw.split(",")
    if len(parts) != 2:
        raise ImpositionSourceError(
            f"{source}: {field} point {raw!r} must use x,y syntax"
        )
    try:
        point = (float(parts[0]), float(parts[1]))
    except ValueError as exc:
        raise ImpositionSourceError(
            f"{source}: {field} point {raw!r} contains a non-numeric coordinate"
        ) from exc
    if not all(math.isfinite(value) for value in point):
        raise ImpositionSourceError(
            f"{source}: {field} point {raw!r} must contain finite coordinates"
        )
    return point


def _validate_unit_vector(vector: Point, *, source: Path | str) -> None:
    length = math.hypot(*vector)
    if not math.isclose(length, 1.0, rel_tol=1e-6, abs_tol=1e-9):
        raise ImpositionSourceError(
            f"{source}: data-viz-canvas-up-vector must be normalized; "
            f"observed length {length:.12g}"
        )


def _validate_anchor(
    raw: str,
    *,
    polygon: Polygon,
    source: Path | str,
) -> None:
    match = _ANCHOR_RE.fullmatch(raw)
    if match is None:
        raise ImpositionSourceError(
            f"{source}: data-viz-canvas-up-anchor must use edge:N or vertex:N syntax"
        )
    index = int(match.group(2))
    if index >= len(polygon):
        raise ImpositionSourceError(
            f"{source}: data-viz-canvas-up-anchor index {index} is outside a "
            f"{len(polygon)}-vertex polygon"
        )
