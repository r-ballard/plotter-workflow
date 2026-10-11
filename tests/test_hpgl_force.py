import pytest

from hpgl_force import apply_force, validate_force
from pen_force import parse_force

SOFTWARE = parse_force(
    {"mode": "software", "default_gf": 65, "slot_overrides": [{"slot": 2, "force_gf": 50}]}
)
PANEL = parse_force({"mode": "panel", "default_gf": 65})


def test_force_block_order_reset_reapplication_and_unmanaged_identity():
    text = "IN;SP1;PU0,0;PD1,1;PU;DF;SP2;PD2,2;PU;"
    out = apply_force(text, SOFTWARE)
    assert out.startswith("IN;FS7;FS5,2;SP1;")
    assert ";DF;FS7;FS5,2;SP2;" in out
    validate_force(out, SOFTWARE, (1, 2))
    assert apply_force(text, None) == text
    assert apply_force(text, PANEL) == text
    validate_force(text, PANEL, (1, 2))


def test_equivalent_codes_validate_and_hash_does_not_replace_force_check():
    validate_force("IN;FS8;SP1;PD1,1;PA2,2;PU;", SOFTWARE, (1,))
    for text in (
        "IN;FS5;SP1;PD1,1;",
        "IN;FS7;SP1;PD1,1;FS5;PA2,2;",
        "IN;FS7;SP1;PD1,1;PU;IN;PD2,2;",
        "IN;FS7;SP0;PD1,1;",
    ):
        with pytest.raises(ValueError):
            validate_force(text, SOFTWARE, (1,))


@pytest.mark.parametrize(
    "text",
    [
        "IN;FS65;SP1;PD1,1;",
        "IN;FS7.0;SP1;PD1,1;",
        "IN;FS;SP1;PD1,1;",
        "IN;SP1;CI10;",
        "DT$;LBFS65;IN;$SP1;PD1,1;",
    ],
)
def test_unchecked_or_conflicting_force_and_drawing_fail(text):
    with pytest.raises(ValueError):
        apply_force(text, SOFTWARE)


def test_panel_rejects_fs_and_missing_slot_is_not_a_default():
    with pytest.raises(ValueError):
        validate_force("IN;FS7;SP1;PD1,1;", PANEL, (1,))
    only_one = parse_force({"mode": "software", "slot_overrides": [{"slot": 1, "force_gf": 65}]})
    with pytest.raises(ValueError, match="slot 2"):
        validate_force("IN;FS7,1;SP2;PD1,1;", only_one, (2,))


def test_force_commands_do_not_change_preview_geometry():
    from scripts.preview_hpgl import trace

    text = "IN;SP1;PU0,0;PD1,1;PU;"
    assert trace(apply_force(text, SOFTWARE)) == trace(text)


def test_even_20_gf_requires_explicit_software_setting():
    spec = parse_force({'mode': 'software', 'default_gf': 20})
    with pytest.raises(ValueError, match='incorrect force'):
        validate_force('IN;SP1;PD1,1;', spec, (1,))
    validate_force('IN;FS1;SP1;PD1,1;', spec, (1,))
