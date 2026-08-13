#!/usr/bin/env python3
"""Impose vector SVG artwork for a one-sheet origami fortune teller.

The ``cootie_catcher`` layout divides a square substrate into 20 semantic
artwork slots:

* four corner ``outer-N`` squares;
* eight ``selector-N`` triangular flaps; and
* eight ``reveal-N`` triangular message regions.

The physical square is placed on a supported landscape sheet.  The default is
the largest possible square aligned to the left edge, which produces one trim
cut on Letter, A4, A3, and Tabloid sheets.

Input remains vector-only.  Generic SVGs are flattened to one logical output
layer.  SVGs using plotter-workflow's strict ``pen-N`` contract preserve
logical pen IDs and generation provenance through imposition.

The v1 orientation table is intentionally marked provisional.  Its purpose is
to generate a deterministic asymmetric hardware fixture.  Update the table and
golden fixture only after a physical plot/fold validation.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from imposition.model import ObjectPlacement, SheetSpec
from imposition.objects.cootie_catcher import COOTIE_CATCHER, CootieCatcherError
from imposition.source import ImpositionSourceError, inspect_svg_source
from svg_pen_contract import PenLayerContractError, inspect_pen_layer_contract

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

MM_TO_PX = 96.0 / 25.4
LAYOUT_NAME = "cootie_catcher"
ORIENTATION_VALIDATION = "provisional"
LAYOUT_MARKER_ATTRIBUTE = "data-plotter-workflow-layout"
LAYOUT_MARKER_VALUE = "preserve"
FIT_MODES = {"contain", "cover"}
SQUARE_POSITIONS = {"left", "center", "right"}
UNSUPPORTED_SVG_TAGS = {"image", "text", "use", "foreignObject"}
DRAWABLE_SVG_TAGS = {"path", "line", "polyline", "polygon", "rect", "circle", "ellipse"}

SHEET_SIZES_MM: dict[str, tuple[float, float]] = {
    "letter": (279.4, 215.9),
    "a4": (297.0, 210.0),
    "a3": (420.0, 297.0),
    "tabloid": (431.8, 279.4),
}

Point = tuple[float, float]
Polygon = tuple[Point, ...]

# Normalized coordinates use an SVG-like origin: (0, 0) is the physical top
# left of the square and both coordinates run from 0 to 1.
Q = 0.25
C = 0.5
TQ = 0.75

COOTIE_PANEL_POLYGONS: dict[str, Polygon] = {
    # Four corner squares.
    "outer-1": ((0.0, 0.0), (Q, 0.0), (Q, Q), (0.0, Q)),
    "outer-2": ((TQ, 0.0), (1.0, 0.0), (1.0, Q), (TQ, Q)),
    "outer-3": ((TQ, TQ), (1.0, TQ), (1.0, 1.0), (TQ, 1.0)),
    "outer-4": ((0.0, TQ), (Q, TQ), (Q, 1.0), (0.0, 1.0)),
    # Selector triangles, clockwise from the north-west half of the top edge.
    "selector-1": ((Q, 0.0), (C, 0.0), (Q, Q)),
    "selector-2": ((C, 0.0), (TQ, 0.0), (TQ, Q)),
    "selector-3": ((1.0, Q), (1.0, C), (TQ, Q)),
    "selector-4": ((1.0, C), (1.0, TQ), (TQ, TQ)),
    "selector-5": ((TQ, 1.0), (C, 1.0), (TQ, TQ)),
    "selector-6": ((C, 1.0), (Q, 1.0), (Q, TQ)),
    "selector-7": ((0.0, TQ), (0.0, C), (Q, TQ)),
    "selector-8": ((0.0, C), (0.0, Q), (Q, Q)),
    # Reveal triangles fill the central first-blintz diamond.  Each reveal-N
    # shares the long diagonal edge of selector-N, which is the semantic
    # selector/reveal pairing used by a conventional printable template.
    "reveal-1": ((Q, Q), (C, 0.0), (C, C)),
    "reveal-2": ((C, 0.0), (TQ, Q), (C, C)),
    "reveal-3": ((TQ, Q), (1.0, C), (C, C)),
    "reveal-4": ((1.0, C), (TQ, TQ), (C, C)),
    "reveal-5": ((TQ, TQ), (C, 1.0), (C, C)),
    "reveal-6": ((C, 1.0), (Q, TQ), (C, C)),
    "reveal-7": ((Q, TQ), (0.0, C), (C, C)),
    "reveal-8": ((0.0, C), (Q, Q), (C, C)),
}

EXPECTED_SLOTS = tuple(
    [f"outer-{number}" for number in range(1, 5)]
    + [f"selector-{number}" for number in range(1, 9)]
    + [f"reveal-{number}" for number in range(1, 9)]
)
SELECTOR_REVEAL_PAIRS = {
    f"selector-{number}": f"reveal-{number}" for number in range(1, 9)
}

# Clockwise rotation in degrees.  This is deliberately a provisional table for
# the asymmetric physical validation fixture, not a claim that final folded
# reading orientation has already been hardware-verified.
COOTIE_PANEL_ROTATIONS: dict[str, int] = {
    "outer-1": 0,
    "outer-2": 90,
    "outer-3": 180,
    "outer-4": 270,
    "selector-1": 0,
    "selector-2": 0,
    "selector-3": 90,
    "selector-4": 90,
    "selector-5": 180,
    "selector-6": 180,
    "selector-7": 270,
    "selector-8": 270,
    "reveal-1": 0,
    "reveal-2": 0,
    "reveal-3": 90,
    "reveal-4": 90,
    "reveal-5": 180,
    "reveal-6": 180,
    "reveal-7": 270,
    "reveal-8": 270,
}


class ImpositionError(ValueError):
    """Raised when cootie-catcher source data cannot be safely imposed."""


@dataclass(frozen=True)
class PanelEntry:
    slot: str
    source: Path
    fit: str
    margin_mm: float
    rotation_degrees: int

    @property
    def kind(self) -> str:
        return self.slot.rsplit("-", 1)[0]

    @property
    def index(self) -> int:
        return int(self.slot.rsplit("-", 1)[1])


@dataclass(frozen=True)
class SquarePlacement:
    x_mm: float
    y_mm: float
    size_mm: float
    position: str


@dataclass(frozen=True)
class PenMetadata:
    stroke: str
    fill: str


@dataclass(frozen=True)
class ContractFragment:
    pen: int
    generation: int
    stroke: str
    fill: str
    svg_text: str


@dataclass(frozen=True)
class RenderedPanel:
    slot: str
    kind: str
    index: int
    source: str
    fit: str
    margin_mm: float
    rotation_degrees: int
    polygon_normalized: tuple[tuple[float, float], ...]
    polygon_mm: tuple[tuple[float, float], ...]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _mm_to_px(value: float) -> float:
    return value * MM_TO_PX


def _px_to_mm(value: float) -> float:
    return value / MM_TO_PX


def _require_vpype():
    try:
        import vpype  # type: ignore
    except ImportError as exc:  # pragma: no cover - project dependency
        raise ImpositionError(
            "vpype is required. Run this script through the project environment: "
            "uv run python cootie_impose.py ..."
        ) from exc
    return vpype


def resolve_input_dir(value: str) -> Path:
    """Resolve an explicit directory or a subdirectory of repository input/."""
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    repo_candidate = Path(__file__).resolve().parent / "input" / candidate
    if repo_candidate.is_dir():
        return repo_candidate.resolve()

    raise ImpositionError(
        f"Input directory does not exist: {value!r}. Provide a directory path or a "
        "subdirectory name under input/."
    )


def _resolve_source(input_dir: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ImpositionError("Every manifest panel requires a non-empty 'source'.")
    source = (input_dir / raw).resolve()
    try:
        source.relative_to(input_dir.resolve())
    except ValueError as exc:
        raise ImpositionError("Manifest sources must remain inside the input directory.") from exc
    if not source.is_file():
        raise ImpositionError(f"Source SVG does not exist: {source}")
    if source.suffix.lower() != ".svg":
        raise ImpositionError(f"Only SVG source files are supported: {source}")
    try:
        inspect_svg_source(source)
    except ImpositionSourceError as exc:
        raise ImpositionError(str(exc)) from exc
    return source


def _float_field(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ImpositionError(f"Manifest field {key!r} must be numeric.") from exc
    if result < 0:
        raise ImpositionError(f"Manifest field {key!r} cannot be negative.")
    return result


def load_manifest(
    input_dir: Path,
    manifest_path: Path,
    *,
    default_fit: str = "contain",
    default_margin_mm: float = 3.0,
) -> list[PanelEntry]:
    """Load and validate the canonical 20-panel v1 manifest."""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ImpositionError(f"Manifest does not exist: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ImpositionError(f"Invalid JSON in {manifest_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ImpositionError("Cootie-catcher manifest must be a JSON object.")
    if payload.get("schema_version", 1) != 1:
        raise ImpositionError("Only cootie-catcher manifest schema_version 1 is supported.")
    if payload.get("layout", LAYOUT_NAME) != LAYOUT_NAME:
        raise ImpositionError(f"Only layout={LAYOUT_NAME!r} is currently supported.")

    raw_panels = payload.get("panels")
    if not isinstance(raw_panels, list) or not raw_panels:
        raise ImpositionError("Cootie-catcher manifest requires a non-empty 'panels' array.")

    entries: list[PanelEntry] = []
    assigned: list[str] = []
    for manifest_index, raw in enumerate(raw_panels):
        if not isinstance(raw, dict):
            raise ImpositionError(f"Manifest panels[{manifest_index}] must be an object.")
        slot = raw.get("slot")
        if not isinstance(slot, str) or slot not in COOTIE_PANEL_POLYGONS:
            raise ImpositionError(
                f"Manifest panels[{manifest_index}] has invalid slot {slot!r}; "
                f"expected one of {', '.join(EXPECTED_SLOTS)}."
            )
        fit = str(raw.get("fit", default_fit)).lower()
        if fit not in FIT_MODES:
            raise ImpositionError(f"fit must be one of {sorted(FIT_MODES)}, got {fit!r}.")
        margin_mm = _float_field(raw, "margin_mm", default_margin_mm)

        rotation_raw = raw.get("rotation_degrees", COOTIE_PANEL_ROTATIONS[slot])
        try:
            rotation = int(rotation_raw)
        except (TypeError, ValueError) as exc:
            raise ImpositionError("rotation_degrees must be an integer multiple of 90.") from exc
        if rotation % 90:
            raise ImpositionError("rotation_degrees must be an integer multiple of 90.")
        rotation %= 360

        entries.append(
            PanelEntry(
                slot=slot,
                source=_resolve_source(input_dir, raw.get("source")),
                fit=fit,
                margin_mm=margin_mm,
                rotation_degrees=rotation,
            )
        )
        assigned.append(slot)

    missing = [slot for slot in EXPECTED_SLOTS if slot not in assigned]
    duplicates = sorted({slot for slot in assigned if assigned.count(slot) > 1})
    extras = sorted(set(assigned) - set(EXPECTED_SLOTS))
    if len(assigned) != len(EXPECTED_SLOTS) or missing or duplicates or extras:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if duplicates:
            details.append("duplicated " + ", ".join(duplicates))
        if extras:
            details.append("unexpected " + ", ".join(extras))
        raise ImpositionError(
            "Manifest must assign all 20 semantic slots exactly once"
            + (": " + "; ".join(details) if details else ".")
        )

    return sorted(entries, key=lambda entry: EXPECTED_SLOTS.index(entry.slot))


def square_placement(
    sheet_size: str,
    *,
    position: str = "left",
    square_size_mm: float | None = None,
) -> SquarePlacement:
    """Return the square's placement within a supported landscape sheet."""
    if sheet_size not in SHEET_SIZES_MM:
        raise ImpositionError(f"Unsupported sheet size {sheet_size!r}.")

    sheet_width, sheet_height = SHEET_SIZES_MM[sheet_size]
    sheet = SheetSpec(
        name=sheet_size,
        width_mm=sheet_width,
        height_mm=sheet_height,
        orientation="landscape",
    )
    try:
        resolved = COOTIE_CATCHER.resolve_placement(
            sheet,
            {"position": position, "square_size_mm": square_size_mm},
        )
    except CootieCatcherError as exc:
        raise ImpositionError(str(exc)) from exc

    return SquarePlacement(
        x_mm=resolved.x_mm,
        y_mm=resolved.y_mm,
        size_mm=resolved.width_mm,
        position=position,
    )


