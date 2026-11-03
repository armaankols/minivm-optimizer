#!/usr/bin/env python3
"""Independent differential tester for executables implementing optimize.

Fixtures declare output types because MiniVM's JSON encoding does not distinguish
NUM/large INT/STR/DATE strings. Unordered comparison matches complete rows, never
individual columns. Relative tolerance is symmetric; zero has no absolute slack.
The suite is evidence of soundness, not a proof. All random seeds are fixed.
"""
from __future__ import annotations

import collections
import dataclasses
import datetime
import decimal
import json
import os
from pathlib import Path
import random
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
REL_TOL = decimal.Decimal('0.000001')
SEEDS = (1729, 8675309)


class EvaluationError(Exception):
    """Evaluator infrastructure, invalid baseline, or exhausted global budget."""


class Defect(Exception):
    """An optimizer has an executable witness of a contract violation."""


@dataclasses.dataclass
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    issue: str | None = None


def run_process(argv, timeout, deadline, stdout_limit=4 * 1024 * 1024,
                stderr_limit=256 * 1024):
    """Bound time AND captured bytes; kill descendant processes on every path.

    POSIX process groups also cover children keeping inherited pipes open after
    their parent exits. The deadline is absolute monotonic time, across all calls.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise EvaluationError('overall evaluation deadline exhausted')
    cap = min(timeout, remaining)
    budget_limited = cap < timeout
    stop = time.monotonic() + cap
    try:
        proc = subprocess.Popen([str(x) for x in argv], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
    except OSError as exc:
        return ProcessResult(-1, b'', str(exc).encode(), 'could not start subprocess')
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    limits = {'stdout': stdout_limit, 'stderr': stderr_limit}
    issue = None
    selector = selectors.DefaultSelector()
    try:
        for label, pipe in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, label)
        while selector.get_map():
            left = stop - time.monotonic()
            if left <= 0:
                issue = 'subprocess timed out'
                break
            for key, _ in selector.select(min(left, 0.05)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buf = buffers[key.data]
                available = limits[key.data] - len(buf)
                buf.extend(chunk[:max(0, available)])
                if len(chunk) > available and key.data == 'stdout':
                    issue = 'stdout exceeded byte limit'
                    break
                # stderr is diagnostic, with no size limit in the assignment.
                # Retain only its bounded prefix and keep draining the pipe so
                # a correct noisy optimizer can finish under the same deadline.
            if issue:
                break
        if not issue:
            try:
                proc.wait(timeout=max(0.001, stop - time.monotonic()))
            except subprocess.TimeoutExpired:
                issue = 'subprocess timed out'
    finally:
        # Kill the group even if its original process exited successfully.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        selector.close()
        proc.stdout.close()
        proc.stderr.close()
    if issue == 'subprocess timed out' and budget_limited:
        raise EvaluationError('overall evaluation deadline exhausted during subprocess')
    return ProcessResult(proc.returncode, bytes(buffers['stdout']),
                         bytes(buffers['stderr']), issue)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def parse_result(data):
    result = strict_json(data)
    if not isinstance(result, dict) or set(result) != {'ncols', 'rows', 'cycles'}:
        raise ValueError('expected ncols, rows, cycles object')
    if type(result['ncols']) is not int or result['ncols'] < 1:
        raise ValueError('invalid ncols')
    if type(result['cycles']) is not int or result['cycles'] < 0:
        raise ValueError('invalid cycles')
    if not isinstance(result['rows'], list):
        raise ValueError('rows must be an array')
    for row in result['rows']:
        if not isinstance(row, list) or len(row) != result['ncols']:
            raise ValueError('row width does not match ncols')
        if any(v is not None and type(v) not in (bool, int, str) for v in row):
            raise ValueError('invalid MiniVM cell encoding')
    return result


def numeric(value, kind):
    if type(value) not in (int, str):
        return None
    # INT and NUM outputs share the assignment's numeric comparison contract.
    # A candidate may change numeric type/scale while preserving its value.
    # A candidate may emit STR text in a numeric slot. Decimal accepts exponents,
    # whitespace and special values which MiniVM never prints for numbers. Bound
    # the spelling too: every VM numeric serialization is far below 128 bytes.
    if type(value) is str:
        pattern = r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?'
        if len(value) > 128 or re.fullmatch(pattern, value) is None:
            return None
    try:
        n = decimal.Decimal(value)
    except decimal.DecimalException:
        return None
    if not n.is_finite():
        return None
    return n


def cell_equal(a, b, kind):
    if a is None or b is None:
        return a is None and b is None
    if kind in ('INT', 'NUM'):
        x, y = numeric(a, kind), numeric(b, kind)
        if x is None or y is None:
            return False
        # Decimal's default 28-digit precision is insufficient for 128-bit INT.
        try:
            with decimal.localcontext() as ctx:
                ctx.prec = 100
                return abs(x - y) <= REL_TOL * max(abs(x), abs(y))
        except decimal.DecimalException:
            return False
    if kind == 'BOOL':
        return type(a) is bool and type(b) is bool and a == b
    if kind in ('STR', 'DATE'):
        return type(a) is str and type(b) is str and a == b
    raise EvaluationError('unknown fixture output type ' + kind)


def compare_results(expected, actual, kinds, ordered):
    """Return (equal, explanation); preserve multiplicity and row associations.

    Each fixture has homogeneous column kinds. Mixed-type fixtures use separate
    cases with known per-cell origins rather than guessing types from strings.
    """
    if expected['ncols'] != actual['ncols'] or expected['ncols'] != len(kinds):
        return False, 'output column count changed'
    left, right = expected['rows'], actual['rows']
    if len(left) != len(right):
        return False, 'output row count changed'
    def equal_row(a, b):
        return all(cell_equal(x, y, k) for x, y, k in zip(a, b, kinds))
    if ordered:
        return (True, '') if all(map(lambda ab: equal_row(*ab), zip(left, right))) else (False, 'ordered rows differ')
    # Fast path avoids quadratic graphs for exact identity and duplicate rows.
    if collections.Counter(tuple((type(v).__name__, v) for v in row) for row in left) == collections.Counter(tuple((type(v).__name__, v) for v in row) for row in right):
        return True, ''
    # Maximum matching, not greedy matching: tolerance is not transitive.
    edges = [[j for j, b in enumerate(right) if equal_row(a, b)] for a in left]
    matched_right = {}
    for start in range(len(left)):
        queue = collections.deque([start])
        seen_left = {start}
        previous = {}
        free = None
        while queue and free is None:
            i = queue.popleft()
            for j in edges[i]:
                if j in previous:
                    continue
                previous[j] = i
                if j not in matched_right:
                    free = j
                    break
                other = matched_right[j]
                if other not in seen_left:
                    seen_left.add(other)
                    queue.append(other)
        if free is None:
            return False, 'unordered rows differ (including duplicate multiplicity)'
        j = free
        while True:
            i = previous[j]
            old = next((r for r, l in matched_right.items() if l == i), None)
            matched_right[j] = i
            if old is None:
                break
            del matched_right[old]
            j = old
    return True, ''


@dataclasses.dataclass
class Case:
    name: str
    program: str
    kinds: tuple[str, ...]
    ordered: bool
    datasets: list[dict]


def table(columns, rows, **constraints):
    return dict(columns=[dict(name=n, type=t) for n, t in columns], rows=rows,
                **constraints)


def simple_data(seed):
    rng = random.Random(seed)
    rows = [[2, 'b', '1.00', '2024-02-29'],
            [1, 'a', '1.0', '2023-01-01'],
            [2, 'b', '1.00', '2024-02-29'],
            [None, None, None, None], [0, '', '0.0000001', '0001-01-01'],
            [-3, ' straße ', '-3.125', '9999-12-31']]
    rng.shuffle(rows)
    for _ in range(6):
        rows.append([rng.choice([-7, 0, 2, 9, None]),
                     rng.choice(['', ' ', 'a;b', "it\'s", '1.0', 'Zoë', None]),
                     rng.choice(['1', '1.00', '-0.5', '123456.789', None]),
                     rng.choice(['2023-07-01', '2024-01-01', None])])
    return {'t': table([('x', 'INT'), ('s', 'STR'), ('n', 'NUM'), ('d', 'DATE')], rows)}


def constrained_data(seed):
    rng = random.Random(seed)
    parent = table([('id', 'INT'), ('name', 'STR')], [[1, 'p'], [2, 'q']], key=['id'])
    rows = [[1, 1, '0.01'], [1, 2, None], [2, 1, '9999.99']]
    if seed == SEEDS[1]:
        rows = [[1, i, rng.choice(['0.01', '5.00', None])] for i in range(1, 8)]
    child = table([('pid', 'INT'), ('seq', 'INT'), ('price', 'NUM')], rows,
                  key=['pid', 'seq'], refs={'pid': 'p.id'},
                  check={'seq': [1, 50], 'price': ['0.01', '9999.99']},
                  sorted=['pid', 'seq'])
    return {'p': parent, 'c': child}


def make_cases():
    data = [simple_data(s) for s in SEEDS]
    data.append({'t': table([('x', 'INT'), ('s', 'STR'), ('n', 'NUM'), ('d', 'DATE')], [])})
    definitions = [
        ('bag_rows', 'LOAD x,t.x\nLOAD s,t.s\nOUT x,s', ('INT', 'STR'), False),
        ('ordered_rows', 'LOAD x,t.x\nLOAD s,t.s\nSORT i,x ASC NF,s DESC NL\nGATHER a,x,i\nGATHER b,s,i\nOUT a,b', ('INT', 'STR'), True),
        ('numeric_values', 'LOAD n,t.n\nADD a,n,0.00\nDIV b,a,3\nOUT n,a,b', ('NUM', 'NUM', 'NUM'), False),
        ('string_values', 'LOAD s,t.s\nRTRIM r,s\nUPPER u,r\nLEFT l,u,4\nOUT s,r,u,l', ('STR',)*4, False),
        ('null_logic', 'LOAD x,t.x\nEQ e,x,x\nIS z,x,x\nNOT ne,e\nNVL v,e,FALSE\nOUT e,z,ne,v', ('BOOL',)*4, False),
        ('filter', 'LOAD x,t.x\nLOAD s,t.s\nGT m,x,0\nIDX i,m\nGATHER a,x,i\nGATHER b,s,i\nOUT a,b', ('INT', 'STR'), False),
        ('reassignment', 'LOAD x,t.x\nADD y,x,1\nLOAD x,t.x\nSUB x,x,2\nADD y,y,x\nOUT y,x', ('INT', 'INT'), False),
        ('sort_slice', 'LOAD x,t.x\nLOAD s,t.s\nSORT i,x DESC NL,s ASC NF\nSLICE i,i,3\nGATHER a,x,i\nGATHER b,s,i\nOUT a,b', ('INT', 'STR'), True),
        ('topk', 'LOAD x,t.x\nTOPK i,3,x ASC NF\nGATHER a,x,i\nOUT a,i', ('INT', 'INT'), True),
        ('topk_zero', 'LOAD x,t.x\nTOPK i,0,x ASC NF\nOUT i', ('INT',), True),
        ('group', 'LOAD x,t.x\nLOAD n,t.n\nGROUP g,x\nGFIRST i,g\nGATHER k,x,i\nGCOUNT c,g\nGCOUNTV v,g,n\nGSUM s,g,n\nGMIN lo,g,n\nGMAX hi,g,n\nOUT k,c,v,s,lo,hi', ('INT','INT','INT','NUM','NUM','NUM'), False),
        ('gall', 'LOAD n,t.n\nGALL g,n\nGCOUNT c,g\nGSUM s,g,n\nOUT c,s', ('INT','NUM'), False),
        ('join', 'LOAD x,t.x\nHJOIN l,r,x,x\nOUT l,r', ('INT','INT'), True),
        ('join_null_equal', 'LOAD x,t.x\nNLJOIN l,r,x,x,NULLEQ\nOUT l,r', ('INT','INT'), True),
        ('join_same_dest', 'LOAD x,t.x\nNLJOIN i,i,x,x\nOUT i', ('INT',), True),
        ('dates', 'LOAD d,t.d\nYEAR y,d\nMONTH m,d\nDAY a,d\nDOW w,d\nOUT d,y,m,a,w', ('DATE','INT','INT','INT','INT'), False),
        ('wide_integer', 'LOAD x,t.x\nMUL a,x,10000000000000000000\nOUT a', ('INT',), False),
    ]
    cases = [Case(n, p+'\n', k, o, data) for n,p,k,o in definitions]
    constraints = [constrained_data(s) for s in SEEDS]
    constraints.append({n: dict(t, rows=[]) for n,t in constraints[0].items()})
    cases.append(Case('constraints', 'LOAD p,c.pid\nLOAD q,c.seq\nLOAD v,c.price\nSORT i,p ASC NF,q ASC NF\nGATHER a,p,i\nGATHER b,q,i\nGE m,b,1\nOUT a,b,m,v\n', ('INT','INT','BOOL','NUM'), True, constraints))
    example_kinds = [('INT','INT','INT','STR'), ('INT',)*3,
                     ('INT','STR','INT'), ('NUM','INT'), ('STR','NUM'),
                     ('INT','NUM','INT'), ('INT','NUM','STR'), ('STR','INT','INT')]
    example_data = json.loads((ROOT/'examples/data.json').read_text())
    empty = {n:dict(t, rows=[]) for n,t in example_data.items()}
    for i,kinds in enumerate(example_kinds, 1):
        name = f'q{i:04d}'
        cases.append(Case(name, (ROOT/'examples/programs'/f'{name}.mini').read_text(),
                          kinds, True, [example_data, empty]))
    return cases


def run_vm(program, data, deadline, vm_path):
    result = run_process([vm_path, program, data], 10.0, deadline)
    if result.issue or result.returncode:
        raise ValueError((result.issue or 'VM exited '+str(result.returncode)) + ': ' + result.stderr.decode('utf-8','replace')[:1000])
    return parse_result(result.stdout)


def save_failure(artifact_root, case, program, schema, data, result, message, expected=None, actual=None):
    stamp = f'{time.time_ns()}-{case.name}'
    folder = artifact_root / stamp
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'original.mini').write_text(case.program)
    (folder/'schema.json').write_text(json.dumps(schema, indent=2))
    (folder/'data.json').write_text(json.dumps(data, indent=2))
    if result:
        # Byte streams encoded as hex remain text even for invalid UTF-8 output.
        (folder/'optimizer-stdout.hex').write_text(result.stdout.hex())
        (folder/'optimizer-stderr.hex').write_text(result.stderr.hex())
        try:
            (folder/'optimized.mini').write_text(result.stdout.decode('utf-8'))
        except UnicodeDecodeError:
            pass
    (folder/'failure.json').write_text(json.dumps(dict(message=message, seeds=SEEDS,
        expected=expected, actual=actual), indent=2))
    return folder


def evaluate(optimizer, *, cases=None, budget=840.0, optimizer_timeout=60.0,
             vm_path=None, artifact_root=None):
    """Return a summary or raise Defect/EvaluationError; injectable bounds aid tests."""
    started = time.monotonic()
    deadline = started + budget
    vm_path = Path(vm_path or ROOT/'bin/minivm').resolve()
    optimizer = Path(optimizer).resolve()
    artifact_root = Path(artifact_root or ROOT/'.evaluation-failures')
    cases = make_cases() if cases is None else cases
    summary = dict(cases=0, executions=0, optimizer_seconds=0.0, vm_seconds=0.0)
    with tempfile.TemporaryDirectory(prefix='minivm-evaluate-') as temp:
        temp = Path(temp)
        for case_index, case in enumerate(cases):
            # The optimizer may rewrite, replace, remove or chmod its input.
            # Keep a fresh input per case and create the baseline separately
            # after the subprocess exits; no optimizer gets its oracle path.
            case_dir = temp/str(case_index)
            case_dir.mkdir()
            optimizer_input = case_dir/'optimizer-input.mini'
            program = case_dir/'original.mini'
            schema_file = case_dir/'schema.json'
            data_file = case_dir/'data.json'
            candidate = case_dir/'optimized.mini'
            optimizer_input.write_text(case.program)
            data_file.write_text(json.dumps(case.datasets[0]))
            schema_run = run_process([vm_path, '--schema', data_file], 10.0, deadline)
            if schema_run.issue or schema_run.returncode:
                raise EvaluationError('invalid fixture/schema '+case.name+': '+schema_run.stderr.decode('utf-8','replace'))
            try:
                schema = strict_json(schema_run.stdout)
            except (ValueError, UnicodeError) as exc:
                raise EvaluationError('malformed VM schema: '+str(exc)) from exc
            schema_file.write_text(json.dumps(schema))
            tick = time.monotonic()
            result = run_process([optimizer, optimizer_input, schema_file], optimizer_timeout, deadline)
            summary['optimizer_seconds'] += time.monotonic()-tick
            if result.issue or result.returncode:
                message = result.issue or 'optimizer exited '+str(result.returncode)
                path = save_failure(artifact_root, case, program, schema, case.datasets[0], result, message)
                raise Defect(message+'; witness '+str(path))
            try:
                source = result.stdout.decode('utf-8')
                if not source.strip():
                    raise ValueError('empty optimized program')
            except (UnicodeError, ValueError) as exc:
                path = save_failure(artifact_root, case, program, schema, case.datasets[0], result, str(exc))
                raise Defect('malformed optimizer output; witness '+str(path)) from exc
            candidate.write_text(source)
            program.write_text(case.program)
            for data in case.datasets:
                data_file.write_text(json.dumps(data))
                # --schema validates declared constraints on EVERY alternative.
                validation = run_process([vm_path, '--schema', data_file], 10.0, deadline)
                if validation.issue or validation.returncode:
                    raise EvaluationError('invalid alternative fixture '+case.name)
                try:
                    alternative_schema = strict_json(validation.stdout)
                    declarations = lambda obj: {n: {k:v for k,v in t.items() if k != 'stats'} for n,t in obj.items()}
                    if declarations(schema) != declarations(alternative_schema):
                        raise EvaluationError('alternative changes schema constraints '+case.name)
                except (ValueError, UnicodeError, AttributeError) as exc:
                    raise EvaluationError('malformed alternative schema '+case.name) from exc
                tick = time.monotonic()
                try:
                    expected = run_vm(program, data_file, deadline, vm_path)
                except (ValueError, UnicodeError) as exc:
                    raise EvaluationError('baseline failed '+case.name+': '+str(exc)) from exc
                actual = None
                try:
                    actual = run_vm(candidate, data_file, deadline, vm_path)
                    same, message = compare_results(expected, actual, case.kinds, case.ordered)
                except (ValueError, UnicodeError) as exc:
                    same, message = False, 'optimized VM failed: '+str(exc)
                summary['vm_seconds'] += time.monotonic()-tick
                if not same:
                    path = save_failure(artifact_root, case, program, schema, data, result,
                                        message, expected, actual)
                    raise Defect(case.name+': '+message+'; witness '+str(path))
                summary['executions'] += 1
            summary['cases'] += 1
    if time.monotonic() >= deadline:
        raise EvaluationError('overall evaluation deadline exhausted')
    summary['wall_seconds'] = time.monotonic()-started
    return summary


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: ./evaluate OPTIMIZER', file=sys.stderr)
        return 2
    try:
        print(json.dumps(dict(status='no defects found', **evaluate(argv[0]))))
        return 0
    except Defect as exc:
        print('optimizer defect: '+str(exc), file=sys.stderr)
        return 1
    except (EvaluationError, OSError) as exc:
        print('evaluation incomplete: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
