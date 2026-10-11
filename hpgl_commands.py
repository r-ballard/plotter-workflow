"""Semicolon HP-GL commands with label terminator awareness and source spans."""

import re
from dataclasses import dataclass


class HPGLParseError(ValueError):
    pass


@dataclass(frozen=True)
class HPGLCommand:
    opcode: str
    arguments: str
    start: int
    end: int


def tokenize_hpgl(text: str) -> tuple[HPGLCommand, ...]:
    result = []
    i = 0
    terminator = '\x03'
    while i < len(text):
        if text[i].isspace() or text[i] == ';':
            i += 1
            continue
        start = i
        opcode = text[i:i+2].upper()
        if not re.fullmatch('[A-Z]{2}', opcode):
            raise HPGLParseError(f'invalid HP-GL opcode at offset {i}')
        i += 2
        end = text.find(terminator if opcode == 'LB' else ';', i)
        if end < 0:
            raise HPGLParseError(f'unterminated {opcode} at offset {start}')
        arguments = text[i:end] if opcode == 'LB' else text[i:end].strip()
        i = end+1
        result.append(HPGLCommand(opcode, arguments, start, i))
        if opcode == 'DT':
            if not arguments:
                terminator = '\x03'
            elif len(arguments) == 1 or (len(arguments) == 3 and arguments[1:] in (',0', ',1')):
                terminator = arguments[0]
            else:
                raise HPGLParseError('DT requires one terminator and optional mode 0 or 1')
        elif opcode == 'IN':
            terminator = '\x03'
    return tuple(result)