def panel_polygon_normalized(slot: str) -> Polygon:
    try:
        return COOTIE_CATCHER.slot(slot).polygon
    except CootieCatcherError as exc:
        raise ImpositionError(str(exc)) from exc


def panel_polygon_px(slot: str, placement: SquarePlacement) -> Polygon:
    polygon = panel_polygon_normalized(slot)
    x0 = _mm_to_px(placement.x_mm)
    y0 = _mm_to_px(placement.y_mm)
    size = _mm_to_px(placement.size_mm)
    return tuple((x0 + x * size, y0 + y * size) for x, y in polygon)


def polygon_area(polygon: Sequence[Point]) -> float:
    """Return the unsigned shoelace area of a polygon."""
    return abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(polygon, (*polygon[1:], polygon[0]))
        )
    ) / 2.0


def polygon_centroid(polygon: Sequence[Point]) -> Point:
    # All v1 panel polygons are convex, so the arithmetic vertex centroid is
    # guaranteed to be an interior point and is the desired artwork anchor.
    return (
        sum(point[0] for point in polygon) / len(polygon),
        sum(point[1] for point in polygon) / len(polygon),
    )


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _inward_halfplanes(polygon: Sequence[Point], inset: float = 0.0) -> list[tuple[Point, float]]:
    center = polygon_centroid(polygon)
    planes: list[tuple[Point, float]] = []
    for p1, p2 in zip(polygon, (*polygon[1:], polygon[0])):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            raise ImpositionError("Panel polygon contains a zero-length edge.")
        normal = (-dy / length, dx / length)
        if _dot(normal, _sub(center, p1)) < 0:
            normal = (-normal[0], -normal[1])
        planes.append((normal, _dot(normal, p1) + inset))
    return planes


