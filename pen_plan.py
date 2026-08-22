"""Resolve logical SVG layers to physical DPX-3300 pen slots.

The producer-facing SVG contract and the machine-facing pen assignment are kept
separate deliberately.  A logical layer may be preserved, compacted into the
lowest available slot, or explicitly assigned by a user-authored pen-plan JSON
file.  Generated HP-GL is remapped only after vpype has completed geometry and
layout processing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable
import xml.etree.ElementTree as ET

MAX_DPX_PENS = 8
PEN_POLICIES = ("preserve", "compact", "explicit")
PEN_PLAN_SCHEMA_VERSION = 1
PEN_PLAN_SUFFIX = ".penplan.json"
RESOLVED_PEN_PLAN_SUFFIX = ".resolved.penplan.json"
RESOLVED_PEN_PLAN_KIND = "resolved-dpx3300-pen-plan"
PEN_ID_RE = re.compile(r"^pen-(\d+)$")
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


def load_pen_plan(path: Path) -> PenPlanSpec:
    """Load and validate a user-authored ``*.penplan.json`` file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PenPlanError(f"Invalid JSON in pen plan {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PenPlanError(f"Pen plan {path} must contain a JSON object")

    version = raw.get("schema_version", PEN_PLAN_SCHEMA_VERSION)
    if version != PEN_PLAN_SCHEMA_VERSION:
        raise PenPlanError(
            f"Pen plan {path} uses schema_version={version!r}; "
            f"supported version is {PEN_PLAN_SCHEMA_VERSION}"
        )

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
