#!/usr/bin/env python3
"""Select joins, replace guaranteed stored-order sorts, and remove safe dead work.

joins.md explicitly guarantees the same ordered pairs and semantic errors. None
of these estimates establish a semantic precondition. Resource-limit failures
remain subject to the assignment's documented work-accounting ambiguity.
"""
from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
import re
import sys

REGISTER = re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')
KEYWORDS = {'NULL', 'TRUE', 'FALSE', 'ASC', 'DESC', 'NF', 'NL', 'NULLEQ'}
NUMERIC = {'INT', 'NUM'}
NON_STRING = {'INT', 'NUM', 'DATE', 'BOOL'}
MAX_VALUES = 4_000_000
MAX_PROGRAM_BYTES = 4 * 1024 * 1024  # docs/running.md: inclusive UTF-8 file limit


@dataclasses.dataclass(frozen=True)
class Estimate:
    rows: float | None = None
    kind: str | None = None
    avg_bytes: float | None = None
    distinct: float | None = None


UNKNOWN = Estimate()


def register(text):
    return REGISTER.fullmatch(text) is not None and text.upper() not in KEYWORDS


def number(value, maximum=MAX_VALUES):
    if type(value) not in (int, float):
        return None
    try:
        return float(value) if math.isfinite(value) and 0 <= value <= maximum else None
    except (OverflowError, ValueError):
        return None


def instruction(line):
    """Find opcode span and operands, respecting escaped quotes and comments.

    Token spans refer to the original decoded source. Emission replaces only
    the opcode span, preserving comments, casing, CRLF and the final newline.
    """
    match = re.match(r'[ \t]*([A-Za-z][A-Za-z_0-9]*)[ \t]+', line)
    if match is None:
        return None
    operands, start, quoted = [], match.end(), False
    i = start
    while i < len(line):
        char = line[i]
        if char == "'":
            if quoted and i + 1 < len(line) and line[i + 1] == "'":
                i += 2
                continue
            quoted = not quoted
        elif not quoted and char in ',;':
            operands.append(line[start:i].strip())
            if char == ';':
                break
            start = i + 1
        elif not quoted and (char in '\x1c\x1d\x1e\x1f'
                             or (not char.isascii() and not char.isspace())):
            # Python treats FS/GS/RS/US as whitespace and Unicode case folding
            # accepts token lookalikes (e.g. long-s or Kelvin sign) that MiniVM
            # rejects. Never prove a rewrite from those tokens. Quoted strings
            # and comments remain unrestricted data; VM Unicode whitespace is OK.
            return None
        i += 1
    else:
        operands.append(line[start:].strip())
    if quoted or not operands or any(not operand for operand in operands):
        return None
    return match.group(1).upper(), operands, match.span(1)


def literal(text):
    if text.upper() in ('NULL', 'TRUE', 'FALSE'):
        return Estimate(kind='BOOL' if text.upper() != 'NULL' else None,
                        avg_bytes=0, distinct=0 if text.upper() == 'NULL' else 1)
    if re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', text):
        return Estimate(kind='NUM' if '.' in text else 'INT', avg_bytes=0, distinct=1)
    if re.fullmatch(r'#[0-9]{4}-[0-9]{2}-[0-9]{2}#', text):
        return Estimate(kind='DATE', avg_bytes=0, distinct=1)
    if re.fullmatch(r"'(?:[^']|'')*'", text):
        return Estimate(kind='STR', avg_bytes=len(text[1:-1].replace("''", "'").encode('utf-8')), distinct=1)
    return UNKNOWN


def count(text):
    if re.fullmatch(r'[0-9]+', text) is None:
        return None
    # Counts beyond the per-register limit are effectively unbounded here. Avoid
    # expensive conversion of arbitrarily long integer-operand spellings.
    significant = text.lstrip('0') or '0'
    return float(MAX_VALUES) if len(significant) > 7 else min(float(significant), MAX_VALUES)


