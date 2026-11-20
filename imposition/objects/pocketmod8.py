"""Declarative one-sheet eight-page booklet geometry and reading semantics."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..model import Guide, ObjectPlacement, OrientationTarget, SheetSpec, Slot

SHEET_SIZES_MM = {
    "letter": (279.4, 215.9),
    "a4": (297.0, 210.0),
    "a3": (420.0, 297.0),
    "tabloid": (431.8, 279.4),
}
SUPPORTED_SHEETS = {
    name: SheetSpec(name, w, h, "landscape") for name, (w, h) in SHEET_SIZES_MM.items()
}

# Row 0 is the top of the flat SVG; angles are clockwise.
POCKETMOD8_CELLS = {
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


@dataclass(frozen=True)
class PocketMod8:
    object_id = "pocketmod8"
    schema_version = 1

    @property
    def facing_spreads(self) -> tuple[tuple[int, int], ...]:
        return tuple(sorted(ALLOWED_SPREADS))

    def cell(self, page: int) -> tuple[int, int, int]:
        if type(page) is not int or page not in POCKETMOD8_CELLS:
            raise ValueError("page must be an integer from 1 through 8")
        return POCKETMOD8_CELLS[page]

    @property
    def slots(self) -> tuple[Slot, ...]:
        slots = []
        for page in range(1, 9):
            row, col, rotation = self.cell(page)
            up = (0, 1) if rotation else (0, -1)
            right = (-1, 0) if rotation else (1, 0)
            slots.append(
                Slot(
                    f"page-{page}",
                    "booklet-page",
                    (
                        (col / 4, row / 2),
                        ((col + 1) / 4, row / 2),
                        ((col + 1) / 4, (row + 1) / 2),
                        (col / 4, (row + 1) / 2),
                    ),
                    OrientationTarget(
                        up, validation="legacy-layout", right_vector=right
                    ),
                )
            )
        return tuple(slots)

    def resolve_placement(
        self, sheet: SheetSpec, options: Mapping[str, object]
    ) -> ObjectPlacement:
        if options:
            raise ValueError(
                "PocketMod8 uses the full sheet; no placement options are supported"
            )
        if sheet.orientation != "landscape":
            raise ValueError("PocketMod8 sheets must use landscape orientation")
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or v <= 0
            for v in (sheet.width_mm, sheet.height_mm)
        ):
            raise ValueError("sheet dimensions must be finite and positive")
        return ObjectPlacement(sheet, 0, 0, sheet.width_mm, sheet.height_mm)

    @staticmethod
    def cell_size(placement: ObjectPlacement) -> tuple[float, float]:
        return placement.width_mm / 4, placement.height_mm / 2

    def place_in_cell(
        self, geometry: Any, page: int, cell_width: float, cell_height: float
    ) -> None:
        """Apply the legacy operation order to vector or neutral SVG geometry."""
        row, col, rotation = self.cell(page)
        if rotation == 180:
            geometry.scale(-1.0, -1.0)
            geometry.translate(cell_width, cell_height)
        geometry.translate(col * cell_width, row * cell_height)

    def guides(self, placement: ObjectPlacement) -> tuple[Guide, ...]:
        expected = self.resolve_placement(placement.sheet, {})
        if placement != expected:
            raise ValueError("PocketMod8 guides require its full-sheet placement")
        w, h = placement.width_mm, placement.height_mm
        return tuple(
            Guide("fold", ((x, 0), (x, h))) for x in (w / 4, w / 2, 3 * w / 4)
        ) + (
            Guide("fold", ((0, h / 2), (w / 4, h / 2))),
            Guide("fold", ((3 * w / 4, h / 2), (w, h / 2))),
            Guide("cut", ((w / 4, h / 2), (3 * w / 4, h / 2))),
        )


POCKETMOD8 = PocketMod8()
