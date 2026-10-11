"""One immutable physical plan model for all supported SVG input contracts."""

from dataclasses import dataclass

from pen_force import ForceSpec

SCHEMA_VERSION = 3
RESOLVED_KIND = 'resolved-dpx3300-plot-pass'


class PenPlanError(ValueError):
    pass


@dataclass(frozen=True)
class LayerInfo:
    id: str
    active: bool
    ordinal: int


@dataclass(frozen=True)
class SlotSpec:
    slot: int
    tool: str | None = None
    color: str | None = None
    label: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class Assignment:
    layer_ids: tuple[str, ...]
    physical_slot: int


@dataclass(frozen=True)
class PassSpec:
    id: str
    assignments: tuple[Assignment, ...]


@dataclass(frozen=True)
class PenPlanSpec:
    policy: str
    passes: tuple[PassSpec, ...] = ()
    slots: tuple[SlotSpec, ...] = ()
    omitted_layers: tuple[str, ...] = ()
    repeated_layers: tuple[str, ...] = ()
    pen_force: ForceSpec | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ForceAudit:
    spec: ForceSpec
    effective_slot_forces: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ResolvedPlotPass:
    source_svg: str
    source_svg_sha256: str
    source_manifest_hash: str | None
    pass_id: str
    pass_number: int
    pass_count: int
    policy: str
    assignments: tuple[Assignment, ...]
    physical_slots: tuple[int, ...]
    omitted_layers: tuple[str, ...]
    repeated_layers: tuple[str, ...]
    slots: tuple[SlotSpec, ...]
    hpgl_sha256: str
    pen_force: ForceAudit | None
