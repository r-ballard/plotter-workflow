"""Strict schema-3 authored plans and resolved audit serialization."""

import json
import re
from dataclasses import asdict
from pathlib import Path

from pen_force import effective_force, force_payload, parse_force
from pen_plan_models import (
    RESOLVED_KIND, SCHEMA_VERSION, Assignment, ForceAudit, PassSpec,
    PenPlanError, PenPlanSpec, ResolvedPlotPass, SlotSpec,
)


def object_fields(raw, required, optional=()):
    if not isinstance(raw, dict) or set(raw)-set(required)-set(optional) or set(required)-set(raw):
        raise PenPlanError(f'expected object fields {sorted(required)}; optional {sorted(optional)}')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise PenPlanError(f'{label} must be nonempty text')
    return value


def integer(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise PenPlanError(f'{label} must be an integer {lo} through {hi}')
    return value


def ids(raw, label):
    if not isinstance(raw, list):
        raise PenPlanError(f'{label} must be an array')
    result = tuple(text(v, label) for v in raw)
    if len(set(result)) != len(result):
        raise PenPlanError(f'{label} contains duplicates')
    return result


def assignments(raw):
    if not isinstance(raw, list) or not raw:
        raise PenPlanError('assignments must be a nonempty array')
    result, seen_layers, seen_slots = [], set(), set()
    for entry in raw:
        object_fields(entry, ('layer_ids', 'physical_slot'))
        layers = ids(entry['layer_ids'], 'layer_ids')
        slot = integer(entry['physical_slot'], 1, 8, 'physical_slot')
        if not layers or seen_layers.intersection(layers) or slot in seen_slots:
            raise PenPlanError('duplicate layer or physical slot assignment')
        seen_layers.update(layers)
        seen_slots.add(slot)
        result.append(Assignment(layers, slot))
    return tuple(result)


def slots(raw):
    if not isinstance(raw, list):
        raise PenPlanError('slots must be an array')
    result = []
    for entry in raw:
        object_fields(entry, ('slot',), ('tool', 'color', 'label', 'notes'))
        values = {k: text(v, f'slots.{k}') for k, v in entry.items() if k != 'slot'}
        result.append(SlotSpec(integer(entry['slot'], 1, 8, 'slot'), **values))
    if len({s.slot for s in result}) != len(result):
        raise PenPlanError('duplicate slot metadata')
    return tuple(sorted(result, key=lambda s: s.slot))


def _version(raw):
    if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 3:
        raise PenPlanError('schema_version 3 required; migrate the authored plan and reconvert old jobs')


def parse_pen_plan(raw: object) -> PenPlanSpec:
    _version(raw)
    object_fields(raw, ('schema_version', 'policy'),
                  ('passes', 'slots', 'omitted_layers', 'repeated_layers', 'pen_force', 'notes'))
    policy = raw['policy']
    if policy not in ('preserve', 'compact', 'explicit'):
        raise PenPlanError('invalid pen assignment policy')
    passes = []
    if policy == 'explicit':
        if not isinstance(raw.get('passes'), list) or not raw['passes']:
            raise PenPlanError('explicit policy requires nonempty passes')
        for p in raw['passes']:
            object_fields(p, ('id', 'assignments'))
            passes.append(PassSpec(text(p['id'], 'pass id'), assignments(p['assignments'])))
        if len({p.id for p in passes}) != len(passes):
            raise PenPlanError('duplicate pass ID')
    elif 'passes' in raw or raw.get('repeated_layers'):
        raise PenPlanError('passes/repeated_layers require explicit policy')
    omitted, repeated = ids(raw.get('omitted_layers', []), 'omitted_layers'), ids(
        raw.get('repeated_layers', []), 'repeated_layers')
    if set(omitted).intersection(repeated):
        raise PenPlanError('omitted and repeated layers conflict')
    if 'pen_force' in raw and raw['pen_force'] is None:
        raise PenPlanError('pen_force must be omitted, not null')
    try:
        force = parse_force(raw.get('pen_force'))
    except ValueError as error:
        raise PenPlanError(str(error)) from error
    notes = text(raw['notes'], 'notes') if 'notes' in raw else None
    return PenPlanSpec(policy, tuple(passes), slots(raw.get('slots', [])), omitted, repeated, force, notes)


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PenPlanError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=_no_duplicate_keys)
    except (OSError, ValueError) as error:
        raise PenPlanError(f'invalid plan {path}: {error}') from error


def load_pen_plan(path: Path) -> PenPlanSpec:
    return parse_pen_plan(read_json(path))