def _intersect_lines(n1: Point, c1: float, n2: Point, c2: float) -> Point:
    determinant = n1[0] * n2[1] - n1[1] * n2[0]
    if abs(determinant) <= 1e-12:
        raise ImpositionError("Inset polygon contains parallel adjacent edges.")
    return (
        (c1 * n2[1] - n1[1] * c2) / determinant,
        (n1[0] * c2 - c1 * n2[0]) / determinant,
    )


def inset_convex_polygon(polygon: Sequence[Point], inset: float) -> Polygon:
    """Inset a convex polygon by a perpendicular distance in SVG units."""
    if inset < 0:
        raise ImpositionError("Panel margin cannot be negative.")
    if inset == 0:
        return tuple(polygon)
    planes = _inward_halfplanes(polygon, inset=inset)
    result = tuple(
        _intersect_lines(previous[0], previous[1], current[0], current[1])
        for previous, current in zip((planes[-1], *planes[:-1]), planes)
    )
    if polygon_area(result) <= 1e-9:
        raise ImpositionError("Panel margin leaves no drawable area.")
    center = polygon_centroid(result)
    for normal, c in planes:
        if _dot(normal, center) < c - 1e-7:
            raise ImpositionError("Panel margin is too large for this panel.")
    return result


def _rotated_canvas_size(width: float, height: float, rotation_degrees: int) -> tuple[float, float]:
    return (height, width) if rotation_degrees % 180 else (width, height)


