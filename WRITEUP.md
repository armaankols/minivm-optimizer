# MiniVM submission overview

Implementation is frozen at `49c7048`. [Reviewer handoff](REVIEW_HANDOFF.md) maps
the source, specification, proofs, checks and known failures. [Setup](SETUP.md)
provides reproducible commands; [checklist](SUBMISSION_CHECKLIST.md) identifies
the outstanding publication and AI-usage details.

## Optimizer

The optimizer first chooses NLJOIN or HJOIN using a simple statistical cost
estimate, preserving all operands and flags. Their documented semantic equivalence
justifies this choice; estimates only predict cost. It then replaces qualifying
SORT operations with IOTA using guaranteed stored order, current direct LOAD keys,
an exact leading sorted prefix and ASC NF ordering. Finally it removes dead first
definitions from a narrow whitelist of proven-total instructions.

The rules preserve register writes where memory lifetime requires them. Dead
arithmetic, unchecked indices and potentially failing operations remain. Ordinary
SQL or algebraic identities are not assumed. See [join proof](docs/optimizer.md),
[stored-order proof](docs/sorted-order.md) and [DCE proof](docs/dce.md).

## Evaluator

An independently implemented evaluator invokes arbitrary optimizer commands and
compares original/candidate MiniVM executions on fixed and seeded constraint-valid
data under frozen schemas. It preserves duplicate multiplicity and whole-row
associations, observes required ordering, and uses typed fixture metadata and
Decimal numeric tolerance. Unordered approximate rows use maximum matching.

Subprocess failures, malformed output, bounded output capture, process-group
cleanup, optimizer timeouts and the overall deadline are covered. The public suite
has 26 cases / 70 dataset executions. Identity and five deliberate mutants establish
a working baseline; 150 tests cover evaluator behavior and adversarial rewrites.
Finite testing does not establish soundness for arbitrary optimizers.

## Results and limitations

Eight supplied examples decrease from 60,363 to 59,121 instruction cycles (2.06%).
Measured incremental savings are 196 from joins, 276 from DCE and 770 from stored
order. The final rule improves six of 39 diagnostic cases and leaves 33 unchanged
relative to the preceding pipeline. Raw per-case results and wall times are in
[final results](records/sorted-order/RESULTS.md); timings include subprocess startup.

Join selection can regress: matching-stat string skew takes 28,852 cycles with
chosen HJOIN versus 22,180 with NLJOIN. Stale statistics also cause losses. An
archived refinement saves 6,672 cycles on the fixed set but loses 7,296 on one
holdout: combined totals are 122,065 simple versus 122,689 refined. Across all 29
diagnostics the refinement instead wins by 13,393. These unweighted collections
do not establish expected real-world performance; the simpler policy was retained
for scope and complexity. Holdouts remain in regression benchmarks.

Retained counterexamples include suppressed runtime errors, literal/token parsing
differences and a memory-lifetime failure where deleting dead overwrites kept large
join columns live until the VM limit. DCE now retains overwrites. Resource-boundary
equivalence is not proved. Ordering intent and relative tolerance need interpretation;
VM JSON lacks full type tags, and general mixed-type output inference is limited.
The evaluator's per-VM 10-second cap is a harness policy worth reviewing.

## Development and AI use

One coordinator owned optimizer/integration/Git, one specialist owned evaluator
code/tests, and one independently reviewed semantics and adversarial fixtures.
Starter text and meaningful verified milestones are retained in Git; binaries
remain local. Prompts, decisions, failures, fixes and available specialist reports
are retained, but this is not a complete provider conversation export.

[AI_USAGE.md](AI_USAGE.md) records the known configuration and the user-dependent
model/reasoning/usage fields still pending. With a few days and unlimited compute
and tokens, priorities would be independent schema/program fuzzing with shrinking,
stronger evaluator mutation testing, exhaustive small-state checks, explicit
resource/lifetime analysis and broader holdouts before expanding cost models or
adding rewrites.