def load_estimates(schema):
    loaded = {}
    if not isinstance(schema, dict):
        return loaded
    for table_name, table in schema.items():
        if not isinstance(table, dict):
            continue
        stats = table.get('stats', {})
        stats = stats if isinstance(stats, dict) else {}
        rows = number(stats.get('rows'), 10_000)
        column_stats = stats.get('columns', {})
        column_stats = column_stats if isinstance(column_stats, dict) else {}
        column_stats = {k.lower(): v for k, v in column_stats.items()}
        columns = table.get('columns', [])
        if not isinstance(columns, list):
            continue
        for column in columns:
            if not isinstance(column, dict) or not isinstance(column.get('name'), str):
                continue
            key = (str(table_name) + '.' + column['name']).lower()
            kind = str(column.get('type', '')).upper()
            info = column_stats.get(column['name'].lower(), {})
            info = info if isinstance(info, dict) else {}
            avg_bytes = number(info.get('avg_bytes'), 32 * 1024 * 1024) if kind == 'STR' else 0
            loaded[key] = Estimate(rows, kind, avg_bytes, number(info.get('distinct'), 10_000))
    return loaded


def costs(left, right):
    if left.rows is None or right.rows is None:
        return None
    if left.kind == right.kind == 'STR':
        if left.avg_bytes is None or right.avg_bytes is None:
            return None
        shorter = min(left.avg_bytes, right.avg_bytes)
        nl = left.rows * right.rows * (1 + shorter)
        hashed = left.rows * (6 + left.avg_bytes) + right.rows * (6 + right.avg_bytes)
    elif left.kind in NON_STRING and right.kind in NON_STRING and (
            left.kind == right.kind or {left.kind, right.kind} <= NUMERIC):
        nl = left.rows * right.rows
        hashed = 6 * (left.rows + right.rows)
    else:
        return None
    # Base 4 and 2 per emitted pair are common to both algorithms. For strings,
    # min(mean bytes) is a heuristic for mean(min(bytes)); not an identity.
    return nl, hashed


UNARY = {'NEG', 'WRAP', 'TRUNC', 'NOT', 'ISNULL', 'NULLIFE', 'UPPER', 'RTRIM',
         'TRIM', 'LEN', 'YEAR', 'MONTH', 'DAY', 'DOW'}
BINARY = {'ADD', 'SUB', 'MUL', 'DIV', 'IDIV', 'MOD', 'EQ', 'NE', 'LT', 'LE',
          'GT', 'GE', 'IS', 'AND', 'OR', 'NVL', 'NULLIF', 'CAT', 'DATEADD', 'DATEDIFF'}
BOOL_OPS = {'EQ', 'NE', 'LT', 'LE', 'GT', 'GE', 'IS', 'AND', 'OR', 'NOT', 'ISNULL'}
INT_OPS = {'WRAP', 'TRUNC', 'IDIV', 'MOD', 'LEN', 'YEAR', 'MONTH', 'DAY', 'DOW', 'DATEDIFF'}
STRING_OPS = {'NULLIFE', 'UPPER', 'RTRIM', 'TRIM', 'LEFT', 'SUBSTR', 'CAT'}