def _largest_centered_canvas_scale(
    polygon: Sequence[Point],
    canvas_width: float,
    canvas_height: float,
) -> float:
    if canvas_width <= 0 or canvas_height <= 0:
        raise ImpositionError("Source SVG must have positive width and height.")
    center = polygon_centroid(polygon)
    scales: list[float] = []
    for normal, c in _inward_halfplanes(polygon):
        available = _dot(normal, center) - c
        demand = (abs(normal[0]) * canvas_width + abs(normal[1]) * canvas_height) / 2.0
        if demand <= 1e-12:
            continue
        scales.append(available / demand)
    if not scales or min(scales) <= 0:
        raise ImpositionError("Unable to fit source canvas inside panel polygon.")
    return min(scales)


def fit_transform(
    polygon: Sequence[Point],
    *,
    source_width: float,
    source_height: float,
    rotation_degrees: int,
    fit: str,
) -> tuple[float, float, float]:
    """Return (scale, target_x, target_y) after source-center rotation."""
    rotated_width, rotated_height = _rotated_canvas_size(
        source_width, source_height, rotation_degrees
    )
    if fit == "contain":
        scale = _largest_centered_canvas_scale(polygon, rotated_width, rotated_height)
        target_x, target_y = polygon_centroid(polygon)
    elif fit == "cover":
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        box_width = max(xs) - min(xs)
        box_height = max(ys) - min(ys)
        if rotated_width <= 0 or rotated_height <= 0:
            raise ImpositionError("Source SVG must have positive width and height.")
        scale = max(box_width / rotated_width, box_height / rotated_height)
        target_x = (min(xs) + max(xs)) / 2.0
        target_y = (min(ys) + max(ys)) / 2.0
    else:
        raise ImpositionError(f"Unknown fit mode {fit!r}.")
    return scale, target_x, target_y


def clip_segment_to_convex_polygon(
    start: Point,
    end: Point,
    polygon: Sequence[Point],
    *,
    epsilon: float = 1e-9,
) -> tuple[Point, Point] | None:
    """Clip one line segment to a convex polygon using half-plane intervals."""
    t_min = 0.0
    t_max = 1.0
    direction = (end[0] - start[0], end[1] - start[1])

    for normal, c in _inward_halfplanes(polygon):
        initial = _dot(normal, start) - c
        rate = _dot(normal, direction)
        if abs(rate) <= epsilon:
            if initial < -epsilon:
                return None
            continue
        crossing = -initial / rate
        if rate > 0:
            t_min = max(t_min, crossing)
        else:
            t_max = min(t_max, crossing)
        if t_min > t_max + epsilon:
            return None

    def at(t: float) -> Point:
        return start[0] + direction[0] * t, start[1] + direction[1] * t

    return at(max(0.0, t_min)), at(min(1.0, t_max))


def _points_close(a: complex, b: complex, tolerance: float = 1e-7) -> bool:
    return abs(a - b) <= tolerance


def clip_line_collection(lines: Any, polygon: Sequence[Point]) -> Any:
    """Clip every polyline segment to *polygon*, preserving contiguous runs."""
    vpype = _require_vpype()
    result = vpype.LineCollection()
    for raw_line in lines:
        points = [complex(point) for point in raw_line]
        current: list[complex] = []
        for first, second in pairwise(points):
            clipped = clip_segment_to_convex_polygon(
                (first.real, first.imag), (second.real, second.imag), polygon
            )
            if clipped is None:
                if len(current) >= 2:
                    result.append(current)
                current = []
                continue
            p0 = complex(*clipped[0])
            p1 = complex(*clipped[1])
            if current and _points_close(current[-1], p0):
                if not _points_close(current[-1], p1):
                    current.append(p1)
            else:
                if len(current) >= 2:
                    result.append(current)
                current = [p0, p1]
        if len(current) >= 2:
            result.append(current)
    return result


