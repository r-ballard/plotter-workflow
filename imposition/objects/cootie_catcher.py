"""Declarative geometry for the one-sheet cootie-catcher imposition."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ..model import (
    Guide,
    ObjectPlacement,
    OrientationTarget,
    Polygon,
    SheetSpec,
    Slot,
)

Q = 0.25
C = 0.5
TQ = 0.75

SUPPORTED_SHEETS: dict[str, SheetSpec] = {
    "letter": SheetSpec("letter", 279.4, 215.9, "landscape"),
    "a4": SheetSpec("a4", 297.0, 210.0, "landscape"),
    "a3": SheetSpec("a3", 420.0, 297.0, "landscape"),
    "tabloid": SheetSpec("tabloid", 431.8, 279.4, "landscape"),
}

PANEL_POLYGONS: dict[str, Polygon] = {
    "outer-1": ((0.0, 0.0), (Q, 0.0), (Q, Q), (0.0, Q)),
    "outer-2": ((TQ, 0.0), (1.0, 0.0), (1.0, Q), (TQ, Q)),
    "outer-3": ((TQ, TQ), (1.0, TQ), (1.0, 1.0), (TQ, 1.0)),
    "outer-4": ((0.0, TQ), (Q, TQ), (Q, 1.0), (0.0, 1.0)),
    "selector-1": ((Q, 0.0), (C, 0.0), (Q, Q)),
    "selector-2": ((C, 0.0), (TQ, 0.0), (TQ, Q)),
    "selector-3": ((1.0, Q), (1.0, C), (TQ, Q)),
    "selector-4": ((1.0, C), (1.0, TQ), (TQ, TQ)),
    "selector-5": ((TQ, 1.0), (C, 1.0), (TQ, TQ)),
    "selector-6": ((C, 1.0), (Q, 1.0), (Q, TQ)),
    "selector-7": ((0.0, TQ), (0.0, C), (Q, TQ)),
    "selector-8": ((0.0, C), (0.0, Q), (Q, Q)),
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

# Compatibility contract for the current physically inspected implementation.
# Rendering still uses these values until target vectors have been validated as
# the authoritative folded-reading orientation model.
LEGACY_ROTATIONS: dict[str, int] = {
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

_TARGET_UP_BY_ROTATION = {
    0: (0.0, -1.0),
    90: (1.0, 0.0),
    180: (0.0, 1.0),
    270: (-1.0, 0.0),
}


class CootieCatcherError(ValueError):
    """Raised when cootie-catcher object geometry cannot be resolved."""


def _family(slot_id: str) -> str:
    return slot_id.rsplit("-", 1)[0]


class CootieCatcher:
    """Declarative normalized geometry and construction semantics."""

    object_id = "cootie_catcher"
    schema_version = 1

    def __init__(self) -> None:
        self._slots = tuple(
            Slot(
                slot_id=slot_id,
                family=_family(slot_id),
                polygon=PANEL_POLYGONS[slot_id],
                target_orientation=OrientationTarget(
                    up_vector=_TARGET_UP_BY_ROTATION[LEGACY_ROTATIONS[slot_id]],
                    validation="provisional",
                ),
            )
            for slot_id in EXPECTED_SLOTS
        )
        self._slot_by_id = {slot.slot_id: slot for slot in self._slots}

    @property
    def slots(self) -> Sequence[Slot]:
        return self._slots

    def slot(self, slot_id: str) -> Slot:
        try:
            return self._slot_by_id[slot_id]
        except KeyError as exc:
            raise CootieCatcherError(f"Unknown cootie-catcher slot {slot_id!r}.") from exc

    def resolve_placement(
        self,
        sheet: SheetSpec,
        options: Mapping[str, object],
    ) -> ObjectPlacement:
        if sheet.orientation != "landscape":
            raise CootieCatcherError("Cootie-catcher sheets must be landscape.")
        position = str(options.get("position", "left"))
        if position not in {"left", "center", "right"}:
            raise CootieCatcherError(
                "square position must be one of ['center', 'left', 'right']."
            )

        maximum = min(sheet.width_mm, sheet.height_mm)
        raw_size = options.get("square_size_mm")
        try:
            size = maximum if raw_size is None else float(raw_size)
        except (TypeError, ValueError) as exc:
            raise CootieCatcherError("square size must be numeric.") from exc
        if not math.isfinite(size) or size <= 0:
            raise CootieCatcherError("square size must be greater than zero.")
        if size > maximum + 1e-9:
            raise CootieCatcherError(
                f"square size {size:g}mm exceeds the {maximum:g}mm maximum for {sheet.name}."
            )

        if position == "left":
            x = 0.0
        elif position == "center":
            x = (sheet.width_mm - size) / 2.0
        else:
            x = sheet.width_mm - size
        y = (sheet.height_mm - size) / 2.0
        return ObjectPlacement(
            sheet=sheet,
            x_mm=x,
            y_mm=y,
            width_mm=size,
            height_mm=size,
        )

    def guides(self, placement: ObjectPlacement) -> Sequence[Guide]:
        if not math.isclose(placement.width_mm, placement.height_mm, abs_tol=1e-9):
            raise CootieCatcherError("Cootie-catcher placement must be square.")

        x = placement.x_mm
        y = placement.y_mm
        size = placement.width_mm
        sheet = placement.sheet
        quarter = size / 4.0
        center = size / 2.0
        tolerance = 1e-7
        guides: list[Guide] = []

        trim: list[tuple[tuple[float, float], tuple[float, float]]] = []
        if x > tolerance:
            trim.append(((x, y), (x, y + size)))
        if x + size < sheet.width_mm - tolerance:
            trim.append(((x + size, y), (x + size, y + size)))
        if y > tolerance:
            trim.append(((x, y), (x + size, y)))
        if y + size < sheet.height_mm - tolerance:
            trim.append(((x, y + size), (x + size, y + size)))
        guides.extend(Guide(kind="trim", points=segment) for segment in trim)

        top = (x + center, y)
        right = (x + size, y + center)
        bottom = (x + center, y + size)
        left = (x, y + center)
        guides.append(
            Guide(kind="first-blintz", points=(top, right, bottom, left), closed=True)
        )

        nw = (x + quarter, y + quarter)
        ne = (x + 3 * quarter, y + quarter)
        se = (x + 3 * quarter, y + 3 * quarter)
        sw = (x + quarter, y + 3 * quarter)
        guides.append(
            Guide(kind="second-blintz", points=(nw, ne, se, sw), closed=True)
        )

        guides.extend(
            [
                Guide(kind="center-prefold", points=((x, y), (x + size, y + size))),
                Guide(kind="center-prefold", points=((x + size, y), (x, y + size))),
                Guide(
                    kind="center-prefold",
                    points=((x, y + center), (x + size, y + center)),
                ),
                Guide(
                    kind="center-prefold",
                    points=((x + center, y), (x + center, y + size)),
                ),
            ]
        )
        return tuple(guides)


COOTIE_CATCHER = CootieCatcher()
