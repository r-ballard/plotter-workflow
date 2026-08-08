from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


class PlacementValidationError(ValueError):
    """Raised when generated HP-GL violates the configured placement envelope."""


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def contains(self, other: "Bounds", tolerance: float = 0.0) -> bool:
        return (
            other.min_x >= self.min_x - tolerance
            and other.max_x <= self.max_x + tolerance
            and other.min_y >= self.min_y - tolerance
            and other.max_y <= self.max_y + tolerance
        )

    def inset(self, amount: float) -> "Bounds":
        if amount < 0:
            raise PlacementValidationError("Margin inset cannot be negative.")
        if amount * 2 >= self.width or amount * 2 >= self.height:
            raise PlacementValidationError(
                "Requested margin consumes the entire configured paper profile."
            )
        return Bounds(
            self.min_x + amount,
            self.min_y + amount,
            self.max_x - amount,
            self.max_y - amount,
        )


@dataclass(frozen=True)
class ParsedHPGL:
    addressed_bounds: Bounds
    drawing_bounds: Bounds
    coordinate_modes: tuple[str, ...]
    addressed_point_count: int
    drawing_segment_count: int


@dataclass(frozen=True)
class PlacementReport:
    source_hpgl: str
    device: str
    page_profile: str
    margin: str
    plotter_unit_length_mm: float
    margin_units: float
    tolerance_units: float
    paper_bounds: Bounds
    margin_bounds: Bounds
    addressed_bounds: Bounds
    drawing_bounds: Bounds
    coordinate_modes: tuple[str, ...]
    addressed_point_count: int
    drawing_segment_count: int
    status: str = "pass"

    def to_dict(self) -> dict:
        return asdict(self)


_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
_LENGTH_RE = re.compile(
    r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mm|cm|in)\s*$",
    re.IGNORECASE,
)


def _bounds(points: Iterable[tuple[float, float]], *, label: str) -> Bounds:
    point_list = list(points)
    if not point_list:
        raise PlacementValidationError(f"HP-GL contains no {label} coordinates.")
    xs = [point[0] for point in point_list]
    ys = [point[1] for point in point_list]
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def _coordinate_pairs(argument_text: str) -> list[tuple[float, float]]:
    values = [float(value) for value in _NUMBER_RE.findall(argument_text)]
    if not values:
        return []
    if len(values) % 2:
        raise PlacementValidationError(
            f"HP-GL coordinate list contains an odd number of values: {argument_text!r}"
        )
    return list(zip(values[::2], values[1::2]))


def parse_hpgl_coordinates(text: str) -> ParsedHPGL:
    """Parse PA/PR/PU/PD motion sufficiently to audit generated plot extents."""
    absolute = True
    pen_down = False
    current = (0.0, 0.0)
    addressed_points: list[tuple[float, float]] = []
    drawing_points: list[tuple[float, float]] = []
    drawing_segments = 0
    seen_modes: list[str] = []

    def record_mode(name: str) -> None:
        if name not in seen_modes:
            seen_modes.append(name)

    def move_to(raw_point: tuple[float, float]) -> None:
        nonlocal current, drawing_segments
        start = current
        if absolute:
            destination = raw_point
        else:
            destination = (current[0] + raw_point[0], current[1] + raw_point[1])
        addressed_points.append(destination)
        if pen_down:
            drawing_points.append(start)
            drawing_points.append(destination)
            drawing_segments += 1
        current = destination

    for raw_command in text.replace("\r", "\n").split(";"):
        command = raw_command.strip()
        if len(command) < 2:
            continue
        opcode = command[:2].upper()
        arguments = command[2:]
        if opcode == "IN":
            absolute = True
            pen_down = False
            current = (0.0, 0.0)
            continue
        if opcode == "PA":
            absolute = True
            record_mode("absolute")
            for point in _coordinate_pairs(arguments):
                move_to(point)
            continue
        if opcode == "PR":
            absolute = False
            record_mode("relative")
            for point in _coordinate_pairs(arguments):
                move_to(point)
            continue
        if opcode in {"PU", "PD"}:
            pen_down = opcode == "PD"
            for point in _coordinate_pairs(arguments):
                move_to(point)
            continue

    if not addressed_points:
        raise PlacementValidationError("HP-GL contains no addressed motion coordinates.")
    if not drawing_points:
        raise PlacementValidationError("HP-GL contains no pen-down drawing coordinates.")

    return ParsedHPGL(
        addressed_bounds=_bounds(addressed_points, label="addressed motion"),
        drawing_bounds=_bounds(drawing_points, label="pen-down drawing"),
        coordinate_modes=tuple(seen_modes) or ("absolute",),
        addressed_point_count=len(addressed_points),
        drawing_segment_count=drawing_segments,
    )