def render_lines_to_panel(
    lines: Any,
    source_width: float,
    source_height: float,
    *,
    polygon: Sequence[Point],
    rotation_degrees: int,
    fit: str,
) -> Any:
    """Rotate, fit, position, and polygon-clip a vpype LineCollection."""
    if source_width <= 0 or source_height <= 0:
        raise ImpositionError("Source SVG must have positive width and height.")
    lines.translate(-source_width / 2.0, -source_height / 2.0)
    if rotation_degrees:
        lines.rotate(math.radians(rotation_degrees))
    scale, target_x, target_y = fit_transform(
        polygon,
        source_width=source_width,
        source_height=source_height,
        rotation_degrees=rotation_degrees,
        fit=fit,
    )
    lines.scale(scale)
    lines.translate(target_x, target_y)
    return clip_line_collection(lines, polygon)


def _validate_vector_source(path: Path) -> None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ImpositionError(f"Invalid SVG/XML in {path}: {exc}") from exc
    if _local_name(root.tag) != "svg":
        raise ImpositionError(f"Expected an SVG root element in {path}")
    unsupported = sorted(
        {_local_name(element.tag) for element in root.iter()} & UNSUPPORTED_SVG_TAGS
    )
    if unsupported:
        raise ImpositionError(
            f"{path}: unsupported SVG elements for imposition: {', '.join(unsupported)}. "
            "Convert raster images and live text to plotter-ready vector paths first."
        )


def source_mode(entries: Iterable[PanelEntry]) -> str:
    """Return ``generic`` or ``pen-contract`` and reject mixed source modes."""
    modes: set[str] = set()
    for entry in entries:
        _validate_vector_source(entry.source)
        try:
            contract = inspect_pen_layer_contract(entry.source)
        except PenLayerContractError as exc:
            raise ImpositionError(str(exc)) from exc
        modes.add("pen-contract" if contract is not None else "generic")
    if len(modes) != 1:
        raise ImpositionError(
            "Do not mix generic SVGs and strict pen-N contract SVGs in one cootie catcher."
        )
    return next(iter(modes))


def _read_generic(path: Path, *, quantization: float) -> tuple[Any, float, float]:
    vpype = _require_vpype()
    lines, width, height = vpype.read_svg(str(path), quantization=quantization, crop=True)
    return lines, float(width), float(height)


