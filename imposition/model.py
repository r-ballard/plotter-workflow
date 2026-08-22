"""Minimal shared data model for physical SVG imposition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

Point = tuple[float, float]
Polygon = tuple[Point, ...]
FitMode = Literal["contain", "cover"]
SheetOrientation = Literal["landscape", "portrait"]
OrientationPolicy = Literal[
    "explicit-override",
    "intrinsic-up-vector",
    "legacy-default",
]


@dataclass(frozen=True)
class SheetSpec:
    """Resolved physical sheet dimensions used by an imposition object."""

    name: str
    width_mm: float
    height_mm: float
    orientation: SheetOrientation


@dataclass(frozen=True)
class OrientationFrame:
    """Semantic two-dimensional orientation independent of polygon geometry.

    ``up_vector`` is sufficient for rotation-only placement. ``right_vector`` is
    optional and, when present on both source and target frames, lets the
    resolver detect handedness/reflection mismatches. ``anchor`` identifies the
    source geometric feature carrying the semantic orientation (for example
    ``vertex:0`` or ``edge:1``) without constraining the vector direction.
    """

    up_vector: Point
    right_vector: Point | None = None
    anchor: str | None = None


@dataclass(frozen=True)
class OrientationTarget:
    """Semantic reading frame expected for artwork placed in a slot."""

    up_vector: Point
    validation: str | None = None
    right_vector: Point | None = None

    @property
    def frame(self) -> OrientationFrame:
        """Return the target as a general orientation frame."""

        return OrientationFrame(
            up_vector=self.up_vector,
            right_vector=self.right_vector,
        )


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

    @property
    def orientation_frame(self) -> OrientationFrame:
        """Promote the v1 ``up_anchor``/``up_vector`` contract to a frame."""

        return OrientationFrame(
            up_vector=self.up_vector,
            anchor=self.up_anchor,
        )


@dataclass(frozen=True)
class OrientationResolution:
    """Auditable result of mapping source orientation into an imposition slot."""

    policy: OrientationPolicy
    source_up_vector: Point | None
    target_up_vector: Point
    override_degrees: float | None
    resolved_degrees: float


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