def _sha(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise PenPlanError(f'{label} must be a lowercase SHA-256')
    return value


_RESOLVED = ('schema_version', 'kind', 'source_svg', 'source_svg_sha256', 'source_manifest_hash',
             'pass_id', 'pass_number', 'pass_count', 'policy', 'assignments', 'physical_slots',
             'omitted_layers', 'repeated_layers', 'slots', 'hpgl_sha256', 'pen_force')


def parse_resolved(raw) -> ResolvedPlotPass:
    _version(raw)
    object_fields(raw, _RESOLVED)
    if raw['kind'] != RESOLVED_KIND:
        raise PenPlanError('resolved kind must be resolved-dpx3300-plot-pass')
    a = assignments(raw['assignments'])
    physical = tuple(integer(v, 1, 8, 'physical_slots') for v in raw['physical_slots'])
    if physical != tuple(x.physical_slot for x in a):
        raise PenPlanError('physical_slots differs from assignment order')
    count = integer(raw['pass_count'], 1, 10000, 'pass_count')
    number = integer(raw['pass_number'], 1, count, 'pass_number')
    policy = raw['policy']
    if policy not in ('preserve', 'compact', 'explicit'):
        raise PenPlanError('invalid policy')
    omitted, repeated = ids(raw['omitted_layers'], 'omitted_layers'), ids(raw['repeated_layers'], 'repeated_layers')
    if set(omitted).intersection(repeated) or set(omitted).intersection(v for x in a for v in x.layer_ids):
        raise PenPlanError('conflicting resolved omission/repetition')
    metadata = slots(raw['slots'])
    if any(s.slot not in physical for s in metadata):
        raise PenPlanError('resolved slot metadata refers to unused slot')
    force_audit = None
    if raw['pen_force'] is not None:
        f = raw['pen_force']
        object_fields(f, ('spec', 'effective_slot_forces'))
        if f['spec'] is None:
            raise PenPlanError('force audit requires configured spec')
        try:
            spec = parse_force(f['spec'])
        except ValueError as error:
            raise PenPlanError(str(error)) from error
        expected = tuple((s, effective_force(spec, s)) for s in sorted(physical))
        if any(gf is None for s, gf in expected):
            raise PenPlanError('missing used-slot force')
        expected_json = [{'slot': s, 'force_gf': gf} for s, gf in expected]
        # Type-aware validation prevents bool == integer from accepting forged audit values.
        if not isinstance(f['effective_slot_forces'], list):
            raise PenPlanError('effective_slot_forces must be an array')
        for item in f['effective_slot_forces']:
            object_fields(item, ('slot', 'force_gf'))
            integer(item['slot'], 1, 8, 'force slot')
            if type(item['force_gf']) is not int:
                raise PenPlanError('effective force must be an integer')
        if f['effective_slot_forces'] != expected_json:
            raise PenPlanError('effective_slot_forces do not match force spec')
        force_audit = ForceAudit(spec, expected)
    manifest = raw['source_manifest_hash']
    if manifest is not None:
        _sha(manifest, 'source_manifest_hash')
    return ResolvedPlotPass(text(raw['source_svg'], 'source_svg'), _sha(raw['source_svg_sha256'], 'source_svg_sha256'),
        manifest, text(raw['pass_id'], 'pass_id'), number, count, policy, a, physical, omitted,
        repeated, metadata, _sha(raw['hpgl_sha256'], 'hpgl_sha256'), force_audit)


def resolved_payload(plan: ResolvedPlotPass) -> dict:
    raw = asdict(plan)
    raw.update(schema_version=SCHEMA_VERSION, kind=RESOLVED_KIND)
    raw['assignments'] = [{'layer_ids': list(a.layer_ids), 'physical_slot': a.physical_slot} for a in plan.assignments]
    for key in ('physical_slots', 'omitted_layers', 'repeated_layers'):
        raw[key] = list(raw[key])
    raw['slots'] = [{k: v for k, v in asdict(s).items() if v is not None} for s in plan.slots]
    raw['pen_force'] = None if plan.pen_force is None else {
        'spec': force_payload(plan.pen_force.spec),
        'effective_slot_forces': [{'slot': s, 'force_gf': gf} for s, gf in plan.pen_force.effective_slot_forces]}
    parse_resolved(raw)
    return raw


def load_resolved_plot_pass(path: Path) -> ResolvedPlotPass:
    return parse_resolved(read_json(path))


def write_resolved_plot_pass(path: Path, plan: ResolvedPlotPass) -> None:
    Path(path).write_text(json.dumps(resolved_payload(plan), indent=2)+'\n', encoding='utf-8')
