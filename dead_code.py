"""Remove dead computations only from a small proven-total whitelist.

Facts come from guaranteed column types, never stats. Potentially failing
instructions always remain and keep their input definitions live. Resource-limit
failures are outside the semantic-error equivalence argument (see docs/dce.md).
"""
import re

UNARY = {'NEG', 'WRAP', 'TRUNC', 'NOT', 'ISNULL', 'NULLIFE', 'UPPER', 'RTRIM',
         'TRIM', 'LEN', 'YEAR', 'MONTH', 'DAY', 'DOW'}
BINARY = {'ADD', 'SUB', 'MUL', 'DIV', 'IDIV', 'MOD', 'EQ', 'NE', 'LT', 'LE',
          'GT', 'GE', 'IS', 'AND', 'OR', 'NVL', 'NULLIF', 'CAT', 'DATEADD', 'DATEDIFF'}
STR_UNARY = {'NULLIFE', 'UPPER', 'RTRIM', 'TRIM', 'LEN'}
DATE_UNARY = {'YEAR', 'MONTH', 'DAY', 'DOW'}


def integer(text, positive=False):
    # Counts are unbounded literals; syntax alone suffices, without int conversion.
    return re.fullmatch(r'[0-9]+', text) is not None and (not positive or bool(text.lstrip('0')))


def roles(op, args, is_register):
    """Return exact writes/reads roles, or None to disable the entire pass."""
    if op == 'OUT':
        return (set(), set(args)) if args and all(map(is_register, args)) else None
    if not args or not is_register(args[0]):
        return None
    writes = {args[0]}
    if op in ('NLJOIN', 'HJOIN'):
        if (len(args) not in (4, 5) or not all(map(is_register, args[:4]))
                or (len(args) == 5 and args[4].upper() != 'NULLEQ')):
            return None
        return set(args[:2]), set(args[2:4])
    if op in ('SORT', 'TOPK'):
        keys = args[1:] if op == 'SORT' else args[2:]
        if not keys or (op == 'TOPK' and (len(args) < 3 or not integer(args[1]))):
            return None
        reads = set()
        for key in keys:
            parts = key.split()
            if (len(parts) != 3 or not is_register(parts[0])
                    or parts[1].upper() not in ('ASC', 'DESC')
                    or parts[2].upper() not in ('NF', 'NL')):
                return None
            reads.add(parts[0])
        return writes, reads
    if op == 'GROUP':
        return (writes, set(args[1:])) if len(args) >= 2 and all(map(is_register, args[1:])) else None
    arity = (2 if op in UNARY | {'LOAD', 'IOTA', 'IDX', 'GALL', 'GID', 'GFIRST', 'GCOUNT'} else
             3 if op in BINARY | {'FILL', 'GATHER', 'SLICE', 'LEFT', 'GCOUNTV', 'GSUM', 'GMIN', 'GMAX'} else
             4 if op in {'IF', 'SUBSTR'} else None)
    if arity is None or len(args) != arity:
        return None
    sources = ([] if op == 'LOAD' else [args[2]] if op == 'FILL' else
               [args[1]] if op in ('LEFT', 'SUBSTR', 'SLICE') else args[1:])
    return writes, {arg for arg in sources if is_register(arg)}


def columns(schema):
    """Guaranteed stored types; reject ambiguous/malformed declarations."""
    if not isinstance(schema, dict):
        return None
    result, tables = {}, set()
    for table_name, table in schema.items():
        if not isinstance(table, dict) or table_name.lower() in tables:
            return None
        tables.add(table_name.lower())
        stored = table.get('columns')
        if not isinstance(stored, list):
            return None
        for column in stored:
            if not isinstance(column, dict) or not isinstance(column.get('name'), str):
                return None
            kind = column.get('type')
            key = (table_name+'.'+column['name']).lower()
            if kind not in ('INT', 'NUM', 'STR', 'DATE') or key in result:
                return None
            result[key] = kind
    return result


def without_instruction(line, opcode_start):
    # Only whitelist forms with register sources/counts can reach here, so the
    # first semicolon is a comment rather than a character inside a literal.
    comment = line.find(';')
    if comment >= 0:
        return line[:opcode_start] + line[comment:]
    return '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''


def eliminate_dead(source, schema, parse, is_register):
    stored = columns(schema)
    if stored is None:
        return source
    facts, assigned, nodes = {}, set(), []
    pieces = source.split('\n')
    for index, body in enumerate(pieces):
        line = body + ('\n' if index < len(pieces)-1 else '')
        parsed = parse(line)
        if parsed is None:
            if line.strip() and not line.lstrip().startswith(';'):
                return source
            nodes.append((line, set(), set(), False, 0))
            continue
        op, args, span = parsed
        effects = roles(op, args, is_register)
        if effects is None:
            return source
        writes, reads = effects
        kind, total = None, False
        src = facts.get(args[1]) if len(args) > 1 else None
        if op == 'LOAD':
            kind = stored.get(args[1].lower())
            total = kind is not None
        elif op == 'IOTA' and src is not None:
            kind, total = 'INT', True
        elif op == 'SLICE' and src is not None and integer(args[2]):
            kind, total = src, True
        elif op == 'ISNULL' and src is not None:
            kind, total = 'BOOL', True
        elif op in STR_UNARY and src == 'STR':
            kind, total = ('INT' if op == 'LEN' else 'STR'), True
        elif op == 'LEFT' and src == 'STR' and integer(args[2]):
            kind, total = 'STR', True
        elif (op == 'SUBSTR' and src == 'STR'
                and integer(args[2], positive=True) and integer(args[3])):
            kind, total = 'STR', True
        elif op in DATE_UNARY and src == 'DATE':
            kind, total = 'INT', True
        # An apparently dead overwrite can release a large old register value.
        # Removing it may extend that value's lifetime and introduce a memory
        # limit error. Only first definitions are eligible for deletion.
        total = total and writes.isdisjoint(assigned)
        assigned.update(writes)
        # Read facts before any aliased write; every unmodeled destination loses
        # its old column/type fact (including both outputs of a join).
        for dest in writes:
            facts[dest] = None
        if len(writes) == 1 and kind is not None:
            facts[args[0]] = kind
        nodes.append((line, writes, reads, total, span[0]))
    live, output = set(), []
    for line, writes, reads, total, start in reversed(nodes):
        if total and writes.isdisjoint(live):
            output.append(without_instruction(line, start))
            continue
        live.difference_update(writes)
        live.update(reads)
        output.append(line)
    return ''.join(reversed(output))
