"""Minimal shared data model for physical SVG imposition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

Point = tuple[float, float]
Polygon = tuple[Point, ...]
FitMode = Literal["contain", "cover"]
SheetOrientation = Literal["landscape", "portrait"]


@dataclass(frozen=True)
class SheetSpec:
    """Resolved physical sheet dimensions used by an imposition object."""

    name: str
    width_mm: float
    height_mm: float
    orientation: SheetOrientation


@dataclass(frozen=True)
class OrientationTarget:
    """Semantic reading direction expected for artwork placed in a slot."""

    up_vector: Point
    validation: str | None = None


@dataclass(frozen=True)
class Slot:
    """Stable semantic region in normalized object coordinates."""

    slot_id: str
    family: str
    polygon: Polygon
    target_orientation: OrientationTarget
    default_fit: FitMode = "contain"


@dataclass(frozen=True)
class Guide:
    """Object-owned construction geometry emitted separately from artwork."""

    kind: str
    points: tuple[Point, ...]
    closed: bool = False


@dataclass(frozen=True)
class ObjectPlacement:
    """Physical placement of a normalized object on a resolved sheet, in millimetres."""

    sheet: SheetSpec
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class IntrinsicCanvas:
    """Semantic source-canvas metadata declared by ``viz-virtualserver`` SVGs."""

    version: int
    shape: str
    coordinate_system: str
    polygon: Polygon
    up_anchor: str
    up_vector: Point
    clip_id: str | None = None


class ImpositionObject(Protocol):
    """Minimal protocol for declarative physical imposition objects."""

    object_id: str
    schema_version: int

    @property
    def slots(self) -> Sequence[Slot]: ...

    def resolve_placement(
        self,
        sheet: SheetSpec,
        options: Mapping[str, object],
    ) -> ObjectPlacement: ...

    def guides(self, placement: ObjectPlacement) -> Sequence[Guide]: ...
