"""Resolve logical SVG layers to physical DPX-3300 pen slots.

The producer-facing SVG contract and the machine-facing pen assignment are kept
separate deliberately.  A logical layer may be preserved, compacted into the
lowest available slot, or explicitly assigned by a user-authored pen-plan JSON
file.  Generated HP-GL is remapped only after vpype has completed geometry and
layout processing.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from logical_layer_contract import (
    InputMode,
    LogicalLayerContract,
    LogicalLayerManifest,
    LogicalLayerMetadata,
)

MAX_DPX_PENS = 8
PEN_POLICIES = ("preserve", "compact", "explicit")
PEN_PLAN_SCHEMA_VERSION = 1
LOGICAL_PEN_PLAN_SCHEMA_VERSION = 2
PEN_PLAN_SUFFIX = ".penplan.json"
RESOLVED_PEN_PLAN_SUFFIX = ".resolved.penplan.json"
RESOLVED_PEN_PLAN_KIND = "resolved-dpx3300-pen-plan"
RESOLVED_PLOT_PASS_KIND = "resolved-dpx3300-logical-pass"
PEN_ID_RE = re.compile(r"^pen-(\d+)$")
_MANIFEST_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SP_RE = re.compile(r"SP([0-8]);", re.IGNORECASE)
_DRAWABLE_TAGS = {
    "path",
    "line",
    "polyline",
    "polygon",
    "rect",
    "circle",
    "ellipse",
}


class PenPlanError(ValueError):
    """Raised when a pen plan is incomplete, ambiguous, or unsafe."""


@dataclass(frozen=True)
class LogicalLayer:
    logical_layer: int
    active: bool
    generations: tuple[int, ...]
    preview_color: str


@dataclass(frozen=True)
class SlotSpec:
    slot: int
    tool: str | None = None
    color: str | None = None
    label: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class RequestedAssignment:
    logical_layer: int
    physical_slot: int


@dataclass(frozen=True)
class PenPlanSpec:
    schema_version: int
    policy: str
    assignments: tuple[RequestedAssignment, ...]
    slots: tuple[SlotSpec, ...]
    notes: str | None = None


@dataclass(frozen=True)
class LogicalAssignment:
    layer_ids: tuple[str, ...]
    physical_slot: int


@dataclass(frozen=True)
class PassSpec:
    id: str
    assignments: tuple[LogicalAssignment, ...]


@dataclass(frozen=True)
class LogicalPenPlanSpec:
    schema_version: int
    passes: tuple[PassSpec, ...]
    omitted_layers: tuple[str, ...]
    repeated_layers: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedLogicalAssignment:
    """A catalog-ordered logical merge assigned to one physical slot."""

    layer_ids: tuple[str, ...]
    physical_slot: int


@dataclass(frozen=True)
class ResolvedPlotPass:
    """One validated physical pass of a neutral logical-layer job."""

    id: str
    assignments: tuple[ResolvedLogicalAssignment, ...]
    omitted_layers: tuple[str, ...]
    source_manifest_hash: str


@dataclass(frozen=True)
class ResolvedAssignment:
    logical_layer: int
    physical_slot: int
    generations: tuple[int, ...]
    preview_color: str
    tool: str | None = None
    color: str | None = None
    label: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ResolvedPenPlan:
    source_svg: str
    policy: str
    logical_layers: tuple[LogicalLayer, ...]
    assignments: tuple[ResolvedAssignment, ...]
    notes: str | None = None

    @property
    def logical_pens(self) -> tuple[int, ...]:
        """Active logical SVG layers expected in vpype's initial HP-GL."""
        return tuple(item.logical_layer for item in self.assignments)

    @property
    def physical_pens(self) -> tuple[int, ...]:
        """Physical DPX slots expected after HP-GL remapping."""
        return tuple(item.physical_slot for item in self.assignments)

    @property
    def declared_logical_pens(self) -> tuple[int, ...]:
        return tuple(layer.logical_layer for layer in self.logical_layers)

    @property
    def inactive_logical_pens(self) -> tuple[int, ...]:
        return tuple(
            layer.logical_layer for layer in self.logical_layers if not layer.active
        )


