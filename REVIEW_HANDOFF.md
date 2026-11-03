# Fresh reviewer handoff

**New optimizations remain frozen. Review current HEAD**, including the two
correctness fixes from the [fresh review](records/post-review/supplied-REVIEW.md).
The original optimization freeze was `49c7048`; `fc300d2` prepared documentation.
Later fixes preserve the evaluator's pristine oracle and the VM program-size limit.
See [post-review results](records/post-review/RESULTS.md) for validation and commits.

Submission overview: [WRITEUP.md](WRITEUP.md). Remaining items:
[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).

## Contract and implementation map

- Specification: [requirements transcript](docs/assignment.md), original supplied
  assignment.pdf, and [MiniVM docs](docs/README.md). The PDF and interpreter are
  deliberately outside the text-only submission.
- Required interfaces: `./optimize PROGRAM SCHEMA` prints a program in <=60s;
  `./evaluate OPTIMIZER` exits 0 if no defects found, nonzero otherwise, in <=900s.
  Results must agree for any data satisfying declarations/constraints; stats are
  estimates only. Numeric tolerance is 1e-6 relative; ordering matters when specified.
- [optimizer.py](optimizer.py): CLI/parser, frozen simple NLJOIN/HJOIN selection,
  and a final UTF-8 byte-size guard with original-source fallback.
- [sorted_order.py](sorted_order.py): current direct LOAD keys, one table, exact
  leading guaranteed sorted prefix, ASC NF only; preserves the destination write.
- [dead_code.py](dead_code.py): backward liveness, guaranteed type facts, narrow
  totality whitelist, **first textual definitions only**. Unsafe instructions stay.
- [evaluator.py](evaluator.py): independent VM oracle, typed fixture metadata,
  full-row multiplicity/order comparison, Decimal tolerance and maximum matching,
  frozen schemas with varied valid data, subprocess bounds and global deadline.
  A separate pristine program is used for the baseline, never the input given to
  the optimizer (which may edit that input in place).
- [experiments/](experiments/README.md): exact archived profile model, not active.
  Proofs: [joins](docs/optimizer.md), [sort rule](docs/sorted-order.md), [DCE](docs/dce.md).

## Setup and commands

Follow [SETUP.md](SETUP.md): Python 3.9+, POSIX, original matching MiniVM in local
ignored `bin/`; no pip dependencies. Use a full-history checkout.

```sh
./evaluate ./optimize
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
review_dir="$(mktemp -d)"
python3 tools/verify_baseline.py --output "$review_dir/cli-checks.json"
python3 tools/benchmark_sorted.py --output "$review_dir/benchmark.json"
python3 tools/benchmark.py ./optimize --output "$review_dir/examples.json"
```

At the original freeze: 150 tests (75+75), public 26 cases / 70 datasets, identity
accepted and five baseline mutants rejected. Post-review counts are in the
linked results: **162 tests (79+83) pass**, and public 26/70 still passes. Flags `--joins-only` and
`--no-sorted-order` isolate stages; required two-argument behavior remains primary.

## Measurements and tradeoffs

- Eight examples: 60363 original -> 59121 current cycles (-1242, 2.06%). Measured
  incremental contributions: 196 join selection, 276 DCE, 770 SORT->IOTA. Current
  per-program cycles are 12766,3527,8562,18442,5518,6338,2444,1524.
- Last rule: q0001 improves; seven examples unchanged. All 39 diagnostic cases
  preserve exact outputs; 6 improve / 33 unchanged versus prior pipeline. This does
  **not** mean the join cost policy never regresses relative to original programs.
- Active join losses remain: stale row estimates 28 -> 48 and 1040 -> 4368; matching-stat
  string skew chooses HJOIN 28852 when NLJOIN 22180. These are performance losses, not output
  mismatches. All holdouts stay in regression benchmarks.
- Archived profile saves 6672 on fixed 19 but loses 7296 on one stale-profile holdout:
  combined 20 is 122065 simple vs 122689 refined (+624). All 29 instead favor profile:
  341953 vs 328560 (-13393). Neither diagnostic weighting is representative. Simpler
  policy was frozen on scope/complexity grounds, not a general performance claim.
- Results/raw JSON: [final rule](records/sorted-order/RESULTS.md),
  [DCE](records/dce/RESULTS.md), [join tradeoff](records/join-costs/RESULTS.md).
  Wall times include startup and are noisy; current recorded evaluator ~4.4s,
  optimizer ~89-91ms/example, scale probe ~0.45s. See receipts for exact runs.

## Highest-value review targets and encountered failures

Fresh review found two further confirmed bugs: ordinary in-place optimizer input
mutation contaminated the evaluator oracle, and HJOIN-to-NLJOIN expansion made an
exact-limit program exceed 4 MiB. Fixes and generated regressions are retained;
large padding is generated locally instead of stored as a fixture.


1. Error preservation: dead DIV0/type/overflow/index/date errors must stay.
   SORT+SLICE->TOPK can suppress errors and was deferred. NULL-first type checking,
   empty columns and cross-table length errors rule out ordinary algebraic DCE.
2. Memory lifetime: deleting dead overwrites after large joins caused original
   success/candidate failure at 64M values. First-definition-only DCE now preserves
   every overwrite, even after an earlier definition is deleted. Replay:
   `python3 tools/reproduce_dce_lifetime.py`; optional `--include-unsafe` uses ~1 GiB.
3. Parsing: broad splitlines corrupted string literals; LF-only splitting fixed it.
   Python-only FS..US whitespace, long-s ASC and Kelvin identifiers suppressed
   source errors. Shared scanner now refuses those tokens outside quotes/comments.
   Valid quoted data/comments remain intact. Before/after fixtures are retained.
4. Reaching definitions: invalidate every write, including both join outputs and
   destination/input aliases. Sorted suffixes/derived keys/statistical order are
   not proofs. DCE after SORT->IOTA must retain overwrite lifetime boundaries.
5. Evaluator: preserve duplicates and whole-row associations; avoid greedy fuzzy
   matching, BOOL==INT, numeric-looking STR coercion and stale-schema mistakes.
   Prior Decimal crashes, INT/NUM false rejection, overstrict ordering and noisy
   stderr rejection were fixed with retained regressions.

## Limits and provenance

Finite tests do not prove soundness. Assignment ordering intent, relative-error
denominator and error/resource-limit equivalence are underspecified; adopted
policies are in [CONTRACT.md](records/CONTRACT.md). VM output lacks complete type
tags; fixtures have homogeneous output types. General mixed-type output inference,
arbitrary-schema generation, Windows execution and resource-boundary proofs remain
limited. Review timeout classification too (optimizer 60s, VM 10s, overall 840s).

Prompts/decisions: [PROMPTS](records/PROMPTS.md), [SESSION](records/SESSION.md),
specialist reports under tests/, and [final returned review log](records/sorted-order/REVIEW_LOG.md).
Logs are curated, not a complete provider conversation export. A separate
GPT-6.1 Sol / High brainstorming thread helped discuss next steps and draft prompts;
it is not included in submitted logs. User-reported development/review models and
ChatGPT Plus usage allowances are recorded in AI_USAGE.md. Specialists
temporarily hit limits then resumed final checks; evaluator reran reviewer fixtures
rather than authoring a separate SORT fixture set. See [AI_USAGE.md](AI_USAGE.md).

Git starts at untouched text starter `b8e7f8a`; original files are checksummed.
Binaries are excluded. Baseline publication was user-confirmed; latest remote
state is unverified because GitHub DNS fails here. [Submission checklist](SUBMISSION_CHECKLIST.md)
separates verified artifacts from publication and log-coverage gaps.
