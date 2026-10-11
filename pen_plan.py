"""Unified schema-3 physical planning, provenance and pen selection."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from hpgl_commands import tokenize_hpgl
from hpgl_force import validate_force
from logical_layer_contract import InputMode, inspect_svg_contract
from pen_force import effective_force
from pen_plan_io import load_pen_plan, load_resolved_plot_pass, read_json
from pen_plan_io import write_resolved_plot_pass as write_resolved_plot_pass
from pen_plan_models import (
    Assignment,
    ForceAudit,
    LayerInfo,
    PassSpec,
    PenPlanSpec,
    ResolvedPlotPass,
)
from pen_plan_models import PenPlanError as PenPlanError
from pen_plan_resolution import resolve_plot_passes

PEN_POLICIES = ("preserve", "compact", "explicit")
MAX_DPX_PENS = 8


def default_pen_plan_path(source_svg: Path) -> Path:
    return source_svg.with_suffix(".penplan.json")


def default_resolved_pen_plan_path(hpgl_path: Path) -> Path:
    return hpgl_path.with_suffix(".resolved.penplan.json")


def discover_resolved_pen_plan_path(hpgl_path: Path) -> Path:
    return default_resolved_pen_plan_path(hpgl_path)


def discover_pen_plan(source_svg: Path, explicit: Path | None = None) -> Path | None:
    candidate = Path(explicit) if explicit is not None else default_pen_plan_path(source_svg)
    if candidate.is_file():
        return candidate
    if explicit is not None:
        raise PenPlanError(f"Pen plan does not exist: {candidate}")
    return None


def _drawable(node):
    if node.tag.rsplit("}", 1)[-1] in ("defs", "clipPath", "mask", "marker", "pattern"):
        return False
    if node.tag.rsplit("}", 1)[-1] in (
        "path",
        "line",
        "polyline",
        "polygon",
        "rect",
        "circle",
        "ellipse",
        "use",
    ):
        return True
    return any(_drawable(child) for child in node)


def inspect_plan_layers(source_svg: Path) -> tuple[LayerInfo, ...]:
    contract = inspect_svg_contract(source_svg)
    root = ET.parse(source_svg).getroot()
    if contract.mode == InputMode.NEUTRAL:
        groups = {
            g.get("data-viz-layer-id"): g for g in root if g.get("data-viz-layer-id") is not None
        }
        return tuple(
            LayerInfo(layer.id, layer.id in groups and _drawable(groups[layer.id]), layer.ordinal)
            for layer in contract.layers
        )
    if contract.mode == InputMode.LEGACY:
        return tuple(
            LayerInfo(f"pen-{n}", n in contract.legacy.pens, i)
            for i, n in enumerate(contract.legacy.declared_pens, 1)
        )
    return (LayerInfo("artwork", _drawable(root), 1),)


def parse_pen_map(raw: str | None) -> tuple[Assignment, ...]:
    if not raw:
        return ()
    result = []
    for part in raw.split(","):
        match = re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*", part)
        if match is None or not all(1 <= int(v) <= 8 for v in match.groups()):
            raise PenPlanError("pen map requires logical:physical numbers 1 through 8")
        result.append(Assignment((f"pen-{int(match[1])}",), int(match[2])))
    if len({a.layer_ids[0] for a in result}) != len(result) or len(
        {a.physical_slot for a in result}
    ) != len(result):
        raise PenPlanError("duplicate pen-map layer or physical slot")
    return tuple(result)


def source_plan(source_svg, *, plan_path=None, cli_policy=None, cli_pen_map=None):
    discovered = discover_pen_plan(source_svg, plan_path)
    if discovered is not None:
        if cli_policy is not None or cli_pen_map is not None:
            raise PenPlanError("CLI pen mapping/policy conflicts with authored plan")
        spec = load_pen_plan(discovered)
    elif cli_pen_map:
        if cli_policy not in (None, "explicit"):
            raise PenPlanError("pen map requires explicit policy")
        spec = PenPlanSpec("explicit", (PassSpec("plot", parse_pen_map(cli_pen_map)),))
    else:
        contract = inspect_svg_contract(source_svg)
        default = "preserve" if contract.mode == InputMode.LEGACY else "compact"
        spec = PenPlanSpec(cli_policy or default)
    return spec, resolve_plot_passes(inspect_plan_layers(source_svg), spec)


def physical_pens_in_hpgl(path: Path) -> tuple[int, ...]:
    result = []
    for command in tokenize_hpgl(path.read_text(encoding="ascii")):
        if command.opcode != "SP":
            continue
        if not re.fullmatch(r"[0-8]", command.arguments):
            raise PenPlanError(f"invalid physical pen selection SP{command.arguments}")
        slot = int(command.arguments)
        if slot and slot not in result:
            result.append(slot)
    return tuple(result)


def remap_hpgl_pen_selections(path: Path, mapping: dict[int, int]) -> None:
    text = path.read_text(encoding="ascii")
    pieces = []
    last = 0
    for command in tokenize_hpgl(text):
        if command.opcode != "SP":
            continue
        if not re.fullmatch(r"[0-8]", command.arguments):
            raise PenPlanError("invalid SP command")
        slot = int(command.arguments)
        if slot and slot not in mapping:
            raise PenPlanError(f"HP-GL selected unassigned logical pen {slot}")
        pieces.extend((text[last : command.start], f"SP{mapping[slot] if slot else 0};"))
        last = command.end
    pieces.append(text[last:])
    path.write_text("".join(pieces), encoding="ascii")


def make_resolved_pass(
    source, plot_pass, spec, hpgl_path, *, manifest_hash=None, pass_number=1, pass_count=1
):
    physical = tuple(a.physical_slot for a in plot_pass.assignments)
    metadata = tuple(s for s in spec.slots if s.slot in physical)
    force = (
        None
        if spec.pen_force is None
        else ForceAudit(
            spec.pen_force, tuple((s, effective_force(spec.pen_force, s)) for s in sorted(physical))
        )
    )
    return ResolvedPlotPass(
        str(source.resolve()),
        hashlib.sha256(source.read_bytes()).hexdigest(),
        manifest_hash,
        plot_pass.id,
        pass_number,
        pass_count,
        spec.policy,
        plot_pass.assignments,
        physical,
        spec.omitted_layers,
        spec.repeated_layers,
        metadata,
        hashlib.sha256(hpgl_path.read_bytes()).hexdigest(),
        force,
    )


def validate_resolved_sidecar_for_hpgl(
    hpgl_path: Path, sidecar_path: Path | None = None
) -> ResolvedPlotPass:
    sidecar = sidecar_path or default_resolved_pen_plan_path(hpgl_path)
    plan = load_resolved_plot_pass(sidecar)
    if hashlib.sha256(hpgl_path.read_bytes()).hexdigest() != plan.hpgl_sha256:
        raise PenPlanError("HP-GL SHA-256 differs from resolved plan; reconvert")
    if physical_pens_in_hpgl(hpgl_path) != plan.physical_slots:
        raise PenPlanError("HP-GL physical pen order differs from resolved plan")
    source = Path(plan.source_svg)
    if (
        source.is_file()
        and hashlib.sha256(source.read_bytes()).hexdigest() != plan.source_svg_sha256
    ):
        raise PenPlanError("source SVG SHA-256 differs from resolved plan")
    audit_path = source.with_suffix(".imposition.json")
    if plan.source_manifest_hash is not None and audit_path.is_file():
        audit = read_json(audit_path)
        raw_path = audit.get("source_manifest_path") if isinstance(audit, dict) else None
        if not isinstance(raw_path, str) or not raw_path:
            raise PenPlanError("source manifest path missing from imposition audit")
        manifest = Path(raw_path)
        if not manifest.is_absolute():
            manifest = audit_path.parent / manifest
        if (
            manifest.is_file()
            and hashlib.sha256(manifest.read_bytes()).hexdigest() != plan.source_manifest_hash
        ):
            raise PenPlanError("source manifest SHA-256 differs from resolved plan")
    try:
        validate_force(
            hpgl_path.read_text(encoding="ascii"),
            None if plan.pen_force is None else plan.pen_force.spec,
            plan.physical_slots,
        )
    except ValueError as error:
        raise PenPlanError(str(error)) from error
    return plan


def plan_has_documented_tools(plan: ResolvedPlotPass) -> bool:
    slots = {s.slot: s for s in plan.slots}
    return all(s in slots and (slots[s].tool or slots[s].label) for s in plan.physical_slots)


def format_resolved_plot_pass(plan: ResolvedPlotPass) -> str:
    lines = [f"Physical pass: {plan.pass_id} ({plan.pass_number}/{plan.pass_count})", "Carriage:"]
    metadata = {s.slot: s for s in plan.slots}
    forces = {} if plan.pen_force is None else dict(plan.pen_force.effective_slot_forces)
    for a in plan.assignments:
        info = metadata.get(a.physical_slot)
        description = (
            " / ".join(v for v in (info.tool, info.label, info.color) if v)
            if info
            else "<not documented>"
        )
        force = (
            f"; expected {forces[a.physical_slot]} gf"
            if a.physical_slot in forces
            else "; force unmanaged"
        )
        lines.append(
            f"  SP{a.physical_slot}: logical {', '.join(a.layer_ids)} - {description}{force}"
        )
    if plan.pen_force:
        lines.append(
            "Force: FS encoded; confirm AUTO OFF."
            if plan.pen_force.spec.mode == "software"
            else "Force: operator panel settings; confirm AUTO ON and displayed forces set."
        )
    return "\n".join(lines)
