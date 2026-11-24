"""Count-parameterized net using the supplied reference's face proportions.

Coordinates use horizontal half-segment = 2, vertical half-edge = 1.
The net and folded reading frames remain provisional pending a paper fold.
"""

import math
from dataclasses import dataclass
from functools import cached_property

from ..geometry import map_normalized_polygon
from ..model import Guide, ObjectPlacement, OrientationTarget, Slot


def _positive(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")  # noqa: TRY004 -- shared geometry API
    if not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


@dataclass(frozen=True)
class Kaleidocycle:
    tetrahedron_count: int = 6
    object_id = "kaleidocycle"
    schema_version = 1
    net_height = 5.0

    def __post_init__(self):
        n = self.tetrahedron_count
        if type(n) is not int or n < 6 or n % 2:
            raise ValueError("tetrahedron_count must be an even integer >= 6")

    @property
    def net_width(self):
        return 2 * self.tetrahedron_count + 0.35

    @property
    def aspect_ratio(self):
        return self.net_width / self.net_height

    def normalize(self, polygon):
        return tuple(((x + 0.35) / self.net_width, y / 5) for x, y in polygon)

    @cached_property
    def slots(self):
        result = []
        for column in range(self.tetrahedron_count):
            x = column * 2
            if column % 2 == 0:
                triangles = [
                    ((x, y), (x + 2, y + 1), (x, y + 2))
                    if face % 2 == 0
                    else ((x + 2, y), (x + 2, y + 2), (x, y + 1))
                    for face, y in enumerate(range(4))
                ]
            else:
                triangles = [
                    ((x + 2, y), (x + 2, y + 2), (x, y + 1))
                    if face % 2 == 0
                    else ((x, y), (x + 2, y + 1), (x, y + 2))
                    for face, y in enumerate(range(4))
                ]
            for state, polygon in zip("ABCD", triangles):
                result.append(
                    Slot(
                        f"column-{column + 1}-{state.lower()}",
                        state,
                        self.normalize(polygon),
                        OrientationTarget((0, -1), "provisional", (1, 0)),
                    )
                )
        return tuple(result)

    def local_polygon(self, slot_id, width_mm):
        slot = next((s for s in self.slots if s.slot_id == slot_id), None)
        if slot is None:
            raise ValueError("unknown kaleidocycle slot")
        width = _positive(width_mm, "width_mm")
        height = width / self.aspect_ratio
        x0 = min(x for x, y in slot.polygon)
        y0 = min(y for x, y in slot.polygon)
        return tuple(((x - x0) * width, (y - y0) * height) for x, y in slot.polygon)

    def resolve_placement(self, sheet, options):
        if set(options) - {"width_mm", "margin_mm", "position"}:
            raise ValueError("unknown kaleidocycle placement option")
        sw = _positive(sheet.width_mm, "sheet width")
        sh = _positive(sheet.height_mm, "sheet height")
        margin = _positive(options.get("margin_mm", 5), "margin_mm", zero=True)
        maximum = min(sw - 2 * margin, (sh - 2 * margin) * self.aspect_ratio)
        width = _positive(options.get("width_mm", maximum), "width_mm")
        if width > maximum + 1e-9:
            raise ValueError("kaleidocycle does not fit sheet with margins")
        height = width / self.aspect_ratio
        position = options.get("position", "center")
        if position not in ("center", "top-left"):
            raise ValueError("position must be center or top-left")
        if position == "top-left":
            return ObjectPlacement(sheet, margin, margin, width, height)
        return ObjectPlacement(
            sheet, (sw - width) / 2, (sh - height) / 2, width, height
        )

    @property
    def glue_polygons(self):
        top = [
            ((4 * i, 0), (4 * i + 4, 0), (4 * i + 2, 1))
            for i in range(self.tetrahedron_count // 2)
        ]
        ends = [
            ((0, y), (-0.35, y + 0.2), (-0.35, y + 1.8), (0, y + 2)) for y in (0, 2)
        ]
        return tuple(self.normalize(p) for p in top + ends)

    def guides(self, placement):
        if not math.isclose(
            placement.width_mm / placement.height_mm, self.aspect_ratio
        ):
            raise ValueError("placement must preserve net aspect ratio")
        # All face edges, deduplicated; glue edges join the outer net boundary.
        edges = {}
        for polygon in [s.polygon for s in self.slots] + list(self.glue_polygons):
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                key = tuple(sorted((a, b)))
                edges[key] = edges.get(key, 0) + 1

        def mapped(points):
            return tuple(
                (
                    placement.x_mm + x * placement.width_mm,
                    placement.y_mm + y * placement.height_mm,
                )
                for x, y in points
            )

        result = [
            Guide("fold" if count == 2 else "cut", mapped(edge))
            for edge, count in edges.items()
        ]
        result.extend(
            Guide("glue", map_normalized_polygon(p, placement), True)
            for p in self.glue_polygons
        )
        return tuple(result)