def load_pen_plan(path: Path) -> PenPlanSpec | LogicalPenPlanSpec:
    """Load and validate a user-authored ``*.penplan.json`` file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PenPlanError(f"Invalid JSON in pen plan {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PenPlanError(f"Pen plan {path} must contain a JSON object")

    if "schema_version" not in raw:
        raise PenPlanError(f"Pen plan {path} requires an explicit schema_version")
    version = raw["schema_version"]
    if type(version) is not int or version not in (
        PEN_PLAN_SCHEMA_VERSION,
        LOGICAL_PEN_PLAN_SCHEMA_VERSION,
    ):
        raise PenPlanError(
            f"Pen plan {path} uses schema_version={version!r}; "
            "supported versions are 1 and 2"
        )
    if version == LOGICAL_PEN_PLAN_SCHEMA_VERSION:
        return _load_logical_pen_plan(raw)

    policy = raw.get("policy", "preserve")
    _validate_policy(policy)

    assignments_raw = raw.get("assignments", [])
    if not isinstance(assignments_raw, list):
        raise PenPlanError("pen-plan 'assignments' must be a JSON array")
    assignments: list[RequestedAssignment] = []
    for index, item in enumerate(assignments_raw):
        if not isinstance(item, dict):
            raise PenPlanError(f"assignments[{index}] must be a JSON object")
        try:
            logical = int(item["logical_layer"])
            physical = int(item["physical_slot"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PenPlanError(
                f"assignments[{index}] requires integer logical_layer and physical_slot"
            ) from exc
        _validate_pen_number(logical, label="logical_layer")
        _validate_pen_number(physical, label="physical_slot")
        assignments.append(RequestedAssignment(logical, physical))

    slots_raw = raw.get("slots", [])
    if not isinstance(slots_raw, list):
        raise PenPlanError("pen-plan 'slots' must be a JSON array")
    slots: list[SlotSpec] = []
    for index, item in enumerate(slots_raw):
        if not isinstance(item, dict):
            raise PenPlanError(f"slots[{index}] must be a JSON object")
        try:
            slot = int(item["slot"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PenPlanError(f"slots[{index}] requires an integer slot") from exc
        _validate_pen_number(slot, label="slot")
        slots.append(
            SlotSpec(
                slot=slot,
                tool=_optional_text(item.get("tool")),
                color=_optional_text(item.get("color")),
                label=_optional_text(item.get("label")),
                notes=_optional_text(item.get("notes")),
            )
        )

    _ensure_unique((item.logical_layer for item in assignments), "logical_layer")
    _ensure_unique((item.physical_slot for item in assignments), "physical_slot")
    _ensure_unique((item.slot for item in slots), "slot")

    if policy == "explicit" and not assignments:
        raise PenPlanError("explicit pen policy requires at least one assignment")
    if policy != "explicit" and assignments:
        raise PenPlanError(
            f"assignments are only valid with policy='explicit', not {policy!r}"
        )

    return PenPlanSpec(
        schema_version=version,
        policy=policy,
        assignments=tuple(assignments),
        slots=tuple(sorted(slots, key=lambda item: item.slot)),
        notes=_optional_text(raw.get("notes")),
    )


def _load_logical_pen_plan(raw: dict[str, Any]) -> LogicalPenPlanSpec:
    _reject_unknown_fields(
        raw,
        {"schema_version", "passes", "omitted_layers", "repeated_layers"},
        "pen plan",
        top_level=True,
    )
    for field in ("passes", "omitted_layers", "repeated_layers"):
        if field not in raw:
            raise PenPlanError(f"v2 pen plan requires '{field}'")

    passes_raw = _require_array(raw["passes"], "passes")
    if not passes_raw:
        raise PenPlanError("v2 pen-plan 'passes' must contain at least one pass")

    passes: list[PassSpec] = []
    seen_pass_ids: set[str] = set()
    layer_locations: dict[str, list[str]] = {}
    for pass_index, item in enumerate(passes_raw):
        pass_path = f"passes[{pass_index}]"
        if not isinstance(item, dict):
            raise PenPlanError(f"{pass_path} must be a JSON object")
        _reject_unknown_fields(item, {"id", "assignments"}, pass_path)
        pass_id = _require_nonempty_text(item, "id", pass_path)
        if pass_id in seen_pass_ids:
            raise PenPlanError(f"{pass_path}.id has duplicate value {pass_id!r}")
        seen_pass_ids.add(pass_id)

        if "assignments" not in item:
            raise PenPlanError(f"{pass_path} requires 'assignments'")
        assignments_raw = _require_array(
            item["assignments"], f"{pass_path}.assignments"
        )
        if not assignments_raw:
            raise PenPlanError(
                f"{pass_path}.assignments must contain at least one assignment"
            )
        if len(assignments_raw) > MAX_DPX_PENS:
            raise PenPlanError(
                f"{pass_path}.assignments must contain at most {MAX_DPX_PENS} assignments"
            )

        assignments: list[LogicalAssignment] = []
        seen_slots: set[int] = set()
        seen_in_pass: set[str] = set()
        for assignment_index, assignment_raw in enumerate(assignments_raw):
            assignment_path = f"{pass_path}.assignments[{assignment_index}]"
            if not isinstance(assignment_raw, dict):
                raise PenPlanError(f"{assignment_path} must be a JSON object")
            _reject_unknown_fields(
                assignment_raw,
                {"layer_ids", "physical_slot"},
                assignment_path,
            )
            for field in ("layer_ids", "physical_slot"):
                if field not in assignment_raw:
                    raise PenPlanError(f"{assignment_path} requires '{field}'")

            layer_ids = _parse_logical_ids(
                assignment_raw["layer_ids"],
                f"{assignment_path}.layer_ids",
                require_nonempty=True,
            )
            slot = assignment_raw["physical_slot"]
            slot_path = f"{assignment_path}.physical_slot"
            if type(slot) is not int:
                raise PenPlanError(f"{slot_path} must be an integer from 1 through 8")
            if not 1 <= slot <= MAX_DPX_PENS:
                raise PenPlanError(f"{slot_path}={slot} is outside the range 1-8")
            if slot in seen_slots:
                raise PenPlanError(f"{slot_path} has duplicate value {slot}")
            seen_slots.add(slot)

            for layer_index, layer_id in enumerate(layer_ids):
                layer_path = f"{assignment_path}.layer_ids[{layer_index}]"
                if layer_id in seen_in_pass:
                    raise PenPlanError(
                        f"{layer_path}={layer_id!r} is already assigned in {pass_path}"
                    )
                seen_in_pass.add(layer_id)
                layer_locations.setdefault(layer_id, []).append(layer_path)
            assignments.append(LogicalAssignment(layer_ids, slot))
        passes.append(PassSpec(pass_id, tuple(assignments)))

    omitted_layers = _parse_logical_ids(raw["omitted_layers"], "omitted_layers")
    repeated_layers = _parse_logical_ids(raw["repeated_layers"], "repeated_layers")
    repeated_set = set(repeated_layers)

    for index, layer_id in enumerate(omitted_layers):
        if layer_id in layer_locations or layer_id in repeated_set:
            raise PenPlanError(
                f"omitted_layers[{index}]={layer_id!r} cannot also be assigned or repeated"
            )

    for layer_id, locations in layer_locations.items():
        if len(locations) > 1 and layer_id not in repeated_set:
            raise PenPlanError(
                f"{locations[1]}={layer_id!r} repeats across passes but is absent "
                "from repeated_layers"
            )

    for index, layer_id in enumerate(repeated_layers):
        if len(layer_locations.get(layer_id, ())) < 2:
            raise PenPlanError(
                f"repeated_layers[{index}]={layer_id!r} does not repeat across passes"
            )

    return LogicalPenPlanSpec(
        schema_version=LOGICAL_PEN_PLAN_SCHEMA_VERSION,
        passes=tuple(passes),
        omitted_layers=omitted_layers,
        repeated_layers=repeated_layers,
    )


def _reject_unknown_fields(
    record: dict[str, Any],
    allowed: set[str],
    path: str,
    *,
    top_level: bool = False,
) -> None:
    unknown = sorted(set(record) - allowed)
    if not unknown:
        return
    description = "unknown top-level field" if top_level else "unknown field"
    raise PenPlanError(
        f"{path} has {description}{'s' if len(unknown) != 1 else ''}: "
        + ", ".join(unknown)
    )


def _require_array(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise PenPlanError(f"{path} must be a JSON array")
    return value


def _require_nonempty_text(
    record: dict[str, Any], field: str, path: str
) -> str:
    if field not in record:
        raise PenPlanError(f"{path} requires '{field}'")
    value = record[field]
    if not isinstance(value, str) or not value.strip():
        raise PenPlanError(f"{path}.{field} must be a nonempty string")
    return value


def _parse_logical_ids(
    value: object, path: str, *, require_nonempty: bool = False
) -> tuple[str, ...]:
    items = _require_array(value, path)
    if require_nonempty and not items:
        raise PenPlanError(f"{path} must contain at least one logical layer ID")
    parsed: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if not isinstance(item, str) or not item.strip():
            raise PenPlanError(f"{item_path} must be a nonempty string")
        if item in seen:
            raise PenPlanError(f"{item_path} has duplicate logical layer ID {item!r}")
        seen.add(item)
        parsed.append(item)
    return tuple(parsed)


def resolve_logical_pen_plan(
    contract_or_catalog: LogicalLayerContract
    | LogicalLayerManifest
    | tuple[LogicalLayerMetadata, ...]
    | list[LogicalLayerMetadata],
    spec: LogicalPenPlanSpec | None,
    *,
    source_manifest_hash: str | None = None,
) -> tuple[ResolvedPlotPass, ...]:
    """Resolve a validated neutral catalog into explicit physical passes.

    The neutral catalog is authoritative for IDs and ordering.  This resolver
    never discovers or infers layers from arbitrary strings or SVG structure;
    callers must provide the inspected contract/catalog and the exact source
    manifest hash that established it.
    """
    _validate_source_manifest_hash(source_manifest_hash)
    catalog = _validated_neutral_catalog(contract_or_catalog)
    catalog_ids = tuple(layer.id for layer in catalog)
    catalog_index = {layer_id: index for index, layer_id in enumerate(catalog_ids)}

    if spec is None:
        if len(catalog) > MAX_DPX_PENS:
            raise PenPlanError(
                f"Catalog has {len(catalog)} active logical layers; use an explicit "
                "merge or multiple passes plan before physical resolution"
            )
        return (
            ResolvedPlotPass(
                id="preserve",
                assignments=tuple(
                    ResolvedLogicalAssignment((layer.id,), index)
                    for index, layer in enumerate(catalog, start=1)
                ),
                omitted_layers=(),
                source_manifest_hash=source_manifest_hash,
            ),
        )

    if not isinstance(spec, LogicalPenPlanSpec) or spec.schema_version != 2:
        raise PenPlanError(
            "Logical catalog resolution requires a validated schema_version=2 "
            "logical-layer pen plan"
        )
    if not isinstance(spec.passes, (tuple, list)) or not spec.passes:
        raise PenPlanError("passes must contain at least one pass")

    omitted_layers = _validated_accounting_ids(
        spec.omitted_layers, "omitted_layers", catalog_index
    )
    repeated_layers = _validated_accounting_ids(
        spec.repeated_layers, "repeated_layers", catalog_index
    )
    omitted_set = set(omitted_layers)
    repeated_set = set(repeated_layers)
    if omitted_set & repeated_set:
        conflict = tuple(sorted(omitted_set & repeated_set))
        raise PenPlanError(
            "omitted_layers cannot also declare repeated layers: "
            + ", ".join(conflict)
        )

    resolved_passes: list[ResolvedPlotPass] = []
    placements: dict[str, list[str]] = {layer_id: [] for layer_id in catalog_ids}
    pass_ids: set[str] = set()
    for pass_index, plot_pass in enumerate(spec.passes):
        pass_path = f"passes[{pass_index}]"
        if not isinstance(plot_pass, PassSpec):
            raise PenPlanError(f"{pass_path} must be a PassSpec")
        if not isinstance(plot_pass.id, str) or not plot_pass.id.strip():
            raise PenPlanError(f"{pass_path}.id must be a nonempty string")
        if plot_pass.id in pass_ids:
            raise PenPlanError(f"{pass_path}.id has duplicate value {plot_pass.id!r}")
        pass_ids.add(plot_pass.id)
        if not isinstance(plot_pass.assignments, (tuple, list)):
            raise PenPlanError(f"{pass_path}.assignments must be a sequence")
        if not plot_pass.assignments:
            raise PenPlanError(
                f"{pass_path}.assignments must contain at least one assignment"
            )
        if len(plot_pass.assignments) > MAX_DPX_PENS:
            raise PenPlanError(
                f"{pass_path}.assignments must contain at most {MAX_DPX_PENS} assignments"
            )

        pass_assignments: list[ResolvedLogicalAssignment] = []
        seen_slots: set[int] = set()
        seen_ids: set[str] = set()
        for assignment_index, assignment in enumerate(plot_pass.assignments):
            assignment_path = f"{pass_path}.assignments[{assignment_index}]"
            if not isinstance(assignment, LogicalAssignment):
                raise PenPlanError(f"{assignment_path} must be a LogicalAssignment")
            slot = assignment.physical_slot
            if type(slot) is not int or not 1 <= slot <= MAX_DPX_PENS:
                raise PenPlanError(
                    f"{assignment_path}.physical_slot must be an integer from 1 through 8"
                )
            if slot in seen_slots:
                raise PenPlanError(
                    f"{assignment_path}.physical_slot has duplicate physical slot {slot}"
                )
            seen_slots.add(slot)
            layer_ids = _validated_assignment_ids(
                assignment.layer_ids, assignment_path, catalog_index
            )
            for layer_id in layer_ids:
                if layer_id in seen_ids:
                    raise PenPlanError(
                        f"{assignment_path} repeats logical layer {layer_id!r} in {plot_pass.id!r}"
                    )
                seen_ids.add(layer_id)
                placements[layer_id].append(plot_pass.id)
            normalized = tuple(sorted(layer_ids, key=catalog_index.__getitem__))
            pass_assignments.append(
                ResolvedLogicalAssignment(normalized, slot)
            )
        resolved_passes.append(
            ResolvedPlotPass(
                id=plot_pass.id,
                assignments=tuple(pass_assignments),
                omitted_layers=omitted_layers,
                source_manifest_hash=source_manifest_hash,
            )
        )

    for layer_id in omitted_layers:
        if placements[layer_id]:
            raise PenPlanError(
                f"omitted layer {layer_id!r} is also assigned in a pass"
            )

    for layer_id, pass_locations in placements.items():
        count = len(pass_locations)
        if layer_id in omitted_set:
            if count:
                raise PenPlanError(
                    f"omitted layer {layer_id!r} is also assigned in a pass"
                )
            continue
        if layer_id in repeated_set:
            if count < 2:
                raise PenPlanError(
                    f"repeated_layers declaration for {layer_id!r} does not repeat across passes"
                )
            continue
        if count == 0:
            raise PenPlanError(
                f"logical catalog layer {layer_id!r} is not accounted for; "
                "assign it or explicitly omit it"
            )
        if count > 1:
            raise PenPlanError(
                f"logical catalog layer {layer_id!r} repeats across passes but is absent "
                "from repeated_layers"
            )

    return tuple(resolved_passes)


def _validate_source_manifest_hash(value: object) -> None:
    if not isinstance(value, str) or _MANIFEST_SHA256_RE.fullmatch(value) is None:
        raise PenPlanError(
            "source manifest hash must be a lowercase 64-character SHA-256"
        )


def _validated_neutral_catalog(
    contract_or_catalog: object,
) -> tuple[LogicalLayerMetadata, ...]:
    allow_sparse_ordinals = False
    if isinstance(contract_or_catalog, LogicalLayerContract):
        if contract_or_catalog.mode is not InputMode.NEUTRAL:
            raise PenPlanError(
                "logical catalog resolution requires a validated neutral contract"
            )
        catalog = contract_or_catalog.layers
        allow_sparse_ordinals = True
    elif isinstance(contract_or_catalog, LogicalLayerManifest):
        catalog = contract_or_catalog.layers
    elif isinstance(contract_or_catalog, (tuple, list)):
        catalog = tuple(contract_or_catalog)
    else:
        raise PenPlanError(
            "logical catalog resolution requires a validated neutral catalog or contract"
        )

    if not catalog:
        raise PenPlanError("neutral catalog has no active logical layers")
    previous_ordinal = 0
    for index, layer in enumerate(catalog, start=1):
        if not isinstance(layer, LogicalLayerMetadata):
            raise PenPlanError(
                "logical catalog must contain validated LogicalLayerMetadata entries"
            )
        if not isinstance(layer.id, str) or not layer.id.strip():
            raise PenPlanError(f"catalog layer {index} has an invalid ID")
        if type(layer.ordinal) is not int:
            raise PenPlanError(f"catalog layer {layer.id!r} has an invalid ordinal")
        if allow_sparse_ordinals:
            if layer.ordinal <= previous_ordinal:
                raise PenPlanError(
                    "active neutral contract ordinals must be positive, unique, and "
                    "strictly increasing in authoritative order"
                )
            previous_ordinal = layer.ordinal
        elif layer.ordinal != index:
            raise PenPlanError(
                "logical catalog ordinals must be contiguous in authoritative order"
            )
        if not isinstance(layer.label, str) or not layer.label.strip():
            raise PenPlanError(f"catalog layer {layer.id!r} has an invalid label")
    ids = [layer.id for layer in catalog]
    if len(set(ids)) != len(ids):
        raise PenPlanError("logical catalog contains duplicate layer IDs")
    return tuple(catalog)


def _validated_accounting_ids(
    values: object,
    field: str,
    catalog_index: dict[str, int],
) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise PenPlanError(f"{field} must be a sequence of logical layer IDs")
    seen: set[str] = set()
    result: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PenPlanError(f"{field}[{index}] must be a nonempty string")
        if value in seen:
            raise PenPlanError(f"{field}[{index}] has duplicate logical layer ID {value!r}")
        if value not in catalog_index:
            raise PenPlanError(f"{field}[{index}] names unknown logical layer {value!r}")
        seen.add(value)
        result.append(value)
    return tuple(result)


def _validated_assignment_ids(
    values: object,
    path: str,
    catalog_index: dict[str, int],
) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or not values:
        raise PenPlanError(f"{path}.layer_ids must contain at least one logical layer ID")
    seen: set[str] = set()
    result: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PenPlanError(f"{path}.layer_ids[{index}] must be a nonempty string")
        if value in seen:
            raise PenPlanError(
                f"{path}.layer_ids[{index}] has duplicate logical layer ID {value!r}"
            )
        if value not in catalog_index:
            raise PenPlanError(
                f"{path}.layer_ids[{index}] names unknown logical layer {value!r}"
            )
        seen.add(value)
        result.append(value)
    return tuple(result)


def parse_pen_map(raw: str | None) -> tuple[RequestedAssignment, ...]:
    """Parse ``logical:physical`` CLI mappings such as ``2:1,3:2``."""
    if raw is None or not raw.strip():
        return ()
    assignments: list[RequestedAssignment] = []
    for part in raw.split(","):
        try:
            logical_raw, physical_raw = part.split(":", 1)
            logical = int(logical_raw)
            physical = int(physical_raw)
        except ValueError as exc:
            raise PenPlanError(
                f"Invalid --pen-map item {part!r}; expected logical:physical"
            ) from exc
        _validate_pen_number(logical, label="logical_layer")
        _validate_pen_number(physical, label="physical_slot")
        assignments.append(RequestedAssignment(logical, physical))
    _ensure_unique((item.logical_layer for item in assignments), "logical_layer")
    _ensure_unique((item.physical_slot for item in assignments), "physical_slot")
    return tuple(assignments)


def default_pen_plan_path(source_svg: Path) -> Path:
    # Conventional user-authored pen-plan path for an SVG.
    return Path(source_svg).with_suffix(PEN_PLAN_SUFFIX)


def default_resolved_pen_plan_path(hpgl_path: Path) -> Path:
    # Generated resolved pen-plan path for an HP-GL job.
    return Path(hpgl_path).with_suffix(RESOLVED_PEN_PLAN_SUFFIX)


def _json_kind(path: Path) -> str | None:
    # Return a JSON object's kind discriminator when it can be read.
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    return str(kind) if kind is not None else None


def discover_pen_plan(
    source_svg: Path, explicit_path: Path | None = None
) -> Path | None:
    # Return an explicit plan or an adjacent user-authored plan if present.
    if explicit_path is not None:
        return explicit_path
    adjacent = default_pen_plan_path(source_svg)
    if not adjacent.is_file():
        return None
    # Old converter output used the same suffix as user-authored input plans.
    # Do not parse a generated resolved audit sidecar as an input specification.
    if _json_kind(adjacent) == RESOLVED_PEN_PLAN_KIND:
        return None
    return adjacent


def discover_resolved_pen_plan_path(hpgl_path: Path) -> Path:
    # Find a resolved sidecar, with read-only support for the legacy name.
    preferred = default_resolved_pen_plan_path(hpgl_path)
    if preferred.is_file():
        return preferred

    legacy = Path(hpgl_path).with_suffix(PEN_PLAN_SUFFIX)
    if legacy.is_file() and _json_kind(legacy) == RESOLVED_PEN_PLAN_KIND:
        return legacy
    return preferred


def inspect_logical_layers(source_svg: Path) -> tuple[LogicalLayer, ...]:
    """Read logical layer metadata and whether each layer contains geometry."""
    try:
        root = ET.parse(source_svg).getroot()
    except ET.ParseError as exc:
        raise PenPlanError(f"Invalid SVG/XML in {source_svg}: {exc}") from exc

    layers: list[LogicalLayer] = []
    for group in root:
        if _local_name(group.tag) != "g":
            continue
        match = PEN_ID_RE.fullmatch(group.get("id", ""))
        if not match:
            continue
        logical = int(match.group(1))
        generations = _parse_generations(group.get("data-generations", ""), source_svg)
        layers.append(
            LogicalLayer(
                logical_layer=logical,
                active=_contains_drawable(group),
                generations=generations,
                preview_color=group.get("stroke", ""),
            )
        )
    return tuple(sorted(layers, key=lambda item: item.logical_layer))


def resolve_pen_plan(
    source_svg: Path,
    *,
    plan_path: Path | None = None,
    cli_policy: str | None = None,
    cli_pen_map: str | None = None,
) -> ResolvedPenPlan:
    """Resolve active logical SVG layers to physical DPX slots.

    Precedence is intentionally explicit:
    1. a JSON pen plan (explicit path or adjacent sidecar),
    2. CLI policy/map when no JSON plan is used,
    3. ``preserve`` when neither is supplied.
    """
    discovered = discover_pen_plan(source_svg, plan_path)
    if discovered is not None:
        if cli_policy is not None or cli_pen_map is not None:
            raise PenPlanError(
                "Do not combine a .penplan.json file with --pen-policy or --pen-map"
            )
        spec = load_pen_plan(discovered)
        if isinstance(spec, LogicalPenPlanSpec):
            raise PenPlanError(
                "schema_version=2 requires logical-layer catalog resolution; "
                "the legacy SVG resolver only supports v1 numeric plans"
            )
    else:
        policy = cli_policy or ("explicit" if cli_pen_map else "preserve")
        _validate_policy(policy)
        assignments = parse_pen_map(cli_pen_map)
        if policy == "explicit" and not assignments:
            raise PenPlanError("--pen-policy explicit requires --pen-map or a pen-plan JSON")
        if policy != "explicit" and assignments:
            raise PenPlanError("--pen-map requires --pen-policy explicit")
        spec = PenPlanSpec(
            schema_version=PEN_PLAN_SCHEMA_VERSION,
            policy=policy,
            assignments=assignments,
            slots=(),
        )

    layers = inspect_logical_layers(source_svg)
    if not layers:
        raise PenPlanError(f"{source_svg} does not contain any top-level pen-N layers")
    active = tuple(layer for layer in layers if layer.active)
    if not active:
        raise PenPlanError(f"{source_svg} contains no drawable pen layers")

    mapping = _resolve_mapping(active, spec)
    slots = {slot.slot: slot for slot in spec.slots}
    resolved: list[ResolvedAssignment] = []
    for layer in active:
        physical = mapping[layer.logical_layer]
        slot = slots.get(physical)
        resolved.append(
            ResolvedAssignment(
                logical_layer=layer.logical_layer,
                physical_slot=physical,
                generations=layer.generations,
                preview_color=layer.preview_color,
                tool=slot.tool if slot else None,
                color=slot.color if slot else None,
                label=slot.label if slot else None,
                notes=slot.notes if slot else None,
            )
        )

    return ResolvedPenPlan(
        source_svg=source_svg.name,
        policy=spec.policy,
        logical_layers=layers,
        assignments=tuple(resolved),
        notes=spec.notes,
    )


def remap_hpgl_pen_selections(path: Path, plan: ResolvedPenPlan) -> None:
    """Rewrite logical ``SPn;`` commands to the resolved physical slots."""
    mapping = {
        assignment.logical_layer: assignment.physical_slot
        for assignment in plan.assignments
    }
    text = path.read_text(encoding="ascii", errors="ignore")
    seen_logical: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        logical = int(match.group(1))
        if logical == 0:
            return "SP0;"
        if logical not in mapping:
            raise PenPlanError(
                f"HP-GL contains SP{logical}; but logical layer {logical} "
                "is not present in the resolved pen plan"
            )
        seen_logical.add(logical)
        return f"SP{mapping[logical]};"

    remapped = SP_RE.sub(replace, text)
    missing = sorted(set(mapping) - seen_logical)
    if missing:
        raise PenPlanError(
            "HP-GL is missing active logical pen selections before remapping: "
            + ", ".join(f"SP{pen}" for pen in missing)
        )
    path.write_text(remapped, encoding="ascii")


def write_resolved_pen_plan(path: Path, plan: ResolvedPenPlan) -> None:
    """Write the exact physical assignment used for an HP-GL output file."""
    used_slots = set(plan.physical_pens)
    payload: dict[str, Any] = {
        "schema_version": PEN_PLAN_SCHEMA_VERSION,
        "kind": "resolved-dpx3300-pen-plan",
        "source_svg": plan.source_svg,
        "policy": plan.policy,
        "logical_layers": [
            {
                **asdict(layer),
                "generations": list(layer.generations),
            }
            for layer in plan.logical_layers
        ],
        "assignments": [
            {
                **asdict(item),
                "generations": list(item.generations),
            }
            for item in plan.assignments
        ],
        "slots": [
            {
                key: value
                for key, value in {
                    "slot": item.physical_slot,
                    "tool": item.tool,
                    "color": item.color,
                    "label": item.label,
                    "notes": item.notes,
                }.items()
                if value is not None
            }
            for item in plan.assignments
        ],
        "unused_physical_slots": [
            slot for slot in range(1, MAX_DPX_PENS + 1) if slot not in used_slots
        ],
    }
    if plan.notes:
        payload["notes"] = plan.notes
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _validate_resolved_plot_pass(raw: object) -> dict[str, Any]:
    """Validate the standalone v2 audit contract without guessing legacy fields."""
    fields = {
        "schema_version",
        "kind",
        "pass_id",
        "pass_number",
        "pass_count",
        "source_svg",
        "source_svg_sha256",
        "source_manifest_hash",
        "assignments",
        "omitted_layers",
        "repeated_layers",
        "physical_slots",
    }
    if not isinstance(raw, dict) or set(raw) != fields:
        raise PenPlanError(
            "Resolved logical pass must contain exactly the v2 audit fields"
        )
    if (
        type(raw["schema_version"]) is not int
        or raw["schema_version"] != 2
        or raw["kind"] != RESOLVED_PLOT_PASS_KIND
    ):
        raise PenPlanError("Invalid resolved logical pass schema_version/kind")
    for field in ("pass_number", "pass_count"):
        if type(raw[field]) is not int or raw[field] < 1:
            raise PenPlanError(f"Invalid resolved logical pass {field}")
    if raw["pass_number"] > raw["pass_count"]:
        raise PenPlanError("pass_number exceeds pass_count")
    if not isinstance(raw["pass_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]*", raw["pass_id"]
    ):
        raise PenPlanError("Invalid resolved logical pass pass_id")
    _require_nonempty_text(raw, "source_svg", "resolved pass")
    _validate_source_manifest_hash(raw["source_manifest_hash"])
    if not isinstance(
        raw["source_svg_sha256"], str
    ) or not _MANIFEST_SHA256_RE.fullmatch(raw["source_svg_sha256"]):
        raise PenPlanError("Invalid source SVG SHA-256")
    omitted = _parse_logical_ids(raw["omitted_layers"], "omitted_layers")
    repeated = _parse_logical_ids(raw["repeated_layers"], "repeated_layers")
    if set(omitted) & set(repeated):
        raise PenPlanError("Omitted layers cannot be repeated")
    assignments = _require_array(raw["assignments"], "assignments")
    if not 1 <= len(assignments) <= 8:
        raise PenPlanError("Resolved pass requires 1..8 assignments")
    slots = []
    included = set()
    for item in assignments:
        if not isinstance(item, dict) or set(item) != {"layer_ids", "physical_slot"}:
            raise PenPlanError("Invalid resolved logical assignment")
        layer_ids = _parse_logical_ids(
            item["layer_ids"], "layer_ids", require_nonempty=True
        )
        slot = item["physical_slot"]
        if type(slot) is not int or not 1 <= slot <= 8 or slot in slots:
            raise PenPlanError("Invalid or duplicate resolved physical slot")
        if included.intersection(layer_ids) or set(omitted).intersection(layer_ids):
            raise PenPlanError("Assigned logical IDs must be unique and not omitted")
        included.update(layer_ids)
        slots.append(slot)
    if (
        not isinstance(raw["physical_slots"], list)
        or any(type(slot) is not int for slot in raw["physical_slots"])
        or raw["physical_slots"] != slots
    ):
        raise PenPlanError("physical_slots differs from ordered assignments")
    return raw


def write_resolved_plot_pass(path: Path, payload: dict[str, Any]) -> None:
    """Write a deterministic, strictly validated neutral v2 pass audit."""
    validated = _validate_resolved_plot_pass(payload)
    path.write_text(
        json.dumps(validated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_resolved_plot_pass(path: Path) -> dict[str, Any]:
    """Read only neutral v2 pass sidecars; legacy sidecars use their old API."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PenPlanError(f"Invalid resolved logical pass {path}: {exc}") from exc
    return _validate_resolved_plot_pass(raw)