def _root_svg_attributes(root: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("width", "height", "viewBox", "preserveAspectRatio"):
        if root.get(key) is not None:
            result[key] = str(root.get(key))
    return result


def _contract_fragments(path: Path) -> tuple[list[ContractFragment], dict[int, PenMetadata], dict[int, set[int]]]:
    """Extract generation fragments while retaining source pen metadata."""
    tree = ET.parse(path)
    root = tree.getroot()
    fragments: list[ContractFragment] = []
    metadata: dict[int, PenMetadata] = {}
    declared_generations: dict[int, set[int]] = defaultdict(set)

    for group in root:
        if _local_name(group.tag) != "g" or not group.get("id", "").startswith("pen-"):
            continue
        try:
            pen = int(group.get("id", "").split("-", 1)[1])
        except ValueError:
            continue  # inspect_pen_layer_contract() is authoritative validation.
        pen_metadata = PenMetadata(stroke=group.get("stroke", "#000000"), fill=group.get("fill", "none"))
        metadata[pen] = pen_metadata
        for generation_group in group:
            if _local_name(generation_group.tag) != "g":
                continue
            raw_generation = generation_group.get("data-generation")
            if raw_generation is None:
                continue
            generation = int(raw_generation)
            declared_generations[pen].add(generation)

            wrapper_root = ET.Element(f"{{{SVG_NS}}}svg", _root_svg_attributes(root))
            for root_child in root:
                if _local_name(root_child.tag) in {"defs", "style"}:
                    wrapper_root.append(copy.deepcopy(root_child))
            wrapper_pen = ET.SubElement(
                wrapper_root,
                f"{{{SVG_NS}}}g",
                {
                    key: value
                    for key, value in group.attrib.items()
                    if key not in {"id", "data-pen", "data-generations"}
                },
            )
            wrapper_pen.append(copy.deepcopy(generation_group))
            fragments.append(
                ContractFragment(
                    pen=pen,
                    generation=generation,
                    stroke=pen_metadata.stroke,
                    fill=pen_metadata.fill,
                    svg_text=ET.tostring(wrapper_root, encoding="unicode"),
                )
            )

    return fragments, metadata, declared_generations


def _read_contract_fragment(fragment: ContractFragment, *, quantization: float) -> tuple[Any, float, float]:
    vpype = _require_vpype()
    lines, width, height = vpype.read_svg(
        io.StringIO(fragment.svg_text), quantization=quantization, crop=True
    )
    return lines, float(width), float(height)


def _svg_number(value: float) -> str:
    rounded = round(value, 6)
    if abs(rounded) < 0.0000005:
        rounded = 0.0
    return f"{rounded:.6f}".rstrip("0").rstrip(".") or "0"


def _line_to_path_data(line: Iterable[complex]) -> str:
    points = [complex(point) for point in line]
    if len(points) < 2:
        return ""
    return "M " + " L ".join(
        f"{_svg_number(point.real)} {_svg_number(point.imag)}" for point in points
    )


def _append_paths(parent: ET.Element, lines: Any, **attributes: str) -> int:
    count = 0
    for line in lines:
        path_data = _line_to_path_data(line)
        if not path_data:
            continue
        ET.SubElement(parent, f"{{{SVG_NS}}}path", {"d": path_data, **attributes})
        count += 1
    return count


def _new_physical_svg_root(
    sheet_size: str,
    placement: SquarePlacement,
    *,
    guide: bool = False,
) -> ET.Element:
    sheet_width_mm, sheet_height_mm = SHEET_SIZES_MM[sheet_size]
    attributes = {
        "width": f"{_svg_number(sheet_width_mm)}mm",
        "height": f"{_svg_number(sheet_height_mm)}mm",
        "viewBox": (
            f"0 0 {_svg_number(_mm_to_px(sheet_width_mm))} "
            f"{_svg_number(_mm_to_px(sheet_height_mm))}"
        ),
        LAYOUT_MARKER_ATTRIBUTE: LAYOUT_MARKER_VALUE,
        "data-plotter-workflow-page-size": sheet_size,
        "data-plotter-workflow-orientation": "landscape",
        "data-imposition-layout": LAYOUT_NAME,
        "data-imposition-square-size-mm": _svg_number(placement.size_mm),
        "data-imposition-square-position": placement.position,
        "data-imposition-orientation-validation": ORIENTATION_VALIDATION,
    }
    if guide:
        attributes["data-imposition-guide"] = "true"
    return ET.Element(f"{{{SVG_NS}}}svg", attributes)


def _assert_pen_metadata_consistent(
    combined: dict[int, PenMetadata], incoming: dict[int, PenMetadata], source: Path
) -> None:
    for pen, metadata in incoming.items():
        previous = combined.get(pen)
        if previous is not None and previous != metadata:
            raise ImpositionError(
                f"{source}: pen-{pen} preview metadata {metadata} does not match "
                f"previous source metadata {previous}."
            )
        combined[pen] = metadata


def impose(
    entries: Sequence[PanelEntry],
    *,
    sheet_size: str,
    placement: SquarePlacement,
    quantization_mm: float = 0.1,
) -> tuple[ET.Element, list[RenderedPanel], str]:
    """Build an imposed physical SVG root and semantic render records."""
    if quantization_mm <= 0:
        raise ImpositionError("quantization_mm must be greater than zero.")
    mode = source_mode(entries)
    quantization = _mm_to_px(quantization_mm)
    root = _new_physical_svg_root(sheet_size, placement)
    rendered: list[RenderedPanel] = []
    total_path_count = 0

    generic_group: ET.Element | None = None
    pen_groups: dict[int, ET.Element] = {}
    pen_generations: dict[int, dict[int, ET.Element]] = defaultdict(dict)
    combined_pen_metadata: dict[int, PenMetadata] = {}
    combined_declared_generations: dict[int, set[int]] = defaultdict(set)

    if mode == "generic":
        generic_group = ET.SubElement(
            root,
            f"{{{SVG_NS}}}g",
            {
                "id": "imposed-artwork",
                "fill": "none",
                "stroke": "#000000",
                "data-source-mode": "generic",
            },
        )

    for entry in entries:
        polygon = panel_polygon_px(entry.slot, placement)
        try:
            drawable_polygon = inset_convex_polygon(polygon, _mm_to_px(entry.margin_mm))
        except ImpositionError as exc:
            raise ImpositionError(f"{entry.slot}: {exc}") from exc

        if mode == "generic":
            assert generic_group is not None
            lines, width, height = _read_generic(entry.source, quantization=quantization)
            lines = render_lines_to_panel(
                lines,
                width,
                height,
                polygon=drawable_polygon,
                rotation_degrees=entry.rotation_degrees,
                fit=entry.fit,
            )
            slot_group = ET.SubElement(
                generic_group,
                f"{{{SVG_NS}}}g",
                {"data-imposed-slot": entry.slot, "data-source": entry.source.name},
            )
            total_path_count += _append_paths(slot_group, lines)
        else:
            fragments, source_metadata, source_generations = _contract_fragments(entry.source)
            _assert_pen_metadata_consistent(combined_pen_metadata, source_metadata, entry.source)
            for pen, generations in source_generations.items():
                combined_declared_generations[pen].update(generations)
            for fragment in fragments:
                lines, width, height = _read_contract_fragment(fragment, quantization=quantization)
                lines = render_lines_to_panel(
                    lines,
                    width,
                    height,
                    polygon=drawable_polygon,
                    rotation_degrees=entry.rotation_degrees,
                    fit=entry.fit,
                )
                if lines.is_empty():
                    continue
                generation_group = pen_generations[fragment.pen].get(fragment.generation)
                if generation_group is None:
                    # Pen groups are finalized after all sources are known so
                    # data-generations can include empty declared generations.
                    generation_group = ET.Element(
                        f"{{{SVG_NS}}}g", {"data-generation": str(fragment.generation)}
                    )
                    pen_generations[fragment.pen][fragment.generation] = generation_group
                slot_group = ET.SubElement(
                    generation_group,
                    f"{{{SVG_NS}}}g",
                    {"data-imposed-slot": entry.slot, "data-source": entry.source.name},
                )
                total_path_count += _append_paths(slot_group, lines)

        polygon_mm = tuple(
            (
                _px_to_mm(point[0]),
                _px_to_mm(point[1]),
            )
            for point in polygon
        )
        rendered.append(
            RenderedPanel(
                slot=entry.slot,
                kind=entry.kind,
                index=entry.index,
                source=entry.source.name,
                fit=entry.fit,
                margin_mm=entry.margin_mm,
                rotation_degrees=entry.rotation_degrees,
                polygon_normalized=COOTIE_PANEL_POLYGONS[entry.slot],
                polygon_mm=polygon_mm,
            )
        )

    if mode == "pen-contract":
        # Rebuild canonical top-level pen groups after all source metadata and
        # generations are known.  Empty declared generations are retained.
        for pen in sorted(combined_pen_metadata):
            metadata = combined_pen_metadata[pen]
            generations = sorted(combined_declared_generations.get(pen, set()))
            if not generations:
                raise ImpositionError(f"pen-{pen} declares no generations after imposition.")
            pen_group = ET.SubElement(
                root,
                f"{{{SVG_NS}}}g",
                {
                    "id": f"pen-{pen}",
                    "data-pen": str(pen),
                    "data-generations": ",".join(str(value) for value in generations),
                    "fill": metadata.fill,
                    "stroke": metadata.stroke,
                    "data-source-mode": "pen-contract",
                },
            )
            pen_groups[pen] = pen_group
            for generation in generations:
                group = pen_generations[pen].get(generation)
                if group is None:
                    group = ET.Element(
                        f"{{{SVG_NS}}}g", {"data-generation": str(generation)}
                    )
                pen_group.append(group)

    if total_path_count == 0:
        raise ImpositionError("Cootie-catcher sources produced no plottable vector paths.")
    return root, rendered, mode


def _line_path(parent: ET.Element, p1: Point, p2: Point) -> None:
    ET.SubElement(
        parent,
        f"{{{SVG_NS}}}path",
        {
            "d": (
                f"M {_svg_number(p1[0])} {_svg_number(p1[1])} "
                f"L {_svg_number(p2[0])} {_svg_number(p2[1])}"
            )
        },
    )


def guide_segments(
    sheet_size: str, placement: SquarePlacement
) -> dict[str, list[tuple[Point, Point]]]:
    """Return object-owned trim and crease segments in physical SVG pixels."""
    if sheet_size not in SHEET_SIZES_MM:
        raise ImpositionError(f"Unsupported sheet size {sheet_size!r}.")

    sheet_width_mm, sheet_height_mm = SHEET_SIZES_MM[sheet_size]
    object_placement = ObjectPlacement(
        sheet=SheetSpec(
            name=sheet_size,
            width_mm=sheet_width_mm,
            height_mm=sheet_height_mm,
            orientation="landscape",
        ),
        x_mm=placement.x_mm,
        y_mm=placement.y_mm,
        width_mm=placement.size_mm,
        height_mm=placement.size_mm,
    )
    try:
        guides = COOTIE_CATCHER.guides(object_placement)
    except CootieCatcherError as exc:
        raise ImpositionError(str(exc)) from exc

    segments: dict[str, list[tuple[Point, Point]]] = {
        "trim": [],
        "first-blintz": [],
        "second-blintz": [],
        "center-prefold": [],
    }
    for guide in guides:
        points = guide.points
        point_pairs = pairwise((*points, points[0])) if guide.closed else pairwise(points)
        for start, end in point_pairs:
            segments[guide.kind].append(
                (
                    (_mm_to_px(start[0]), _mm_to_px(start[1])),
                    (_mm_to_px(end[0]), _mm_to_px(end[1])),
                )
            )
    return segments


def build_guide_svg(sheet_size: str, placement: SquarePlacement) -> ET.Element:
    root = _new_physical_svg_root(sheet_size, placement, guide=True)
    pen_group = ET.SubElement(
        root,
        f"{{{SVG_NS}}}g",
        {
            "id": "pen-1",
            "data-pen": "1",
            "data-generations": "0",
            "fill": "none",
            "stroke": "#000000",
        },
    )
    generation_group = ET.SubElement(
        pen_group, f"{{{SVG_NS}}}g", {"data-generation": "0"}
    )
    for kind, segments in guide_segments(sheet_size, placement).items():
        if not segments:
            continue
        kind_group = ET.SubElement(
            generation_group, f"{{{SVG_NS}}}g", {"data-guide-kind": kind}
        )
        for start, end in segments:
            _line_path(kind_group, start, end)
    return root


def _write_xml(root: ET.Element, path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}. Use --overwrite to replace it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _round_nested_points(points: Iterable[Point]) -> list[list[float]]:
    return [[round(x, 6), round(y, 6)] for x, y in points]


def build_audit_payload(
    *,
    sheet_size: str,
    placement: SquarePlacement,
    rendered: Sequence[RenderedPanel],
    mode: str,
    quantization_mm: float,
) -> dict[str, Any]:
    sheet_width, sheet_height = SHEET_SIZES_MM[sheet_size]
    return {
        "schema_version": 1,
        "layout": LAYOUT_NAME,
        "orientation_validation": ORIENTATION_VALIDATION,
        "sheet": {
            "name": sheet_size,
            "orientation": "landscape",
            "width_mm": sheet_width,
            "height_mm": sheet_height,
        },
        "square": asdict(placement),
        "source_mode": mode,
        "quantization_mm": quantization_mm,
        "selector_reveal_pairs": SELECTOR_REVEAL_PAIRS,
        "panels": [
            {
                **asdict(panel),
                "polygon_normalized": _round_nested_points(panel.polygon_normalized),
                "polygon_mm": _round_nested_points(panel.polygon_mm),
            }
            for panel in rendered
        ],
        "guide_kinds": ["trim", "first-blintz", "second-blintz", "center-prefold"],
        "converter_contract": {
            LAYOUT_MARKER_ATTRIBUTE: LAYOUT_MARKER_VALUE,
            "data-plotter-workflow-page-size": sheet_size,
            "data-plotter-workflow-orientation": "landscape",
        },
    }


def default_output_path(input_dir: Path) -> Path:
    return Path(__file__).resolve().parent / "output" / f"{input_dir.name}.imposed.svg"


def related_output_paths(output: Path) -> tuple[Path, Path]:
    sidecar = output.with_suffix(".imposition.json")
    guide = output.with_name(f"{output.stem}.guides.svg")
    return sidecar, guide


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", help="Input directory or a subdirectory name under input/.")
    parser.add_argument(
        "--manifest",
        default="cootie.json",
        help="Manifest filename inside input_dir. Default: cootie.json.",
    )
    parser.add_argument(
        "--sheet-size",
        choices=tuple(SHEET_SIZES_MM),
        default="letter",
        help="Landscape physical sheet size. Default: letter.",
    )
    parser.add_argument(
        "--square-position",
        choices=tuple(sorted(SQUARE_POSITIONS)),
        default="left",
        help="Horizontal placement of the origami square. Default: left.",
    )
    parser.add_argument(
        "--square-size-mm",
        type=float,
        help="Optional square side length. Default: largest square that fits the sheet height.",
    )
    parser.add_argument(
        "--fit",
        choices=tuple(sorted(FIT_MODES)),
        default="contain",
        help="Default panel fit mode. Individual manifest entries may override it.",
    )
    parser.add_argument(
        "--panel-margin-mm",
        type=float,
        default=3.0,
        help="Default inset from each panel edge. Default: 3mm.",
    )
    parser.add_argument(
        "--quantization-mm",
        type=float,
        default=0.1,
        help="Maximum segment length used when vpype linearizes curves. Default: 0.1mm.",
    )
    parser.add_argument("--output", type=Path, help="Output imposed SVG path.")
    parser.add_argument("--guides", action="store_true", help="Also write a separate fold/trim guide SVG.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing generated files.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.panel_margin_mm < 0:
            raise ImpositionError("--panel-margin-mm cannot be negative.")
        if args.quantization_mm <= 0:
            raise ImpositionError("--quantization-mm must be greater than zero.")
        input_dir = resolve_input_dir(args.input_dir)
        manifest_path = (input_dir / args.manifest).resolve()
        try:
            manifest_path.relative_to(input_dir)
        except ValueError as exc:
            raise ImpositionError("--manifest must refer to a file inside input_dir.") from exc
        entries = load_manifest(
            input_dir,
            manifest_path,
            default_fit=args.fit,
            default_margin_mm=args.panel_margin_mm,
        )
        placement = square_placement(
            args.sheet_size,
            position=args.square_position,
            square_size_mm=args.square_size_mm,
        )
        root, rendered, mode = impose(
            entries,
            sheet_size=args.sheet_size,
            placement=placement,
            quantization_mm=args.quantization_mm,
        )
        output = (args.output or default_output_path(input_dir)).expanduser().resolve()
        sidecar_path, guide_path = related_output_paths(output)

        outputs_to_check = [output, sidecar_path]
        if args.guides:
            outputs_to_check.append(guide_path)
        if not args.overwrite:
            existing = [path for path in outputs_to_check if path.exists()]
            if existing:
                raise FileExistsError(
                    "Output already exists: " + ", ".join(str(path) for path in existing)
                    + ". Use --overwrite to replace generated files."
                )

        _write_xml(root, output, overwrite=True)
        audit = build_audit_payload(
            sheet_size=args.sheet_size,
            placement=placement,
            rendered=rendered,
            mode=mode,
            quantization_mm=args.quantization_mm,
        )
        sidecar_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        if args.guides:
            _write_xml(
                build_guide_svg(args.sheet_size, placement), guide_path, overwrite=True
            )

        print(output)
        print(sidecar_path)
        if args.guides:
            print(guide_path)
        return 0
    except (ImpositionError, FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
