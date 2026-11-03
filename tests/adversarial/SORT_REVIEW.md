# Independent guaranteed-order review

Scope: exactly one new rule, direct stored-order SORT -> IOTA. No identity GATHER
or additional sort/constraint rewrite. Reviewer owns `tests/adversarial/**` only;
no optimizer/shared-helper/Git edits or nested delegation.

## Preconditions and argument sent before implementation

Every key's current register definition must be an unchanged direct LOAD from one
guaranteed table. The nonempty key column sequence must exactly match a leading
prefix of that table's declared `sorted`; every key must say ASC NF. Table/column
identifiers compare case-insensitively, register names case-sensitively. Statistics
do not establish order. Suffixes, extra keys, DESC, NL, mixed tables, derived keys,
and overwritten origins are left unchanged, even where a broader proof might work.

`docs/running.md:121` guarantees stored ASC NF lexicographic order, and
`docs/instructions/sorting.md:18,38-42` specifies stable ordering. A leading prefix
therefore already has identity order, including NULLs and numeric equalities with
different scales. `docs/instructions/columns.md:43` gives IOTA positions 0..N-1.
The replacement writes the same INT column of the same length at the same point.

The destination may alias a key: origins and the first source must be read before
invalidating writes. Every write clears old origin facts, including both outputs
of a join and the new IOTA destination. A later SORT must not reuse that old LOAD
origin. Subsequent DCE may remove dead first definitions, but must preserve its
overwrite guard, including now-unused secondary-key LOAD overwrites that release
old values. The rule preserves the destination write; no original-success memory
failure is excused by the prior resource-error caveat.

## Candidate code review and initial evidence

Independently read `sorted_order.py` and CLI integration. The implementation uses
validated declared columns/order names, nonempty unique order lists, the existing
known-opcode defs table, current direct-LOAD origins, exact prefix equality and
ASC NF checks. Unknown syntax/opcodes cause whole-pass fallback. All writes clear
origins after operand reads. The pipeline is joins -> sorted order -> DCE;
`--no-sorted-order` isolates the prior joins+DCE baseline, while `--joins-only`
continues isolating the frozen simple join policy.

Added `test_sorted_order.py`. First candidate run: fourteen methods passed in
5.117 seconds. Coverage includes full/short nullable prefixes, ties, empty and
frozen-empty snapshots, NUM scale preservation, UTF-8 strings, aliases, overwrite
lifetimes, register case sensitivity, mixed tables, suffix/extra/mode rejection,
unmodeled writes, malformed proofs, undefined/group keys, unknown syntax,
statistics-only order, CRLF/comments/no final newline, and live control characters
inside quoted strings. No baseline pre-implementation run is claimed.

## Confirmed parse-error suppression before fix

An additional independent boundary probe found that Python's whitespace differs
from the VM: U+001C FS, U+001D GS, U+001E RS and U+001F US are whitespace for
Python `.split()`/`.strip()`, but not valid MiniVM sort-key separators. With a
guaranteed ascending column, source

```
LOAD a,t.a
SORT i,a<FS>ASC NF
OUT i
```

exits 1 with `expected a sort key`; the candidate replaces SORT with valid IOTA
and exits 0. All four characters were reproduced before a fix. A retained run
of fifteen methods in 5.198 seconds failed the four new separator subtests; the
other fourteen methods passed. This is a confirmed error-preservation failure,
not a cost-model miss.

Separate pre-fix probes confirmed the same issue with a trailing control after NF,
and a preexisting DCE issue: `LOAD dead,t.a<FS>` is invalid in the VM, but operand
`.strip()` hides the control and DCE removes the erroring LOAD. All four controls
were confirmed for both forms. Regressions now retain internal/trailing SORT
controls and malformed dead LOADs. Coordinator was notified before edits, with
the bounded recommendation to reject these four characters outside quoted strings
and comments. They remain valid string/comment data; broad rejection must not
discard the existing literal-control coverage.

Commands:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -p test_sorted_order.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
```

Fix inspection, reruns, remaining limitations, and coordinator reproduction
provenance will be appended after ready signal. No unexecuted outcome is claimed.