def format_pen_plan(plan: ResolvedPenPlan) -> str:
    """Return a concise human-readable carriage loading/preflight table."""
    lines = [
        f"Pen assignment policy: {plan.policy}",
        "Logical  Generations  ->  DPX slot  Expected tool / color",
        "-------  -----------      --------  ---------------------",
    ]
    for item in plan.assignments:
        generations = ",".join(str(value) for value in item.generations) or "-"
        tool_parts = [value for value in (item.label, item.tool, item.color) if value]
        expected = " / ".join(tool_parts) if tool_parts else "<not documented>"
        lines.append(
            f"{item.logical_layer:>7}  {generations:<11}  ->  "
            f"{item.physical_slot:>8}  {expected}"
        )
    inactive = plan.inactive_logical_pens
    if inactive:
        lines.append(
            "Inactive logical layers (no drawable geometry): "
            + ", ".join(str(value) for value in inactive)
        )
    return "\n".join(lines)


def plan_has_documented_tools(plan: ResolvedPenPlan) -> bool:
    """Return true when every used physical slot identifies the expected tool."""
    return all(bool(item.tool or item.label) for item in plan.assignments)


def _resolve_mapping(
    active: tuple[LogicalLayer, ...], spec: PenPlanSpec
) -> dict[int, int]:
    logical_pens = tuple(layer.logical_layer for layer in active)
    if len(logical_pens) > MAX_DPX_PENS:
        raise PenPlanError(
            f"Drawing has {len(logical_pens)} active logical layers; DPX-3300 supports "
            f"at most {MAX_DPX_PENS} simultaneously loaded pens"
        )

    if spec.policy == "preserve":
        return {logical: logical for logical in logical_pens}
    if spec.policy == "compact":
        return {logical: index for index, logical in enumerate(logical_pens, start=1)}

    requested = {
        item.logical_layer: item.physical_slot for item in spec.assignments
    }
    active_set = set(logical_pens)
    requested_set = set(requested)
    missing = sorted(active_set - requested_set)
    extra = sorted(requested_set - active_set)
    if missing:
        raise PenPlanError(
            "Explicit pen plan is missing active logical layers: "
            + ", ".join(str(value) for value in missing)
        )
    if extra:
        raise PenPlanError(
            "Explicit pen plan assigns inactive or absent logical layers: "
            + ", ".join(str(value) for value in extra)
        )
    return requested


