"""Immutable native artwork fragments and shared viewport/retained-work checks."""

import copy
import hashlib
import io
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from scripts import booklet_impose as booklet

from .artwork_layout import MM_TO_PX


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class NativeFragment:
    layer_id: str
    panel_id: str
    svg_bytes: bytes
    vertices: int


@dataclass(frozen=True)
class PreparedNativeFace:
    profile: str
    face: str
    width_mm: float
    height_mm: float
    catalog: tuple
    fragments: tuple
    panel_audit: tuple
    provenance: object


def _validate_viewport(source, expected):
    root = ET.parse(source).getroot()
    try:
        width, height = float(root.get("width", "")), float(root.get("height", ""))
        view = tuple(float(v) for v in root.get("viewBox", "").split())
    except ValueError as exc:
        raise ValueError(
            "Source viewport requires canonical native pixel dimensions"
        ) from exc
    x0, y0, x1, y1 = expected
    want = (x0, y0, x1 - x0, y1 - y0)
    if (
        len(view) != 4
        or not all(math.isfinite(v) for v in (width, height, *view))
        or abs(width - want[2]) / MM_TO_PX > 1e-6
        or abs(height - want[3]) / MM_TO_PX > 1e-6
        or any(abs(a - b) / MM_TO_PX > 1e-6 for a, b in zip(view, want))
    ):
        raise ValueError("Source viewport differs from exact panel size")


def _retained_vertices(geometry, width, height):
    """Count copied paths, including off-viewport and definition geometry.

    Presence lines have already been cropped. The XML retains the full paths,
    so counting those lines alone would undercharge repeated output copies.
    This separate count does not change the artwork or its clipping.
    """
    namespace = f"{{{booklet.SVG_NS}}}"
    root = ET.Element(namespace + "svg", width=str(width), height=str(height))
    fragment = copy.deepcopy(geometry.svg)
    for node in fragment.iter():
        if node.tag.rsplit("}", 1)[-1] in ("defs", "clipPath"):
            node.tag = namespace + "g"
        for key in ("clip-path", "display", "visibility", "opacity", "style"):
            node.attrib.pop(key, None)
    root.append(fragment)
    lines, _, _ = booklet._require_vpype().read_svg(
        io.StringIO(ET.tostring(root, encoding="unicode")),
        quantization=0.05 * MM_TO_PX,
        crop=False,
    )
    return max(
        sum(len(line) for line in lines), sum(len(line) for line in geometry.lines)
    )
