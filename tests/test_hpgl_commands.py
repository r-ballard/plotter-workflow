import pytest

from hpgl_commands import tokenize_hpgl


def test_tokens_keep_original_spans_and_ignore_command_like_labels():
    text = ' in; DT$;LBhello;FS65;IN;$SP2;PD1,2;'
    commands = tokenize_hpgl(text)
    assert [c.opcode for c in commands] == ['IN', 'DT', 'LB', 'SP', 'PD']
    assert commands[2].arguments == 'hello;FS65;IN;'
    assert text[commands[3].start:commands[3].end] == 'SP2;'
    assert tokenize_hpgl('LBFS65;\x03;SP1;')[0].arguments == 'FS65;'


@pytest.mark.parametrize('text', ['I;', 'SP1', 'LBmissing;', 'DTxx;SP1;', '\x1bIN;'])
def test_malformed_commands_fail(text):
    with pytest.raises(ValueError):
        tokenize_hpgl(text)