def _validate_policy(policy: object) -> None:
    if policy not in PEN_POLICIES:
        raise PenPlanError(
            f"Unsupported pen policy {policy!r}; choose from {', '.join(PEN_POLICIES)}"
        )


def _validate_pen_number(value: int, *, label: str) -> None:
    if not 1 <= value <= MAX_DPX_PENS:
        raise PenPlanError(f"{label}={value} is outside the DPX-3300 range 1-8")


def _ensure_unique(values: Iterable[int], label: str) -> None:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise PenPlanError(
            f"Duplicate {label} values: " + ", ".join(str(value) for value in sorted(duplicates))
        )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PenPlanError(f"Expected text value, got {type(value).__name__}")
    stripped = value.strip()
    return stripped or None


def _parse_generations(raw: str, path: Path) -> tuple[int, ...]:
    if not raw:
        return ()
    try:
        return tuple(int(value) for value in raw.split(","))
    except ValueError as exc:
        raise PenPlanError(f"{path}: invalid data-generations={raw!r}") from exc


def _contains_drawable(element: ET.Element) -> bool:
    return any(_local_name(child.tag) in _DRAWABLE_TAGS for child in element.iter())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def physical_pens_in_hpgl(path: Path) -> tuple[int, ...]:
    """Return physical ``SPn`` selections in first-use order, excluding ``SP0``."""
    text = path.read_text(encoding="ascii", errors="ignore")
    ordered: list[int] = []
    seen: set[int] = set()
    for match in SP_RE.finditer(text):
        pen = int(match.group(1))
        if pen == 0 or pen in seen:
            continue
        seen.add(pen)
        ordered.append(pen)
    return tuple(ordered)