def select_joins(source, schema):
    loaded, registers, output = load_estimates(schema), {}, []
    # MiniVM instructions are LF-delimited. str.splitlines also treats Unicode
    # and control characters *inside valid string literals* as line boundaries,
    # which could expose literal text as a fake join and corrupt result values.
    lines = source.split('\n')
    for index, body in enumerate(lines):
        line = body + ('\n' if index < len(lines) - 1 else '')
        parsed = instruction(line)
        if parsed is None:
            # Blank/comment lines cannot write registers. Unknown syntax might.
            if line.strip() and not line.lstrip().startswith(';'):
                registers.clear()
            output.append(line)
            continue
        op, args, span = parsed
        get = lambda name: registers.get(name, UNKNOWN) if register(name) else literal(name)
        dest = args[0]
        result = UNKNOWN
        if op in ('NLJOIN', 'HJOIN'):
            valid = len(args) in (4, 5) and all(register(a) for a in args[:4])
            valid = valid and (len(args) == 4 or args[4].upper() == 'NULLEQ')
            if not valid:
                registers.clear()
            else:
                left, right = get(args[2]), get(args[3])  # before aliased writes
                comparison = costs(left, right)
                if comparison is not None:
                    nl, hashed = comparison
                    chosen = 'NLJOIN' if nl < hashed else 'HJOIN' if hashed < nl else op
                    if chosen != op:
                        line = line[:span[0]] + chosen + line[span[1]:]
                rows = None
                if left.rows is not None and right.rows is not None:
                    if left.rows == 0 or right.rows == 0:
                        rows = 0.0
                    elif left.distinct is not None and right.distinct is not None:
                        rows = min(MAX_VALUES, left.rows * right.rows / max(1, left.distinct, right.distinct))
                # Pair columns have equal length; same-destination assignment
                # leaves the right positions, as the VM documents.
                registers[args[0]] = Estimate(rows, 'INT', 0, min(left.rows, rows) if rows is not None else None)
                registers[args[1]] = Estimate(rows, 'INT', 0, min(right.rows, rows) if rows is not None else None)
            output.append(line)
            continue
        if op == 'LOAD' and len(args) == 2:
            result = loaded.get(args[1].lower(), UNKNOWN)
        elif op == 'FILL' and len(args) == 3:
            result = dataclasses.replace(literal(args[1]), rows=get(args[2]).rows)
        elif op == 'IOTA' and len(args) == 2:
            rows = get(args[1]).rows
            result = Estimate(rows, 'INT', 0, rows)
        elif op == 'IDX' and len(args) == 2:
            rows = get(args[1]).rows
            rows = rows / 2 if rows is not None else None
            result = Estimate(rows, 'INT', 0, rows)
        elif op in ('SORT', 'TOPK') and len(args) >= (2 if op == 'SORT' else 3):
            rows = get(args[1 if op == 'SORT' else 2].split()[0]).rows
            n = None if op == 'SORT' else count(args[1])
            if op == 'TOPK':
                rows = min(rows, n) if rows is not None and n is not None else None
            result = Estimate(rows, 'INT', 0, rows)
        elif op == 'GATHER' and len(args) == 3:
            result = dataclasses.replace(get(args[1]), rows=get(args[2]).rows)
        elif op == 'SLICE' and len(args) == 3:
            old, n = get(args[1]), count(args[2])
            result = dataclasses.replace(old, rows=min(old.rows, n) if old.rows is not None and n is not None else None)
        elif ((op in UNARY and len(args) == 2) or (op in BINARY and len(args) == 3)
              or (op == 'IF' and len(args) == 4) or (op == 'LEFT' and len(args) == 3)
              or (op == 'SUBSTR' and len(args) == 4)):
            inputs = [get(a) for a in args[1:] if register(a)]
            rows = inputs[0].rows if inputs else None
            kinds = {get(a).kind for a in args[1:]}
            kind = ('BOOL' if op in BOOL_OPS else 'INT' if op in INT_OPS else
                    'NUM' if op == 'DIV' else 'STR' if op in STRING_OPS else
                    'DATE' if op == 'DATEADD' else
                    next(iter(kinds)) if len(kinds) == 1 else
                    'NUM' if kinds <= NUMERIC else None)
            avg = inputs[0].avg_bytes if kind == 'STR' and inputs else 0 if kind in NON_STRING else None
            distinct = inputs[0].distinct if inputs and op in ('NVL', 'NULLIF') else None
            result = Estimate(rows, kind, avg, distinct)
        # Any unmodeled operation invalidates its destination. This includes
        # GROUP/GALL/aggregates: their cardinalities are deliberately unmodeled.
        if register(dest):
            registers[dest] = result
        else:
            registers.clear()
        output.append(line)
    return ''.join(output)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if len(argv) == 3 and argv[0] in ('--joins-only', '--no-sorted-order') else None
    if mode:
        argv = argv[1:]
    if len(argv) != 2:
        print('usage: ./optimize [--joins-only|--no-sorted-order] PROGRAM SCHEMA', file=sys.stderr)
        return 2
    try:
        original = Path(argv[0]).read_bytes()
        schema = json.loads(Path(argv[1]).read_text())
        source = original.decode('utf-8')
        selected = select_joins(source, schema)
        if mode != '--joins-only':
            if mode != '--no-sorted-order':
                from sorted_order import replace_sorted
                selected = replace_sorted(selected, schema, instruction, register)
            from dead_code import eliminate_dead
            selected = eliminate_dead(selected, schema, instruction, register)
        output = selected.encode('utf-8')
        # HJOIN -> NLJOIN adds a byte. Check after every pass has finished, since
        # later removals may offset growth. Preserve the original bytes if the
        # candidate would exceed the VM's file limit (including UTF-8 comments).
        if len(output) > MAX_PROGRAM_BYTES:
            output = original
        sys.stdout.buffer.write(output)
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print('optimize: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