def parse_length_mm(value: str) -> float:
    match = _LENGTH_RE.match(value)
    if not match:
        raise PlacementValidationError(
            f"Unsupported length {value!r}; use mm, cm, or in (for example 10mm or 0.5in)."
        )
    magnitude = float(match.group(1))
    unit = match.group(2).lower()
    if magnitude < 0:
        raise PlacementValidationError("Length cannot be negative.")
    if unit == "mm":
        return magnitude
    if unit == "cm":
        return magnitude * 10.0
    return magnitude * 25.4


def _load_device_profile(config_path: Path, *, device: str, page_profile: str) -> tuple[Bounds, float]:
    with Path(config_path).open("rb") as handle:
        config = tomllib.load(handle)
    try:
        device_config = config["device"][device]
    except KeyError as exc:
        raise PlacementValidationError(
            f"Device {device!r} is not defined in {config_path}."
        ) from exc
    unit_text = str(device_config.get("plotter_unit_length", ""))
    unit_length_mm = parse_length_mm(unit_text)
    if unit_length_mm <= 0:
        raise PlacementValidationError("plotter_unit_length must be greater than zero.")
    papers = device_config.get("paper", [])
    paper = next((item for item in papers if item.get("name") == page_profile), None)
    if paper is None:
        raise PlacementValidationError(
            f"Paper profile {page_profile!r} is not defined for device {device!r}."
        )
    try:
        x_min, x_max = (float(value) for value in paper["x_range"])
        y_min, y_max = (float(value) for value in paper["y_range"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PlacementValidationError(
            f"Paper profile {page_profile!r} does not contain valid x_range/y_range values."
        ) from exc
    return Bounds(x_min, y_min, x_max, y_max), unit_length_mm


def validate_hpgl_placement(
    hpgl_path: Path,
    *,
    config_path: Path,
    device: str,
    page_profile: str,
    margin: str,
    tolerance_units: float = 2.0,
) -> PlacementReport:
    hpgl_path = Path(hpgl_path)
    text = hpgl_path.read_text(encoding="ascii", errors="ignore")
    parsed = parse_hpgl_coordinates(text)
    paper_bounds, unit_length_mm = _load_device_profile(
        Path(config_path), device=device, page_profile=page_profile
    )
    margin_mm = parse_length_mm(margin)
    margin_units = margin_mm / unit_length_mm
    margin_bounds = paper_bounds.inset(margin_units)

    if not paper_bounds.contains(parsed.addressed_bounds, tolerance=tolerance_units):
        raise PlacementValidationError(
            "HP-GL addressed coordinates exceed the configured paper profile: "
            f"addressed={parsed.addressed_bounds}, paper={paper_bounds}."
        )
    if not margin_bounds.contains(parsed.drawing_bounds, tolerance=tolerance_units):
        raise PlacementValidationError(
            "HP-GL pen-down coordinates violate the requested layout margin: "
            f"drawing={parsed.drawing_bounds}, allowed={margin_bounds}."
        )

    return PlacementReport(
        source_hpgl=hpgl_path.name,
        device=device,
        page_profile=page_profile,
        margin=margin,
        plotter_unit_length_mm=unit_length_mm,
        margin_units=margin_units,
        tolerance_units=tolerance_units,
        paper_bounds=paper_bounds,
        margin_bounds=margin_bounds,
        addressed_bounds=parsed.addressed_bounds,
        drawing_bounds=parsed.drawing_bounds,
        coordinate_modes=parsed.coordinate_modes,
        addressed_point_count=parsed.addressed_point_count,
        drawing_segment_count=parsed.drawing_segment_count,
    )


def write_placement_report(report: PlacementReport, destination: Path) -> Path:
    destination = Path(destination)
    destination.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return destination
