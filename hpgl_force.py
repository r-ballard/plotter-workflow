"""Insert and validate physical force state without changing drawing geometry."""

import re

from hpgl_commands import tokenize_hpgl
from pen_force import ForceSpec, effective_force, force_code, force_gf


class ForceValidationError(ValueError):
    pass


def _integers(arguments, *, count, opcode):
    parts = arguments.split(',')
    if len(parts) not in count or any(not re.fullmatch(r'\d+', p.strip()) for p in parts):
        raise ForceValidationError(f'invalid {opcode} arguments: {arguments!r}')
    return tuple(int(p.strip()) for p in parts)


def _fs(arguments):
    values = _integers(arguments, count=(1, 2), opcode='FS')
    gf = force_gf(values[0])
    slot = values[1] if len(values) == 2 else None
    if slot is not None and not 1 <= slot <= 8:
        raise ForceValidationError('FS slot must be 1 through 8')
    return gf, slot


def validate_force(text: str, spec: ForceSpec | None, used_slots: tuple[int, ...]) -> None:
    if spec is None:
        return
    for slot in used_slots:
        if effective_force(spec, slot) is None:
            raise ForceValidationError(f'missing force for physical slot {slot}')
    slot, down = 0, False
    forces = {s: 20 for s in range(1, 9)}
    for command in tokenize_hpgl(text):
        op, args = command.opcode, command.arguments
        if op in ('IN', 'DF'):
            if args or down:
                raise ForceValidationError(f'unsafe or malformed {op} reset')
            slot, down = 0, False
            forces = {s: 20 for s in range(1, 9)}
        elif op == 'FS':
            if spec.mode == 'panel':
                raise ForceValidationError('panel-force job must not contain FS')
            gf, target = _fs(args)
            if target is None:
                forces = {s: gf for s in forces}
            else:
                forces[target] = gf
        elif op == 'SP':
            selected, = _integers(args, count=(1,), opcode=op)
            if not 0 <= selected <= 8 or down:
                raise ForceValidationError('invalid SP selection or pen change while down')
            slot = selected
        elif op in ('PA', 'PR', 'PU', 'PD'):
            if op == 'PU':
                down = False
            elif op == 'PD':
                down = True
            if down:
                if slot not in used_slots:
                    raise ForceValidationError(f'drawing with unreviewed physical slot {slot}')
                if spec.mode == 'software' and forces[slot] != effective_force(spec, slot):
                    raise ForceValidationError(f'incorrect force at {op} for physical slot {slot}')
        elif op not in ('VS', 'DT', 'PG'):
            message = 'convert text to paths' if op == 'LB' else 'unsupported drawing/state command'
            raise ForceValidationError(f'{op}: {message} in force-managed HP-GL')


def apply_force(text: str, spec: ForceSpec | None) -> str:
    if spec is None:
        return text
    commands = tokenize_hpgl(text)
    for c in commands:
        if c.opcode == 'FS':
            gf, slot = _fs(c.arguments)
            expected = spec.default_gf if slot is None else effective_force(spec, slot)
            if spec.mode == 'panel' or gf != expected:
                raise ForceValidationError('conflicting preexisting FS command')
    block = ''
    if spec.mode == 'software':
        if spec.default_gf is not None:
            block += f'FS{force_code(spec.default_gf)};'
        block += ''.join(f'FS{force_code(gf)},{s};' for s, gf in spec.slot_overrides)
    # Each reset is followed by fresh force settings; initialize at the beginning too.
    pieces = [block if not commands or commands[0].opcode not in ('IN', 'DF') else '']
    last = 0
    for c in commands:
        if c.opcode in ('IN', 'DF'):
            pieces.extend((text[last:c.end], block))
            last = c.end
    pieces.append(text[last:])
    out = ''.join(pieces)
    selected = tuple(dict.fromkeys(_integers(c.arguments, count=(1,), opcode='SP')[0]
                                   for c in commands if c.opcode == 'SP' and c.arguments != '0'))
    validate_force(out, spec, selected)
    return out
