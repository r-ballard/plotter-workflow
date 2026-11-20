"""Resolved intrinsic canvases and assembled artwork layouts, in SVG pixels."""

import math
import re
from dataclasses import dataclass
from types import MappingProxyType

MM_TO_PX = 96.0 / 25.4
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _freeze(value):
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError("layout metadata keys must be strings")
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("layout metadata must be finite JSON data")


def _thaw(value):
    from collections.abc import Mapping

    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def finite(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be finite numeric data")
    return float(value)


def rect(x0, y0, x1, y1):
    if x1 <= x0 or y1 <= y0:
        raise ValueError("crop or canvas is collapsed")
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def bounds(polygon):
    return (
        min(x for x, y in polygon),
        min(y for x, y in polygon),
        max(x for x, y in polygon),
        max(y for x, y in polygon),
    )


def affine(matrix, point):
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def checked_matrix(value):
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        raise ValueError("matrix requires six values")
    v = tuple(finite(c, "matrix") for c in value)
    a, b, c, d, _e, _f = v
    det = a * d - b * c
    if not math.isfinite(det) or det == 0:
        raise ValueError("matrix must be invertible")
    inv = (d / det, -b / det, -c / det, a / det)
    norm = max(abs(a) + abs(c), abs(b) + abs(d))
    inverse_norm = max(abs(inv[0]) + abs(inv[2]), abs(inv[1]) + abs(inv[3]))
    if not math.isfinite(norm * inverse_norm) or norm * inverse_norm > 1e10:
        raise ValueError("unsafe matrix precision")
    return v


@dataclass(frozen=True)
class PanelLayout:
    panel_id: str
    canvas_polygon: tuple
    crop_polygon: tuple
    assembled_matrix: tuple
    binding: object

    def __post_init__(self):
        if not isinstance(self.panel_id, str) or not ID_RE.fullmatch(self.panel_id):
            raise ValueError("invalid panel ID")
        for name in ("canvas_polygon", "crop_polygon"):
            raw = getattr(self, name)
            if not isinstance(raw, (list, tuple)) or not 3 <= len(raw) <= 64:
                raise ValueError("canvas/crop requires 3..64 vertices")
            if any(not isinstance(p, (tuple, list)) or len(p) != 2 for p in raw):
                raise ValueError("invalid polygon point")
            polygon = tuple(tuple(finite(c, name) for c in p) for p in raw)
            if name == "canvas_polygon" and polygon != rect(*bounds(polygon)):
                raise ValueError("canvas corners must be ordered rectangular points")
            if name == "crop_polygon":
                # A consistent strict turn at every edge excludes degenerate,
                # concave and self-intersecting crops (check all other vertices).
                for i, a in enumerate(polygon):
                    b = polygon[(i + 1) % len(polygon)]
                    crosses = [
                        (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
                        for j, p in enumerate(polygon)
                        if j not in (i, (i + 1) % len(polygon))
                    ]
                    if not (all(v > 0 for v in crosses) or all(v < 0 for v in crosses)):
                        raise ValueError("crop must be strictly convex")
            object.__setattr__(self, name, polygon)
        cx0, cy0, cx1, cy1 = bounds(self.canvas_polygon)
        x0, y0, x1, y1 = bounds(self.crop_polygon)
        if not (cx0 <= x0 < x1 <= cx1 and cy0 <= y0 < y1 <= cy1):
            raise ValueError("crop lies outside canvas")
        object.__setattr__(
            self, "assembled_matrix", checked_matrix(self.assembled_matrix)
        )
        object.__setattr__(self, "binding", _freeze(dict(self.binding)))


@dataclass(frozen=True)
class ArtworkLayout:
    profile_id: str
    units: str
    window: tuple
    panels: tuple
    validation_status: str
    settings: object

    def __post_init__(self):
        if not ID_RE.fullmatch(self.profile_id) or self.units != "svg-px":
            raise ValueError("invalid layout profile/units")
        if self.validation_status not in ("provisional", "validated"):
            raise ValueError("invalid validation status")
        if len(self.window) != 4:
            raise ValueError("window requires x,y,width,height")
        x, y, w, h = tuple(finite(v, "window") for v in self.window)
        if min(w, h) <= 0 or max(abs(x), abs(y), w, h) > 1e7:
            raise ValueError("window exceeds dimension limits")
        if x + w <= x or y + h <= y:
            raise ValueError("window cannot be represented")
        if (
            not self.panels
            or len(self.panels) > 1000
            or len({p.panel_id for p in self.panels}) != len(self.panels)
        ):
            raise ValueError("invalid panel count/identity")
        for p in self.panels:
            for q in p.crop_polygon:
                px, py = affine(p.assembled_matrix, q)
                if not (x <= px <= x + w and y <= py <= y + h):
                    raise ValueError("panel crop outside layout window")
        object.__setattr__(self, "window", (x, y, w, h))
        object.__setattr__(self, "panels", tuple(self.panels))
        object.__setattr__(self, "settings", _freeze(dict(self.settings)))


def resolve_booklet_spread(*, sheet_size, pages, margin_mm, gutter_mm):
    """Compatibility entry point for object-backed reading-spread composition."""
    from .booklet_artwork import resolve_booklet_spread as resolve

    return resolve(
        sheet_size=sheet_size, pages=pages, margin_mm=margin_mm, gutter_mm=gutter_mm
    )


def layout_dict(layout):
    return {
        "profile_id": layout.profile_id,
        "units": layout.units,
        "window": list(layout.window),
        "validation_status": layout.validation_status,
        "settings": dict(layout.settings),
        "panels": [
            {
                "panel_id": p.panel_id,
                "canvas_polygon": p.canvas_polygon,
                "crop_polygon": p.crop_polygon,
                "assembled_matrix": p.assembled_matrix,
                "binding": dict(p.binding),
            }
            for p in layout.panels
        ],
    }


def parse_layout(value):
    expected = {
        "profile_id",
        "units",
        "window",
        "validation_status",
        "settings",
        "panels",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("invalid layout fields")
    panels = tuple(PanelLayout(**p) for p in value["panels"])
    return ArtworkLayout(**{**value, "panels": panels})
