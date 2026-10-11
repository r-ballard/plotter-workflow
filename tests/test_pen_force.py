import pytest

from pen_force import effective_force, force_code, force_gf, force_payload, parse_force


def test_force_mapping_and_equivalent_codes():
    for i, gf in enumerate((20, 35, 50, 65, 80, 95, 110, 125)):
        assert force_code(gf) == 2*i+1
        assert force_gf(2*i+1) == force_gf(2*i+2) == gf
    assert force_code(65) == 7 and force_gf(8) == 65


def test_force_overrides_are_canonical_and_unspecified_slots_stay_unspecified():
    spec = parse_force({'mode': 'software', 'slot_overrides': [
        {'slot': 8, 'force_gf': 65}, {'slot': 2, 'force_gf': 50}]})
    assert spec.slot_overrides == ((2, 50), (8, 65))
    assert effective_force(spec, 1) is None
    assert effective_force(spec, 8) == 65
    assert force_payload(spec)['slot_overrides'][0] == {'slot': 2, 'force_gf': 50}
    default = parse_force({'mode': 'panel', 'default_gf': 65,
                          'slot_overrides': [{'slot': 2, 'force_gf': 35}]})
    assert effective_force(default, 2) == 35 and effective_force(default, 8) == 65
    assert parse_force(None) is None


@pytest.mark.parametrize('raw', [True, '65', {}, {'mode': 'other', 'default_gf': 65},
    {'mode': 'software'}, {'mode': 'panel', 'default_gf': 66},
    {'mode': 'panel', 'default_gf': True}, {'mode': 'panel', 'default_gf': '65'},
    {'mode': 'panel', 'default_gf': 65.0}, {'mode': 'panel', 'default_gf': None},
    {'mode': 'panel', 'default_gf': 65, 'extra': 0},
    {'mode': 'panel', 'slot_overrides': [{'slot': True, 'force_gf': 65}]},
    {'mode': 'panel', 'slot_overrides': [{'slot': 9, 'force_gf': 65}]},
    {'mode': 'panel', 'slot_overrides': [{'slot': 1, 'force_gf': 65}]*2},
    {'mode': 'panel', 'slot_overrides': None}])
def test_invalid_force_specs_fail(raw):
    with pytest.raises(ValueError):
        parse_force(raw)


@pytest.mark.parametrize('fn,value', [(force_code, True), (force_code, 65.0),
                                   (force_gf, 0), (force_gf, 17), (force_gf, '7')])
def test_invalid_codes_fail(fn, value):
    with pytest.raises(ValueError):
        fn(value)
