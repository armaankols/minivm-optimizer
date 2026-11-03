"""Replace stable SORT by IOTA only for a guaranteed stored-order prefix."""
from dead_code import columns, roles


def stored_orders(schema, declared):
    orders = {}
    for table_name, table in schema.items():
        key = table_name.lower()
        names = table.get('sorted')
        if names is None:
            continue
        if (not isinstance(names, list) or not names
                or any(not isinstance(name, str) for name in names)):
            continue
        normalized = tuple(name.lower() for name in names)
        if len(set(normalized)) != len(normalized):
            continue
        if all(key+'.'+name in declared for name in normalized):
            orders[key] = normalized
    return orders


def iota_line(line, start, dest, source):
    # SORT operands are register sort keys, not literals; any semicolon begins
    # its comment. Preserve the comment, trailing spaces and exact line ending.
    end = line.find(';')
    if end < 0:
        end = len(line)
        if end and line[end-1] == '\n':
            end -= 1
        if end and line[end-1] == '\r':
            end -= 1
    while end > start and line[end-1] in ' \t':
        end -= 1
    return line[:start] + 'IOTA ' + dest + ', ' + source + line[end:]


def replace_sorted(source, schema, parse, is_register):
    declared = columns(schema)
    if declared is None:
        return source
    orders = stored_orders(schema, declared)
    origins, output = {}, []
    pieces = source.split('\n')
    for index, body in enumerate(pieces):
        line = body + ('\n' if index < len(pieces)-1 else '')
        parsed = parse(line)
        if parsed is None:
            if line.strip() and not line.lstrip().startswith(';'):
                return source
            output.append(line)
            continue
        op, args, span = parsed
        effects = roles(op, args, is_register)
        if effects is None:
            return source
        writes, _ = effects
        origin = None
        if op == 'LOAD' and args[1].lower() in declared:
            parts = args[1].lower().split('.')
            if len(parts) == 2:
                origin = tuple(parts)
        elif op == 'SORT':
            keys = [key.split() for key in args[1:]]
            loaded = [origins.get(key[0]) for key in keys]
            if (all(key[1].upper() == 'ASC' and key[2].upper() == 'NF' for key in keys)
                    and all(item is not None for item in loaded)):
                table = loaded[0][0]
                names = tuple(item[1] for item in loaded)
                if (all(item[0] == table for item in loaded)
                        and names == orders.get(table, ())[:len(names)]):
                    line = iota_line(line, span[0], args[0], keys[0][0])
        # Read origins before writes, especially when SORT destination is a key.
        # Positions are not a direct stored-column origin. Both join outputs and
        # every other write invalidate previous origins, irrespective of type.
        for dest in writes:
            origins.pop(dest, None)
        if origin is not None:
            origins[args[0]] = origin
        output.append(line)
    return ''.join(output)
