import json

import pytest

from pen_plan_io import parse_pen_plan, load_pen_plan
from pen_plan_models import LayerInfo
from pen_plan_resolution import resolve_plot_passes


def test_schema3_compact_preserve_and_explicit_share_assignments():
    layers = (LayerInfo('pen-2', True, 1), LayerInfo('pen-6', True, 2))
    compact = resolve_plot_passes(layers, parse_pen_plan({'schema_version': 3, 'policy': 'compact'}))
    assert [a.physical_slot for a in compact[0].assignments] == [1, 2]
    preserved = resolve_plot_passes(layers, parse_pen_plan({'schema_version': 3, 'policy': 'preserve'}))
    assert [a.physical_slot for a in preserved[0].assignments] == [2, 6]
    explicit = parse_pen_plan({'schema_version': 3, 'policy': 'explicit', 'passes': [
        {'id': 'ink', 'assignments': [{'layer_ids': ['pen-2', 'pen-6'], 'physical_slot': 7}]}]})
    assert resolve_plot_passes(layers, explicit)[0].assignments[0].layer_ids == ('pen-2', 'pen-6')


@pytest.mark.parametrize('raw', [{'schema_version': 1, 'policy': 'compact'},
    {'schema_version': 2, 'passes': []}, {'schema_version': True, 'policy': 'compact'},
    {'schema_version': 3, 'policy': 'compact', 'pen_plan': {}},
    {'schema_version': 3, 'policy': 'compact', 'pen_force': None},
    {'schema_version': 3, 'policy': 'compact', 'passes': []},
    {'schema_version': 3, 'policy': 'explicit'},
    {'schema_version': 3, 'policy': 'compact', 'slots': [{'slot': True}]},
    {'schema_version': 3, 'policy': 'compact', 'repeated_layers': ['a']}])
def test_invalid_or_stale_authored_formats_fail(raw):
    with pytest.raises(ValueError):
        parse_pen_plan(raw)


def test_later_pass_requires_force_for_every_used_slot():
    spec = parse_pen_plan({'schema_version': 3, 'policy': 'explicit', 'passes': [
        {'id': 'one', 'assignments': [{'layer_ids': ['a'], 'physical_slot': 1}]},
        {'id': 'two', 'assignments': [{'layer_ids': ['b'], 'physical_slot': 2}]}],
        'pen_force': {'mode': 'software', 'slot_overrides': [{'slot': 1, 'force_gf': 65}]}})
    with pytest.raises(ValueError, match='slot 2'):
        resolve_plot_passes((LayerInfo('a', True, 1), LayerInfo('b', True, 2)), spec)


def test_omission_repetition_and_missing_layers():
    layers = (LayerInfo('a', True, 1), LayerInfo('b', True, 2))
    spec = parse_pen_plan({'schema_version': 3, 'policy': 'compact', 'omitted_layers': ['b']})
    assert resolve_plot_passes(layers, spec)[0].assignments[0].layer_ids == ('a',)
    bad = parse_pen_plan({'schema_version': 3, 'policy': 'explicit', 'passes': [
        {'id': 'one', 'assignments': [{'layer_ids': ['a'], 'physical_slot': 1}]}]})
    with pytest.raises(ValueError, match='unaccounted'):
        resolve_plot_passes(layers, bad)
    with pytest.raises(ValueError, match='preserve'):
        resolve_plot_passes(layers, parse_pen_plan({'schema_version': 3, 'policy': 'preserve'}))


def test_json_duplicate_keys_are_not_last_key_wins(tmp_path):
    p = tmp_path/'plan.json'
    p.write_text('{"schema_version":3,"policy":"compact","policy":"preserve"}')
    with pytest.raises(ValueError, match='duplicate'):
        load_pen_plan(p)


def test_resolved_roundtrip_recomputes_effective_force_and_checks_order(tmp_path):
    from pen_force import parse_force
    from pen_plan_io import load_resolved_plot_pass, resolved_payload, write_resolved_plot_pass
    from pen_plan_models import Assignment, ForceAudit, ResolvedPlotPass, SlotSpec
    spec = parse_force({'mode': 'software', 'default_gf': 65})
    p = ResolvedPlotPass('drawing.svg', 'a'*64, None, 'plot', 1, 1, 'compact',
        (Assignment(('pen-2',), 1),), (1,), (), (), (SlotSpec(1, tool='Micron'),),
        'b'*64, ForceAudit(spec, ((1, 65),)))
    path = tmp_path/'drawing.resolved.penplan.json'
    write_resolved_plot_pass(path, p)
    assert load_resolved_plot_pass(path) == p
    raw = resolved_payload(p)
    raw['pen_force']['effective_slot_forces'][0]['force_gf'] = 50
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='effective_slot_forces'):
        load_resolved_plot_pass(path)
    raw = resolved_payload(p)
    raw['physical_slots'] = [2]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='assignment order'):
        load_resolved_plot_pass(path)
