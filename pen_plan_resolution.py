"""Resolve one physical pass model from normalized source layers."""

import re
from collections import Counter

from pen_force import effective_force
from pen_plan_models import Assignment, LayerInfo, PassSpec, PenPlanError, PenPlanSpec


def resolve_plot_passes(layers: tuple[LayerInfo, ...], spec: PenPlanSpec) -> tuple[PassSpec, ...]:
    index = {layer.id: layer for layer in layers}
    if len(index) != len(layers):
        raise PenPlanError('duplicate source layer')
    active = {layer.id for layer in layers if layer.active}
    omitted, repeated = set(spec.omitted_layers), set(spec.repeated_layers)
    if (omitted | repeated)-set(index) or omitted & repeated:
        raise PenPlanError('unknown/conflicting omitted or repeated layers')
    if spec.policy != 'explicit':
        assignments = []
        for layer in sorted(layers, key=lambda x: x.ordinal):
            if not layer.active or layer.id in omitted:
                continue
            if spec.policy == 'preserve':
                match = re.fullmatch(r'pen-([1-8])', layer.id)
                if match is None:
                    raise PenPlanError('preserve requires pen-N identities; use compact or explicit')
                slot = int(match[1])
            else:
                slot = len(assignments)+1
            if slot > 8:
                raise PenPlanError('automatic assignment exceeds eight slots; use explicit passes')
            assignments.append(Assignment((layer.id,), slot))
        passes = (PassSpec('plot', tuple(assignments)),)
    else:
        passes = spec.passes
    counts = Counter()
    resolved = []
    for p in passes:
        if not p.assignments:
            raise PenPlanError('pass must have active assignments')
        seen_slots, seen_layers = set(), set()
        entries = []
        for a in p.assignments:
            selected = set(a.layer_ids)
            if not selected or selected-active or selected & omitted or selected & seen_layers:
                raise PenPlanError('unknown, inactive, omitted, or duplicate layer in pass')
            if type(a.physical_slot) is not int or not 1 <= a.physical_slot <= 8 or a.physical_slot in seen_slots:
                raise PenPlanError('invalid/duplicate physical slot')
            if spec.pen_force is not None and effective_force(spec.pen_force, a.physical_slot) is None:
                raise PenPlanError(f'missing force for physical slot {a.physical_slot}')
            seen_slots.add(a.physical_slot)
            seen_layers.update(selected)
            counts.update(selected)
            entries.append(Assignment(tuple(sorted(selected, key=lambda x: index[x].ordinal)), a.physical_slot))
        resolved.append(PassSpec(p.id, tuple(entries)))
    if active-set(counts)-omitted:
        raise PenPlanError(f'unaccounted active layers: {sorted(active-set(counts)-omitted)}')
    actual_repeated = {key for key, count in counts.items() if count > 1}
    if actual_repeated != repeated:
        raise PenPlanError('repeated_layers must match actual cross-pass repetition')
    return tuple(resolved)