def load_resolved_pen_plan(path: Path) -> ResolvedPenPlan:
    """Load the resolved sidecar emitted beside an HP-GL output file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PenPlanError(f"Invalid JSON in resolved pen plan {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PenPlanError(f"Resolved pen plan {path} must contain a JSON object")
    if raw.get("schema_version") != PEN_PLAN_SCHEMA_VERSION:
        raise PenPlanError(
            f"Resolved pen plan {path} has unsupported schema_version="
            f"{raw.get('schema_version')!r}"
        )
    if raw.get("kind") != "resolved-dpx3300-pen-plan":
        raise PenPlanError(
            f"{path} is not a resolved-dpx3300-pen-plan sidecar"
        )
    policy = raw.get("policy")
    _validate_policy(policy)

    logical_layers_raw = raw.get("logical_layers", [])
    assignments_raw = raw.get("assignments", [])
    if not isinstance(logical_layers_raw, list) or not isinstance(assignments_raw, list):
        raise PenPlanError(f"{path} has invalid resolved plan arrays")

    logical_layers: list[LogicalLayer] = []
    for index, item in enumerate(logical_layers_raw):
        if not isinstance(item, dict):
            raise PenPlanError(f"logical_layers[{index}] must be an object")
        try:
            logical = int(item["logical_layer"])
            active = bool(item["active"])
            generations = tuple(int(value) for value in item.get("generations", []))
            preview = str(item.get("preview_color", ""))
        except (KeyError, TypeError, ValueError) as exc:
            raise PenPlanError(f"Invalid logical_layers[{index}] in {path}") from exc
        _validate_pen_number(logical, label="logical_layer")
        logical_layers.append(LogicalLayer(logical, active, generations, preview))

    assignments: list[ResolvedAssignment] = []
    for index, item in enumerate(assignments_raw):
        if not isinstance(item, dict):
            raise PenPlanError(f"assignments[{index}] must be an object")
        try:
            logical = int(item["logical_layer"])
            physical = int(item["physical_slot"])
            generations = tuple(int(value) for value in item.get("generations", []))
        except (KeyError, TypeError, ValueError) as exc:
            raise PenPlanError(f"Invalid assignments[{index}] in {path}") from exc
        _validate_pen_number(logical, label="logical_layer")
        _validate_pen_number(physical, label="physical_slot")
        assignments.append(
            ResolvedAssignment(
                logical_layer=logical,
                physical_slot=physical,
                generations=generations,
                preview_color=str(item.get("preview_color", "")),
                tool=_optional_text(item.get("tool")),
                color=_optional_text(item.get("color")),
                label=_optional_text(item.get("label")),
                notes=_optional_text(item.get("notes")),
            )
        )

    _ensure_unique((item.logical_layer for item in assignments), "logical_layer")
    _ensure_unique((item.physical_slot for item in assignments), "physical_slot")
    return ResolvedPenPlan(
        source_svg=str(raw.get("source_svg", "")),
        policy=str(policy),
        logical_layers=tuple(logical_layers),
        assignments=tuple(assignments),
        notes=_optional_text(raw.get("notes")),
    )


def validate_resolved_pen_plan_for_hpgl(
    hpgl_path: Path, sidecar_path: Path | None = None
) -> ResolvedPenPlan:
    """Verify a resolved sidecar against the actual HP-GL pen selections."""
    if sidecar_path is None:
        sidecar_path = discover_resolved_pen_plan_path(hpgl_path)
    if not sidecar_path.is_file():
        raise PenPlanError(f"Resolved pen-plan sidecar does not exist: {sidecar_path}")
    plan = load_resolved_pen_plan(sidecar_path)
    actual = physical_pens_in_hpgl(hpgl_path)
    expected = plan.physical_pens
    if actual != expected:
        raise PenPlanError(
            f"HP-GL physical pen order {actual} does not match resolved pen plan {expected}"
        )
    return plan
