#!/usr/bin/env python3
"""Impose plotter-ready SVG artwork as a one-sheet eight-page mini-book.

The first supported layout is ``pocketmod8``: a landscape sheet divided into
four columns and two rows. Logical pages are mapped to physical cells as::

    top row:     5  4  3  2    (rotated 180 degrees)
    bottom row:  6  7  8  1    (upright)

Input artwork remains vector-only. Generic SVGs are flattened to one logical
layer. SVGs using plotter-workflow's strict ``pen-N`` contract preserve logical
pen IDs and generation provenance through imposition. Neutral producer bundles
retain their logical IDs, SVG geometry, and semantic provenance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, "") and str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from logical_layer_contract import (
    NEUTRAL_CONTRACT,
    InputMode,
    LogicalLayerContractError,
    LogicalLayerManifest,
    inspect_svg_contract,
    load_logical_layer_manifest,
    validate_surface_against_manifest,
)
from svg_pen_contract import PenLayerContractError, inspect_pen_layer_contract

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

MM_TO_PX = 96.0 / 25.4
LAYOUT_NAME = "pocketmod8"
LAYOUT_MARKER_ATTRIBUTE = "data-plotter-workflow-layout"
LAYOUT_MARKER_VALUE = "preserve"

SHEET_SIZES_MM: dict[str, tuple[float, float]] = {
    "letter": (279.4, 215.9),
    "a4": (297.0, 210.0),
    "a3": (420.0, 297.0),
    "tabloid": (431.8, 279.4),
}

# SVG row 0 is the physical top of the landscape sheet.
# row, column, clockwise rotation in degrees
POCKETMOD8_CELLS: dict[int, tuple[int, int, int]] = {
    1: (1, 3, 0),
    2: (0, 3, 180),
    3: (0, 2, 180),
    4: (0, 1, 180),
    5: (0, 0, 180),
    6: (1, 0, 0),
    7: (1, 1, 0),
    8: (1, 2, 0),
}

ALLOWED_SPREADS = {(2, 3), (4, 5), (6, 7), (8, 1)}
FIT_MODES = {"contain", "cover"}
UNSUPPORTED_SVG_TAGS = {"image", "text", "use", "foreignObject"}
DRAWABLE_SVG_TAGS = {"path", "line", "polyline", "polygon", "rect", "circle", "ellipse"}
PEN_ID_RE = re.compile(r"^pen-(\d+)$")


class ImpositionError(ValueError):
    """Raised when booklet source data cannot be safely imposed."""


@dataclass(frozen=True)
class PageEntry:
    pages: tuple[int, ...]
    source: Path
    fit: str
    margin_mm: float
    gutter_mm: float

    @property
    def is_spread(self) -> bool:
        return len(self.pages) == 2


@dataclass(frozen=True)
class RenderedPage:
    page: int
    source: str
    source_part: str
    row: int
    column: int
    rotation_degrees: int
    fit: str
    margin_mm: float
    gutter_mm: float


@dataclass(frozen=True)
class PenMetadata:
    stroke: str
    fill: str


@dataclass
class ContractFragment:
    pen: int
    generation: int
    stroke: str
    fill: str
    svg_text: str


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _natural_key(path: Path) -> tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    )


def _require_vpype():
    try:
        import vpype  # type: ignore
    except ImportError as exc:  # pragma: no cover - project dependency
        raise ImpositionError(
            "vpype is required. Run this script through the project environment: "
            "uv run python scripts/booklet_impose.py ..."
        ) from exc
    return vpype


def _mm_to_px(value: float) -> float:
    return value * MM_TO_PX


def resolve_input_dir(value: str) -> Path:
    """Resolve either an explicit directory or a subdirectory of repository input/."""
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    repo_candidate = REPO_ROOT / "input" / candidate
    if repo_candidate.is_dir():
        return repo_candidate.resolve()

    raise ImpositionError(
        f"Input directory does not exist: {value!r}. Provide a directory path or a "
        "subdirectory name under input/."
    )


def _resolve_source(input_dir: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ImpositionError("Every manifest entry requires a non-empty 'source'.")
    source = (input_dir / raw).resolve()
    if not source.is_file():
        raise ImpositionError(f"Source SVG does not exist: {source}")
    if source.suffix.lower() != ".svg":
        raise ImpositionError(f"Only SVG source files are supported: {source}")
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
    default_fit: str,
    default_margin_mm: float,
    default_gutter_mm: float,
) -> list[PageEntry]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImpositionError(f"Invalid JSON in {manifest_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ImpositionError("Booklet manifest must contain a JSON object.")
    if payload.get("schema_version", 1) != 1:
        raise ImpositionError("Only booklet manifest schema_version 1 is supported.")
    if payload.get("layout", LAYOUT_NAME) != LAYOUT_NAME:
        raise ImpositionError(f"Only layout={LAYOUT_NAME!r} is currently supported.")

    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ImpositionError("Booklet manifest requires a non-empty 'pages' array.")

    entries: list[PageEntry] = []
    assigned: list[int] = []
    for index, raw in enumerate(raw_pages, start=1):
        if not isinstance(raw, dict):
            raise ImpositionError(f"Manifest pages[{index - 1}] must be an object.")

        has_page = "page" in raw
        has_spread = "spread" in raw
        if has_page == has_spread:
            raise ImpositionError(
                f"Manifest pages[{index - 1}] must specify exactly one of 'page' or 'spread'."
            )

        if has_page:
            try:
                page = int(raw["page"])
            except (TypeError, ValueError) as exc:
                raise ImpositionError("Manifest page numbers must be integers.") from exc
            pages = (page,)
        else:
            spread = raw["spread"]
            if not isinstance(spread, list) or len(spread) != 2:
                raise ImpositionError("A spread must be a two-element page array.")
            try:
                pages = (int(spread[0]), int(spread[1]))
            except (TypeError, ValueError) as exc:
                raise ImpositionError("Spread page numbers must be integers.") from exc
            if pages not in ALLOWED_SPREADS:
                allowed = ", ".join(f"{a}-{b}" for a, b in sorted(ALLOWED_SPREADS))
                raise ImpositionError(
                    f"Spread {pages[0]}-{pages[1]} is not a facing pocketmod8 spread. "
                    f"Allowed logical spreads: {allowed}."
                )

        if any(page not in POCKETMOD8_CELLS for page in pages):
            raise ImpositionError("Logical page numbers must be between 1 and 8.")

        fit = str(raw.get("fit", default_fit)).lower()
        if fit not in FIT_MODES:
            raise ImpositionError(f"fit must be one of {sorted(FIT_MODES)}, got {fit!r}.")

        source = _resolve_source(input_dir, raw.get("source"))
        margin_mm = _float_field(raw, "margin_mm", default_margin_mm)
        gutter_mm = _float_field(raw, "gutter_mm", default_gutter_mm)
        if not has_spread and gutter_mm:
            raise ImpositionError("gutter_mm is only valid for spread entries.")

        entries.append(
            PageEntry(
                pages=pages,
                source=source,
                fit=fit,
                margin_mm=margin_mm,
                gutter_mm=gutter_mm,
            )
        )
        assigned.extend(pages)

    if sorted(assigned) != list(range(1, 9)) or len(assigned) != 8:
        raise ImpositionError(
            "Manifest must assign logical pages 1 through 8 exactly once, including pages inside spreads."
        )
    return entries


def discover_automatic_pages(
    input_dir: Path,
    *,
    fit: str,
    margin_mm: float,
) -> list[PageEntry]:
    sources = sorted(
        (path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".svg"),
        key=_natural_key,
    )
    if len(sources) != 8:
        raise ImpositionError(
            f"Automatic mode requires exactly 8 SVG files in {input_dir}; found {len(sources)}. "
            "Use a booklet manifest when a source represents a spread."
        )
    return [
        PageEntry(pages=(index,), source=source, fit=fit, margin_mm=margin_mm, gutter_mm=0.0)
        for index, source in enumerate(sources, start=1)
    ]


def _validate_svg_source(path: Path) -> None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ImpositionError(f"Invalid SVG/XML in {path}: {exc}") from exc
    if _local_name(root.tag) != "svg":
        raise ImpositionError(f"Expected an SVG root element in {path}.")

    unsupported = sorted(
        {
            _local_name(element.tag)
            for element in root.iter()
            if _local_name(element.tag) in UNSUPPORTED_SVG_TAGS
        }
    )
    if unsupported:
        raise ImpositionError(
            f"{path} contains unsupported non-plotter SVG element(s): {', '.join(unsupported)}. "
            "Convert text to paths and raster images to vector linework first."
        )

    has_pen_group = any(
        _local_name(child.tag) == "g" and PEN_ID_RE.fullmatch(child.get("id", ""))
        for child in root
    )
    if has_pen_group:
        stray = [
            _local_name(child.tag)
            for child in root
            if _local_name(child.tag) in DRAWABLE_SVG_TAGS
        ]
        if stray:
            raise ImpositionError(
                f"{path} mixes pen-N groups with top-level drawable geometry. "
                "Move all plottable geometry into the logical pen groups before imposition."
            )


def determine_source_mode(entries: Sequence[PageEntry]) -> str:
    mode, _ = _inspect_sources(entries)
    return mode


def _inspect_sources(
    entries: Sequence[PageEntry],
) -> tuple[str, LogicalLayerManifest | None]:
    modes: set[InputMode] = set()
    manifests: dict[Path, LogicalLayerManifest] = {}
    authoritative_manifest: LogicalLayerManifest | None = None
    seen: set[Path] = set()
    for entry in entries:
        if entry.source in seen:
            continue
        seen.add(entry.source)
        _validate_svg_source(entry.source)
        try:
            root = ET.parse(entry.source).getroot()
            if root.get("data-viz-layer-contract") == NEUTRAL_CONTRACT:
                if entry.source.parent.name != "surfaces":
                    raise ImpositionError(
                        f"{entry.source}: neutral sources require a design.json bundle "
                        "with artwork in surfaces/."
                    )
                manifest_path = (entry.source.parent.parent / "design.json").resolve()
                if manifest_path not in manifests:
                    manifests[manifest_path] = load_logical_layer_manifest(manifest_path)
                manifest = manifests[manifest_path]
                contract = validate_surface_against_manifest(entry.source, manifest)
                if (authoritative_manifest is not None
                        and authoritative_manifest.raw["logical_layers"] != manifest.raw["logical_layers"]):
                    raise ImpositionError(
                        f"{entry.source}: incompatible logical-layer catalogs across bundles."
                    )
                if authoritative_manifest is not None and authoritative_manifest.path != manifest.path:
                    raise ImpositionError(
                        f"{entry.source}: neutral imposition requires one authoritative bundle manifest."
                    )
                authoritative_manifest = manifest
            else:
                contract = inspect_svg_contract(entry.source)
        except LogicalLayerContractError as exc:
            raise ImpositionError(str(exc)) from exc
        modes.add(contract.mode)

    if len(modes) > 1:
        raise ImpositionError(
            "A booklet may not mix generic SVGs, strict pen-contract SVGs, "
            "and neutral logical-layer SVGs. Use sources with one input contract."
        )
    if modes == {InputMode.NEUTRAL}:
        return "neutral", authoritative_manifest
    if modes == {InputMode.LEGACY}:
        return "pen-contract", None
    return "generic", None


_LOCAL_URL = re.compile(r"url\(\s*['\"]?#([^)'\"\s]+)['\"]?\s*\)", re.IGNORECASE | re.ASCII)
_URL_FUNCTION = re.compile(r"url\(", re.IGNORECASE | re.ASCII)


def _namespace_neutral_fragment(root: ET.Element, prefix: str, source: Path) -> None:
    """Keep local SVG references unambiguous when pages share producer IDs."""
    ids: dict[str, str] = {}
    for element in root.iter():
        if _local_name(element.tag) == "style":
            raise ImpositionError(f"{source}: neutral imposition requires inline SVG styles.")
        element_id = element.get("id")
        if element_id:
            if element_id in ids:
                raise ImpositionError(f"{source}: duplicate SVG element id {element_id!r}.")
            ids[element_id] = f"{prefix}-source-{len(ids)}"

    def reference(target: str) -> str:
        if target not in ids:
            raise ImpositionError(f"{source}: unresolved SVG reference #{target}.")
        return ids[target]

    for element in root.iter():
        for key, value in list(element.attrib.items()):
            if key == "data-viz-canvas-clip-id":
                element.set(key, reference(value))
            elif _local_name(key).lower().startswith("data-"):
                # Semantic metadata is inert text, not an SVG/CSS reference.
                continue
            elif key == "id":
                element.set(key, ids[value])
            elif _local_name(key).lower() == "href":
                if not value.startswith("#"):
                    raise ImpositionError(f"{source}: external SVG references cannot be imposed.")
                element.set(key, "#" + reference(value[1:]))
            elif _URL_FUNCTION.search(value):
                rewritten = _LOCAL_URL.sub(lambda m: f"url(#{reference(m.group(1))})", value)
                if _URL_FUNCTION.search(_LOCAL_URL.sub("", value)):
                    raise ImpositionError(f"{source}: unsupported external SVG URL reference.")
                element.set(key, rewritten)


def _validate_neutral_renderables(element: ET.Element, source: Path) -> None:
    """Validate all copied XML, including non-rendering definition subtrees.

    Producer bundles need static vector shapes, clip paths, and text metadata.
    Other definition types must be explicitly supported before accepting them.
    """
    name = _local_name(element.tag)
    if name not in DRAWABLE_SVG_TAGS | {"svg", "g", "defs", "metadata", "title", "desc", "clipPath"}:
        raise ImpositionError(
            f"{source}: unsupported neutral SVG element {name!r}; convert it to vector paths."
        )
    for key, value in element.attrib.items():
        attribute = _local_name(key).lower()
        if attribute.startswith("on"):
            raise ImpositionError(f"{source}: SVG event-handler attribute {key!r} is unsupported.")
        if attribute in {"src", "srcset", "base"}:
            raise ImpositionError(f"{source}: resource-loading SVG attribute {key!r} is unsupported.")
        if attribute == "href" and not value.startswith("#"):
            raise ImpositionError(f"{source}: external SVG references cannot be imposed.")
        if attribute.startswith("data-"):
            # Browser renderers do not interpret data-* values as CSS or code.
            continue
        if any(token in value for token in ("\\", "/*", "@")):
            raise ImpositionError(
                f"{source}: escaped or indirect CSS resource syntax is unsupported."
            )
        if attribute.startswith("marker") or (
            attribute == "style"
            and re.search(r"(?:^|;)\s*marker(?:-start|-mid|-end)?\s*:", value, re.IGNORECASE | re.ASCII)
        ):
            raise ImpositionError(f"{source}: unsupported neutral marker attribute or style property.")
        if _URL_FUNCTION.search(_LOCAL_URL.sub("", value)):
            raise ImpositionError(f"{source}: unsupported external SVG URL reference.")
    for child in element:
        _validate_neutral_renderables(child, source)


class _NeutralGeometry:
    """Apply existing placement operations to both SVG and presence geometry.

    The XML retains curves, source clips, and path metadata. The companion
    vpype collection determines whether a page/layer survives rectangular
    fitting and cropping; it is never used as the serialized artwork.
    """

    def __init__(self, svg: ET.Element, lines: Any, prefix: str):
        self.svg = svg
        self.lines = lines
        self.prefix = prefix
        self.crop_count = 0

    def _wrap(self, attributes: dict[str, str]) -> None:
        parent = ET.Element(f"{{{SVG_NS}}}g", attributes)
        parent.append(self.svg)
        self.svg = parent

    def scale(self, sx: float, sy: float | None = None) -> None:
        sy = sx if sy is None else sy
        self.lines.scale(sx, sy)
        self._wrap({"transform": f"scale({sx:.12g},{sy:.12g})"})

    def translate(self, dx: float, dy: float) -> None:
        self.lines.translate(dx, dy)
        self._wrap({"transform": f"translate({dx:.12g},{dy:.12g})"})

    def crop(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.lines.crop(x1, y1, x2, y2)
        clip_id = f"{self.prefix}-crop-{self.crop_count}"
        self.crop_count += 1
        self._wrap({"clip-path": f"url(#{clip_id})"})
        defs = ET.SubElement(self.svg, f"{{{SVG_NS}}}defs")
        clip = ET.SubElement(defs, f"{{{SVG_NS}}}clipPath", {"id": clip_id})
        ET.SubElement(clip, f"{{{SVG_NS}}}rect", {
            "x": f"{x1:.12g}", "y": f"{y1:.12g}",
            "width": f"{x2 - x1:.12g}", "height": f"{y2 - y1:.12g}",
        })


def _neutral_fragments(path: Path, page: int, quantization: float):
    source = ET.parse(path).getroot()
    _validate_neutral_renderables(source, path)
    for group in source:
        layer_id = group.get("data-viz-layer-id")
        if layer_id is None:
            continue
        ordinal = group.get("data-viz-layer-ordinal")
        prefix = f"imposed-p{page}-l{ordinal}"
        fragment = ET.Element(source.tag, dict(source.attrib))
        fragment.attrib.pop("data-viz-layer-contract", None)
        for child in source:
            if child.get("data-viz-layer-id") is None:
                fragment.append(copy.deepcopy(child))
        layer = copy.deepcopy(group)
        for key in ("data-viz-layer-id", "data-viz-layer-ordinal", "data-viz-layer-label"):
            layer.attrib.pop(key, None)
        fragment.append(layer)
        _namespace_neutral_fragment(fragment, prefix, path)
        text = ET.tostring(fragment, encoding="unicode")
        lines, width, height = _require_vpype().read_svg(
            io.StringIO(text), quantization=quantization, crop=True
        )
        fragment.set("width", str(width))
        fragment.set("height", str(height))
        geometry = _NeutralGeometry(fragment, lines, prefix)
        # Explicit viewport crop remains valid when nested SVG overflow differs
        # between renderers, including sources without a viewBox.
        geometry.crop(0, 0, float(width), float(height))
        yield layer_id, geometry, float(width), float(height)


def _fit_collection(
    lines: Any,
    source_width: float,
    source_height: float,
    target_width: float,
    target_height: float,
    margin: float,
    fit: str,
) -> None:
    available_width = target_width - 2.0 * margin
    available_height = target_height - 2.0 * margin
    if available_width <= 0 or available_height <= 0:
        raise ImpositionError("Page margin leaves no drawable area in a booklet cell.")
    if source_width <= 0 or source_height <= 0:
        raise ImpositionError("Source SVG has invalid zero or negative dimensions.")

    sx = available_width / source_width
    sy = available_height / source_height
    scale = min(sx, sy) if fit == "contain" else max(sx, sy)
    lines.scale(scale)

    rendered_width = source_width * scale
    rendered_height = source_height * scale
    lines.translate(
        margin + (available_width - rendered_width) / 2.0,
        margin + (available_height - rendered_height) / 2.0,
    )
    lines.crop(margin, margin, target_width - margin, target_height - margin)


def _place_in_cell(lines: Any, page: int, cell_width: float, cell_height: float) -> None:
    row, column, rotation = POCKETMOD8_CELLS[page]
    if rotation == 180:
        # x,y -> cell_width-x, cell_height-y
        lines.scale(-1.0, -1.0)
        lines.translate(cell_width, cell_height)
    lines.translate(column * cell_width, row * cell_height)


def _render_single(
    lines: Any,
    source_width: float,
    source_height: float,
    *,
    page: int,
    cell_width: float,
    cell_height: float,
    margin: float,
    fit: str,
) -> Any:
    _fit_collection(
        lines,
        source_width,
        source_height,
        cell_width,
        cell_height,
        margin,
        fit,
    )
    _place_in_cell(lines, page, cell_width, cell_height)
    return lines


def _render_spread_half(
    lines: Any,
    source_width: float,
    source_height: float,
    *,
    page: int,
    half: str,
    cell_width: float,
    cell_height: float,
    margin: float,
    gutter: float,
    fit: str,
) -> Any:
    spread_width = 2.0 * cell_width
    if gutter >= 2.0 * cell_width:
        raise ImpositionError("Spread gutter is wider than the two-page spread.")

    _fit_collection(
        lines,
        source_width,
        source_height,
        spread_width,
        cell_height,
        margin,
        fit,
    )

    half_gutter = gutter / 2.0
    if half == "left":
        lines.crop(margin, margin, cell_width - half_gutter, cell_height - margin)
    elif half == "right":
        lines.crop(cell_width + half_gutter, margin, spread_width - margin, cell_height - margin)
        lines.translate(-cell_width, 0.0)
    else:  # pragma: no cover - internal invariant
        raise AssertionError(half)

    _place_in_cell(lines, page, cell_width, cell_height)
    return lines


def _read_generic(path: Path, *, quantization: float) -> tuple[Any, float, float]:
    vpype = _require_vpype()
    lines, width, height = vpype.read_svg(str(path), quantization=quantization, crop=True)
    return lines, float(width), float(height)


def _contract_fragments(path: Path) -> list[ContractFragment]:
    root = ET.parse(path).getroot()
    fragments: list[ContractFragment] = []

    for group in root:
        if _local_name(group.tag) != "g":
            continue
        match = PEN_ID_RE.fullmatch(group.get("id", ""))
        if not match:
            continue
        pen = int(match.group(1))
        stroke = group.get("stroke", "")
        fill = group.get("fill", "none")

        for child in group:
            if _local_name(child.tag) != "g" or child.get("data-generation") is None:
                continue
            generation = int(child.get("data-generation", "0"))

            fragment_root = ET.Element(root.tag, dict(root.attrib))
            for root_child in root:
                local = _local_name(root_child.tag)
                if local in DRAWABLE_SVG_TAGS:
                    continue
                if local == "g" and PEN_ID_RE.fullmatch(root_child.get("id", "")):
                    continue
                fragment_root.append(copy.deepcopy(root_child))
            pen_clone = ET.SubElement(fragment_root, group.tag, dict(group.attrib))
            pen_clone.append(copy.deepcopy(child))
            fragments.append(
                ContractFragment(
                    pen=pen,
                    generation=generation,
                    stroke=stroke,
                    fill=fill,
                    svg_text=ET.tostring(fragment_root, encoding="unicode"),
                )
            )
    return fragments


def _read_contract_fragment(
    fragment: ContractFragment,
    *,
    quantization: float,
) -> tuple[Any, float, float]:
    vpype = _require_vpype()
    lines, width, height = vpype.read_svg(
        io.StringIO(fragment.svg_text), quantization=quantization, crop=True
    )
    return lines, float(width), float(height)


def _line_collection_empty(lines: Any) -> bool:
    empty = getattr(lines, "is_empty", None)
    if empty is not None:
        return bool(empty() if callable(empty) else empty)
    return len(lines) == 0


def _append_paths(parent: ET.Element, lines: Iterable[Sequence[complex]]) -> int:
    count = 0
    for line in lines:
        if len(line) < 2:
            continue
        points = [complex(point) for point in line]
        d = "M " + " L ".join(f"{point.real:.4f},{point.imag:.4f}" for point in points)
        ET.SubElement(parent, f"{{{SVG_NS}}}path", {"d": d})
        count += 1
    return count


def _new_root(sheet_name: str, width_px: float, height_px: float) -> ET.Element:
    width_mm, height_mm = SHEET_SIZES_MM[sheet_name]
    return ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": f"{width_mm:g}mm",
            "height": f"{height_mm:g}mm",
            "viewBox": f"0 0 {width_px:.6f} {height_px:.6f}",
            LAYOUT_MARKER_ATTRIBUTE: LAYOUT_MARKER_VALUE,
            "data-plotter-workflow-page-size": sheet_name,
            "data-plotter-workflow-orientation": "landscape",
            "data-imposition-layout": LAYOUT_NAME,
        },
    )


def render_booklet(
    entries: Sequence[PageEntry],
    output: Path,
    *,
    sheet_name: str,
    quantization_mm: float,
    write_guides: bool,
    overwrite: bool,
) -> tuple[Path, Path, Path | None]:
    if sheet_name not in SHEET_SIZES_MM:
        raise ImpositionError(f"Unsupported sheet size: {sheet_name}")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output}. Use --overwrite to replace it.")

    mode, manifest = _inspect_sources(entries)
    catalog = manifest.layers if manifest is not None else ()
    manifest_hash = hashlib.sha256(manifest.path.read_bytes()).hexdigest() if manifest else None
    width_mm, height_mm = SHEET_SIZES_MM[sheet_name]
    width_px = _mm_to_px(width_mm)
    height_px = _mm_to_px(height_mm)
    cell_width = width_px / 4.0
    cell_height = height_px / 2.0
    quantization = _mm_to_px(quantization_mm)

    root = _new_root(sheet_name, width_px, height_px)
    rendered_pages: list[RenderedPage] = []
    logical_groups: dict[str, ET.Element] = {}
    if mode == "neutral":
        root.set("data-viz-layer-contract", NEUTRAL_CONTRACT)
        for layer in catalog:
            logical_groups[layer.id] = ET.Element(f"{{{SVG_NS}}}g", {
                "data-viz-layer-id": layer.id,
                "data-viz-layer-ordinal": str(layer.ordinal),
                "data-viz-layer-label": layer.label,
            })

    # Generic sources collapse to one logical plotter layer.
    generic_group: ET.Element | None = None
    if mode == "generic":
        generic_group = ET.SubElement(
            root,
            f"{{{SVG_NS}}}g",
            {"id": "content", "fill": "none", "stroke": "#000000"},
        )

    pen_groups: dict[int, ET.Element] = {}
    pen_generations: dict[int, list[int]] = {}
    pen_metadata: dict[int, PenMetadata] = {}
    total_path_count = 0

    def append_neutral(layer_id: str, geometry: _NeutralGeometry, entry: PageEntry, page: int):
        nonlocal total_path_count
        if _line_collection_empty(geometry.lines):
            return
        page_group = ET.SubElement(logical_groups[layer_id], f"{{{SVG_NS}}}g", {
            "data-imposed-page": str(page), "data-source": entry.source.name,
        })
        page_group.append(geometry.svg)
        total_path_count += len(geometry.lines)

    def append_contract_fragment(
        fragment: ContractFragment,
        lines: Any,
        *,
        logical_page: int,
        source_name: str,
    ) -> None:
        nonlocal total_path_count
        if _line_collection_empty(lines):
            return
        metadata = PenMetadata(fragment.stroke, fragment.fill)
        previous = pen_metadata.get(fragment.pen)
        if previous is not None and previous != metadata:
            raise ImpositionError(
                f"Logical pen-{fragment.pen} has inconsistent stroke/fill metadata across sources."
            )
        pen_metadata[fragment.pen] = metadata
        if fragment.pen not in pen_groups:
            pen_groups[fragment.pen] = ET.Element(
                f"{{{SVG_NS}}}g",
                {
                    "id": f"pen-{fragment.pen}",
                    "data-pen": str(fragment.pen),
                    "fill": fragment.fill,
                    "stroke": fragment.stroke,
                },
            )
            pen_generations[fragment.pen] = []

        generation_group = ET.SubElement(
            pen_groups[fragment.pen],
            f"{{{SVG_NS}}}g",
            {
                "data-generation": str(fragment.generation),
                "data-imposed-page": str(logical_page),
                "data-source": source_name,
            },
        )
        path_count = _append_paths(generation_group, lines)
        if path_count == 0:
            pen_groups[fragment.pen].remove(generation_group)
            return
        pen_generations[fragment.pen].append(fragment.generation)
        total_path_count += path_count

    for entry in entries:
        margin = _mm_to_px(entry.margin_mm)
        gutter = _mm_to_px(entry.gutter_mm)

        if len(entry.pages) == 1:
            page = entry.pages[0]
            if mode == "generic":
                assert generic_group is not None
                lines, source_width, source_height = _read_generic(
                    entry.source, quantization=quantization
                )
                _render_single(
                    lines,
                    source_width,
                    source_height,
                    page=page,
                    cell_width=cell_width,
                    cell_height=cell_height,
                    margin=margin,
                    fit=entry.fit,
                )
                total_path_count += _append_paths(generic_group, lines)
            elif mode == "neutral":
                for layer_id, geometry, source_width, source_height in _neutral_fragments(
                    entry.source, page, quantization
                ):
                    _render_single(
                        geometry, source_width, source_height, page=page,
                        cell_width=cell_width, cell_height=cell_height,
                        margin=margin, fit=entry.fit,
                    )
                    append_neutral(layer_id, geometry, entry, page)
            else:
                for fragment in _contract_fragments(entry.source):
                    lines, source_width, source_height = _read_contract_fragment(
                        fragment, quantization=quantization
                    )
                    _render_single(
                        lines,
                        source_width,
                        source_height,
                        page=page,
                        cell_width=cell_width,
                        cell_height=cell_height,
                        margin=margin,
                        fit=entry.fit,
                    )
                    append_contract_fragment(
                        fragment,
                        lines,
                        logical_page=page,
                        source_name=entry.source.name,
                    )

            row, column, rotation = POCKETMOD8_CELLS[page]
            rendered_pages.append(
                RenderedPage(
                    page=page,
                    source=entry.source.name,
                    source_part="full",
                    row=row,
                    column=column,
                    rotation_degrees=rotation,
                    fit=entry.fit,
                    margin_mm=entry.margin_mm,
                    gutter_mm=0.0,
                )
            )
            continue

        # A double-wide source is fitted once, then split into its logical left
        # and right pages. This keeps the same scale and center on both halves.
        for half_index, page in enumerate(entry.pages):
            half = "left" if half_index == 0 else "right"
            if mode == "generic":
                assert generic_group is not None
                lines, source_width, source_height = _read_generic(
                    entry.source, quantization=quantization
                )
                _render_spread_half(
                    lines,
                    source_width,
                    source_height,
                    page=page,
                    half=half,
                    cell_width=cell_width,
                    cell_height=cell_height,
                    margin=margin,
                    gutter=gutter,
                    fit=entry.fit,
                )
                total_path_count += _append_paths(generic_group, lines)
            elif mode == "neutral":
                for layer_id, geometry, source_width, source_height in _neutral_fragments(
                    entry.source, page, quantization
                ):
                    _render_spread_half(
                        geometry, source_width, source_height, page=page, half=half,
                        cell_width=cell_width, cell_height=cell_height,
                        margin=margin, gutter=gutter, fit=entry.fit,
                    )
                    append_neutral(layer_id, geometry, entry, page)
            else:
                for fragment in _contract_fragments(entry.source):
                    lines, source_width, source_height = _read_contract_fragment(
                        fragment, quantization=quantization
                    )
                    _render_spread_half(
                        lines,
                        source_width,
                        source_height,
                        page=page,
                        half=half,
                        cell_width=cell_width,
                        cell_height=cell_height,
                        margin=margin,
                        gutter=gutter,
                        fit=entry.fit,
                    )
                    append_contract_fragment(
                        fragment,
                        lines,
                        logical_page=page,
                        source_name=entry.source.name,
                    )

            row, column, rotation = POCKETMOD8_CELLS[page]
            rendered_pages.append(
                RenderedPage(
                    page=page,
                    source=entry.source.name,
                    source_part=half,
                    row=row,
                    column=column,
                    rotation_degrees=rotation,
                    fit=entry.fit,
                    margin_mm=entry.margin_mm,
                    gutter_mm=entry.gutter_mm,
                )
            )

    if total_path_count == 0:
        raise ImpositionError("Booklet sources produced no plottable vector paths.")

    if mode == "pen-contract":
        for pen in sorted(pen_groups):
            generations = pen_generations[pen]
            if not generations:
                continue
            pen_groups[pen].set("data-generations", ",".join(map(str, generations)))
            root.append(pen_groups[pen])
    elif mode == "neutral":
        for group in logical_groups.values():
            if len(group):
                root.append(group)

    output.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)

    if mode == "pen-contract":
        # Assert that the artifact still satisfies the downstream contract.
        inspect_pen_layer_contract(output)
    elif mode == "neutral":
        inspect_svg_contract(output, catalog=catalog)

    audit_path = output.with_suffix(".imposition.json")
    audit_payload = {
        "schema_version": 1,
        "layout": LAYOUT_NAME,
        "source_mode": mode,
        "source_directory": str(entries[0].source.parent.name),
        "sheet": {
            "name": sheet_name,
            "orientation": "landscape",
            "width_mm": width_mm,
            "height_mm": height_mm,
            "columns": 4,
            "rows": 2,
        },
        "converter_contract": {
            "svg_root_attribute": LAYOUT_MARKER_ATTRIBUTE,
            "svg_root_value": LAYOUT_MARKER_VALUE,
            "requires_preserved_layout": True,
        },
        "pages": [asdict(page) for page in sorted(rendered_pages, key=lambda item: item.page)],
    }
    if manifest is not None:
        audit_payload.update({
            "logical_layer_contract": NEUTRAL_CONTRACT,
            "source_manifest_path": manifest.path.as_posix(),
            "source_manifest_sha256": manifest_hash,
            "logical_layers": manifest.raw["logical_layers"],
            "logical_layer_ids": [layer_id for layer_id, group in logical_groups.items() if len(group)],
        })
    audit_path.write_text(json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8")

    guides_path: Path | None = None
    if write_guides:
        guides_path = output.with_name(f"{output.stem}.guides.svg")
        if guides_path.exists() and not overwrite:
            raise FileExistsError(
                f"Guide output already exists: {guides_path}. Use --overwrite to replace it."
            )
        write_guide_svg(guides_path, sheet_name=sheet_name)

    return output, audit_path, guides_path


def _guide_path(parent: ET.Element, points: Sequence[tuple[float, float]]) -> None:
    d = "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in points)
    ET.SubElement(parent, f"{{{SVG_NS}}}path", {"d": d})


def write_guide_svg(path: Path, *, sheet_name: str) -> Path:
    width_mm, height_mm = SHEET_SIZES_MM[sheet_name]
    width = _mm_to_px(width_mm)
    height = _mm_to_px(height_mm)
    root = _new_root(sheet_name, width, height)
    root.set("data-imposition-artifact", "fold-cut-guides")

    pen = ET.SubElement(
        root,
        f"{{{SVG_NS}}}g",
        {
            "id": "pen-1",
            "data-pen": "1",
            "data-generations": "1,2",
            "fill": "none",
            "stroke": "#000000",
        },
    )
    fold = ET.SubElement(
        pen,
        f"{{{SVG_NS}}}g",
        {"data-generation": "1", "data-guide-kind": "fold"},
    )
    for x in (width / 4.0, width / 2.0, 3.0 * width / 4.0):
        _guide_path(fold, [(x, 0.0), (x, height)])
    _guide_path(fold, [(0.0, height / 2.0), (width / 4.0, height / 2.0)])
    _guide_path(fold, [(3.0 * width / 4.0, height / 2.0), (width, height / 2.0)])

    cut = ET.SubElement(
        pen,
        f"{{{SVG_NS}}}g",
        {"data-generation": "2", "data-guide-kind": "cut"},
    )
    _guide_path(cut, [(width / 4.0, height / 2.0), (3.0 * width / 4.0, height / 2.0)])

    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    inspect_pen_layer_contract(path)
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_dir",
        help="Book source directory, or a subdirectory name under repository input/.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional JSON manifest. Defaults to <input_dir>/booklet.json when present.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output imposed SVG. Default: output/<input-dir-name>.imposed.svg",
    )
    parser.add_argument(
        "--sheet-size",
        choices=tuple(SHEET_SIZES_MM),
        default="letter",
        help="Landscape sheet size. Default: letter.",
    )
    parser.add_argument(
        "--fit",
        choices=tuple(sorted(FIT_MODES)),
        default="contain",
        help="Default source fit mode. Default: contain.",
    )
    parser.add_argument(
        "--page-margin-mm",
        type=float,
        default=4.0,
        help="Default logical page margin in millimetres. Default: 4.",
    )
    parser.add_argument(
        "--gutter-mm",
        type=float,
        default=0.0,
        help="Default crop gap at the center of double-wide spreads. Default: 0.",
    )
    parser.add_argument(
        "--quantization-mm",
        type=float,
        default=0.1,
        help="Maximum vpype segment size while reading curves. Default: 0.1mm.",
    )
    parser.add_argument(
        "--guides",
        action="store_true",
        help="Also write a separate fold/cut guide SVG.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing imposed/guide outputs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.page_margin_mm < 0 or args.gutter_mm < 0 or args.quantization_mm <= 0:
            raise ImpositionError("Margins/gutter must be non-negative and quantization must be positive.")

        input_dir = resolve_input_dir(args.input_dir)
        manifest = args.manifest
        if manifest is None:
            candidate = input_dir / "booklet.json"
            manifest = candidate if candidate.is_file() else None
        elif not manifest.is_absolute():
            direct = manifest.expanduser()
            manifest = direct if direct.is_file() else input_dir / manifest
        if manifest is not None:
            manifest = manifest.expanduser().resolve()
            if not manifest.is_file():
                raise ImpositionError(f"Manifest does not exist: {manifest}")
            entries = load_manifest(
                input_dir,
                manifest,
                default_fit=args.fit,
                default_margin_mm=args.page_margin_mm,
                default_gutter_mm=args.gutter_mm,
            )
        else:
            entries = discover_automatic_pages(
                input_dir,
                fit=args.fit,
                margin_mm=args.page_margin_mm,
            )

        output = args.output
        if output is None:
            output = REPO_ROOT / "output" / f"{input_dir.name}.imposed.svg"
        else:
            output = output.expanduser()
            if not output.is_absolute():
                output = (Path.cwd() / output).resolve()
        if output.suffix.lower() != ".svg":
            raise ImpositionError("--output must use the .svg extension.")

        imposed, audit, guides = render_booklet(
            entries,
            output,
            sheet_name=args.sheet_size,
            quantization_mm=args.quantization_mm,
            write_guides=args.guides,
            overwrite=args.overwrite,
        )
    except (ImpositionError, PenLayerContractError, FileExistsError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(imposed)
    print(audit)
    if guides is not None:
        print(guides)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
