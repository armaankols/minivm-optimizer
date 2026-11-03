# Retained task prompts

These are the task requests and specialist assignments available in the session.
This does not include hidden model reasoning, unavailable provider telemetry, or
an automatic export of the application conversation.

## User: final optimization recommendation and approval

```text
Let’s try one more optimization before the final review, which would you recommend next given the findings so far?
```

Coordinator recommended direct guaranteed SORT->IOTA and reported a read-only
temporary q0001 trial saving770 cycles with identical results. Reviewer confirmed
the nonempty leading-prefix, direct-LOAD, same-table, ASC NF preconditions.

```text
Sounds good
```

The user subsequently sent `continue` twice when specialist sessions reported
usage limits. Work continued within the approved one-rule scope. Both specialists
were later able to resume for narrow final independent checks.

Assignments: reviewer owns tests/adversarial sorted-rule fixtures/review, checking
proofs, alias invalidation, source bytes, malformed syntax and DCE lifetime
interaction. Evaluator owns its existing paths and was asked for independent
public-CLI verification. Coordinator owns implementation, shared parsing fixes,
benchmarks, records and Git. No nested delegation, join tuning or additional
GATHER rewrite. When usage limited the initial sessions, coordinator ran retained
tests locally; resumed reviewer inspected the exact fix and reran16tests, and
resumed evaluator independently reran those fixtures and public26/70 CLI. No new
evaluator-owned SORT fixtures were written; that distinction is preserved.

## User: balanced join freeze and next conservative rewrite

```text
The explanation makes sense. One thing I noticed: the holdout regression loses more cycles than the refinement saves across the fixed set. Please include that combined comparison in the results so the tradeoff is clear.

Before we freeze join selection, recommend whether the refined model earns its added complexity over the previous rule. Base that on the available evidence and its limitations, rather than tuning further to these particular cases.

Then let’s move to the next conservative rewrite from the plan. Have the reviewer check its preconditions independently, measure its contribution separately, and commit the verified change. Keep the join holdouts in the regression benchmarks.
```

The user later asked `what is the statys`; coordinator gave a brief progress
update and continued the already authorized milestone.

Assignments: both existing specialists independently recompute the20-case and
all29-case tradeoffs and assess complexity rather than further tune joins.
Reviewer derives DCE preconditions before implementation and owns only
`tests/adversarial/**`. Evaluator owns its existing paths and independent
command-interface DCE tests. Coordinator owns active/archived optimizer code,
stage-isolated benchmarks, records and Git. No nested delegation. Initial DCE
whitelist is limited to guaranteed LOAD, proven-column IOTA/SLICE/ISNULL, typed
unary STR/date operations, and validated LEFT/SUBSTR counts. FILL/GATHER/arithmetic/
TRUNC/SORT/joins/groups remain. After a coordinator-confirmed memory-lifetime
failure, specialists independently review a first-textual-definition-only guard
and retain all semantic negatives; they do not duplicate the heavy memory probe.

## User: cost-rule comparison and refinement

```text
Before adding another rewrite, let’s take a closer look at the join selection. Can you compare the current rule against always choosing HJOIN and always choosing NLJOIN on the same workloads?

I’m particularly interested in why the skewed-string case gets worse even with matching statistics. Have the reviewer investigate that independently, then use the findings to improve the rule if there’s a defensible change.
```

Specialist assignments: reviewer independently derives skew cost and investigates
common/null/average statistics before seeing a coordinator proposal, then reviews
profile validation, rounding, derived-column invalidation and limitations. Own
only `tests/adversarial/**`. Evaluator independently compares the identical
19-case corpus under external forced policies, derives cycle formulas from VM
execution/docs, and adds separate profile holdouts. Own only existing evaluator
paths. Coordinator owns optimizer, comparison tooling, records and Git. No nested
delegation or additional semantic rewrite.

## User: join milestone approval and push update

```text
I was able to push the commits myself, so please update the records to reflect that. If pushing still fails in your environment, keep committing locally and I’ll handle the pushes.

Go ahead with join algorithm selection. Keep this change focused on choosing between NLJOIN and HJOIN while preserving all operands and flags. Have the reviewer check the equivalence assumptions and edge cases independently.

Run the existing checks and compare cycles before and after, including small joins where switching might be worse. Commit the verified change, then show me the results before adding another rewrite.
```

## Join milestone specialist assignments

- Reviewer: independently reread join/cycle/error documentation and challenge
  opcode equivalence, operand/flag preservation, NULL/NULLEQ, duplicate/order,
  exact mixed numeric comparison, errors, aliases/reassignment, lexical cases,
  unknown/stale estimates and small/large cost choices. Own only
  `tests/adversarial/**`; no optimizer/evaluator/shared/Git edits or delegation.
  Return confirmed failures before fixes and retain reproductions and a
  `JOIN_REVIEW.md` command/results log.
- Evaluator: own existing evaluator paths; use public optimizer CLI and MiniVM
  oracles to test join changes independently, retaining baseline identity and
  defective optimizer checks. Cover frozen/stale stats, aliases, flags, duplicate
  pairs, errors and small/large numeric/string workloads. Prefer standalone
  `test_join_optimizer.py` and `JOIN_REPORT.md` to preserve baseline corpus.
  No optimizer imports, shared/Git edits or delegation. Coordinator owns
  benchmark/integration helpers and adapts the explicit identity demonstration.

## User: initial assignment

```text
Help me complete this MiniVM take-home assignment using a small team: you as coordinator and optimizer implementer, plus two specialist subagents.

Read assignment.pdf and docs/README.md, then inspect the relevant interpreter documentation, starter scripts, examples, and repository instructions.

For this first turn, inspect and plan; do not implement yet. Subagents may perform read-only investigation. The implementation instructions below apply after I approve the plan.

Establish the contract

Report:
- The exact optimize and evaluate interfaces, correctness requirements, and runtime limits.
- Which schema fields are guaranteed constraints and which are statistical estimates.
- MiniVM semantics that affect safe rewrites, with references to documentation or interpreter source.
- A small implementation plan ranked by likely instruction-cycle savings, correctness risk, and effort.
- Shared acceptance criteria, file ownership, and any interfaces needed between components.
- A testing strategy covering both the optimizer and evaluator.
- Unresolved ambiguities that materially affect correctness.

Prefer a few defensible optimizations over broad, speculative coverage. Do not assume ordinary SQL or arithmetic identities apply without checking MiniVM behavior.

Agent responsibilities

1. Evaluator agent:
Independently read the specification and MiniVM documentation. During planning, derive the comparison contract and evaluator design. After implementation is authorized, own evaluator code and its assigned test fixtures.

Test arbitrary optimizers through the required command interface, including an identity optimizer and deliberately incorrect implementations with known witnesses. Derive expected behavior from the specification and MiniVM execution rather than optimizer internals.

Cover result comparison, valid test-data generation, subprocess failures, malformed output, timeouts, and the overall evaluation deadline. Preserve duplicate multiplicity, required ordering, output structure, and associations between values where applicable.

2. Adversarial reviewer:
Independently read the VM semantics and examine proposed rewrite rules. Start with read-only review. Search for small executable counterexamples involving NULLs where supported, register reassignment, duplicates, ordering, numeric precision, runtime errors, and interactions between passes.

Identify the exact preconditions each rewrite needs and whether the implementation enforces them. Return confirmed failures separately from suspected risks and coverage gaps. Once implementation is authorized, write reproductions only in an assigned test directory.

3. You, the coordinator:
Own optimizer implementation, integration, shared interfaces, Git operations, and final reporting. Assign shared helpers a single owner before parallel implementation. Keep edits separate and avoid nested delegation.

After implementation is authorized, continue useful work while specialists investigate independent tasks. Wait for their findings before declaring the relevant milestone complete. Resolve disagreements through specification references or reproducible execution results.

Implementation and verification

Start with a working baseline and demonstrate that the evaluator accepts an identity optimizer and rejects known defective optimizers.

Add optimizations incrementally. For each rewrite, record its preconditions, a concise correctness argument, and positive and boundary tests. Use guaranteed constraints to justify correctness; use statistical estimates only to choose among already valid transformations. Leave a rewrite unapplied when its preconditions cannot be established.

Measure MiniVM instruction cycles before and after on a fixed representative benchmark set. Report unchanged cases and regressions as well as improvements. Measure optimizer and evaluator wall-clock runtime separately.

Save reproducible seeds and failure fixtures. Reproduce review findings before fixing them, retain regression tests, and rerun relevant checks. Passing tests provides evidence; it does not prove soundness.

Git and repository

The destination repository is:
https://github.com/armaankols/minivm-optimizer.git

Once implementation begins, commit and push meaningful, verified milestones to this repository as work progresses. This explicitly authorizes routine commits and pushes without asking again at each milestone.

Verify the repository and remote before the first push. Preserve existing history and unrelated changes. Do not force-push or silently replace an existing remote destination.

You alone coordinate commits so unfinished subagent work is not accidentally included. Use clear commit messages describing the concrete change. Commit fixes separately when that makes the development history easier to understand.

Keep all binary files out of commits and the submission, including bin/minivm. Preserve supplied binaries locally when needed for testing.

If authentication or permissions prevent a push, report the issue accurately and continue making local progress and commits.

Development records and delivery

Preserve prompts, agent assignments, important decisions, commands, results, failures, confirmed findings, fixes, and benchmark results in concise development records. Preserve available subagent logs.

Record the model and reasoning settings I provide. Use actual usage information when available; clearly label estimates and unknowns. Never invent token counts, spend, test results, or execution history.

Keep coordination proportional to the assignment’s estimated 2–3 hour scope. Maintain a short list of remaining risks and deferred work.

The final write-up should explain the implemented optimizations, evaluator design, measured results, limitations, AI usage, and what we would do with a few days and unlimited compute and tokens.

For this first response, finish with your recommended scope, agent ownership boundaries, acceptance criteria, and first implementation milestone. Then wait for my approval to implement.
```

## User: first milestone approval

```text
Sounds good go ahead with the first milestone.

First, check that Git is set up correctly and connected to [https://github.com/armaankols/minivm-optimizer.git](https://github.com/armaankols/minivm-optimizer.git). Capture the starter code before changing it, then commit and push meaningful milestones as you go. Keep binaries out of the repo.

For the baseline, make sure the evaluator both accepts the identity optimizer and catches deliberately incorrect ones. Have the reviewer challenge the assumptions independently.

Once that’s working, show me the results and your recommendation for the first optimization before adding rewrites.
```

## Evaluator: initial read-only assignment

```text
Read-only planning investigation. Independently read /Users/armaankolsawala/Downloads/Assessment/assignment.pdf (Python PDF library if needed; pdftotext unavailable), aim-takehome/docs/README.md and all relevant MiniVM docs, starter scripts/examples and repository instructions. Derive exact evaluate/optimize command interface and comparison contract, evaluator architecture, valid data generation respecting guaranteed constraints vs estimates, process failures/malformed output/timeouts/overall deadline, tests identity and deliberately incorrect optimizers with witnesses. No implementation, no repository writes, no nested delegation. Temporary extraction/execution in /tmp permissible. Return concise findings with exact file/line references, ambiguities. Assigned future ownership: evaluator code and own tests only; propose paths.
```

## Reviewer: initial read-only assignment

```text
Read-only adversarial planning review. Independently read assignment.pdf and aim-takehome MiniVM docs, starter scripts/examples and repository instructions. Derive candidate high-value safe rewrite rules with exact preconditions, focus on NULL, register reassignment, duplicates/order, numeric precision/errors, pass interactions. Use supplied interpreter and /tmp executable counterexamples if useful, without editing repository. Confirmed failures separate from suspected risks/gaps. No implementation and no nested delegation. Future ownership: tests/adversarial/ only after approval. Return precise docs/line references and recommendations to coordinator.
```

## Evaluator: implementation assignment

```text
First baseline implementation authorized, NO optimizer rewrites. Starter captured commit b8e7f8a in aim-takehome repo. Implement now within sole ownership evaluate, evaluator.py, tests/evaluator/**. Python standard library preferred. Build independent finite suite, typed ordered/unordered comparator complete rows multiplicity/tolerance, fixed frozen schema multiple constraint-valid datasets incl seeded families and all8 examples. Process failures/malformed output/timeouts/bounded streams/global monotonic deadline cleanup; retain failures text artifacts ignored by git. Actual CLI tests identity and deliberate mutant executables with known witnesses. Include short injected deadlines via Python harness (public CLI unchanged). Conservative policies from your plan; document in code/tests. No optimizer imports; no shared helper edits; no Git operations/no nested delegation. Coordinator owns docs, benchmark, integration, tests root. Reviewer owns tests/adversarial only. Please create tests/evaluator/test_evaluator.py with stdlib unittest runnable via discover -s tests/evaluator, avoid shared test __init__ edits. Provide ready signal early for reviewer; report concrete checks and files. Timebox first milestone scope, correctness first. Default public overall limit ~840s plus reserve under900s, per optimizer60s cap. Avoid regenerating optimizer schema per alternative data. Record all work commands/results in your final report to coordinator.
```

## Reviewer: implementation assignment

```text
First baseline implementation authorized only. Independently challenge evaluator assumptions and test contract; evaluator agent implementing evaluate/evaluator.py/tests/evaluator. You own only tests/adversarial/**, may add repro fixtures and standalone stdlib tests runnable `python3 -m unittest discover -s tests/adversarial -v`. Retain prior /tmp witnesses (DCE TOPK CSE sorted suffix nullable check) here as relevant; no optimizer rewrites yet. Challenge comparator row multiplicity/association/ordering numeric encodings, tolerance greedy matches bool vs int, frozen schema stats, generated validity, process/deadline failures and no false clean pass. Inspect implementation when agent sends ready or files exist. Report confirmed failures separately from risks/gaps; coordinate concrete findings directly with evaluator and coordinator, but do not edit evaluator-owned files. No Git or shared helpers or nested delegation. Starter commit b8e7f8a captured. Independent review completion needed before milestone done. Provide final logs/commands findings in concise report.
```

## User: submission preparation (verbatim)

```text
Let’s prioritize getting this ready to submit. Freeze new optimizations for now.

Prepare a concise handoff for a fresh reviewer, pointing to the specification, current commit, implementation, test commands, benchmarks, and known limitations. Include the join regressions and the error-preservation and memory-lifetime issues we’ve encountered.

Then check what’s still missing from the submission: setup instructions, reproducible results, AI-use write-up, prompts and logs, and Git history. Flag anything that needs information from me rather than filling it in.
```

Asked for exact model/reasoning settings and approximate usage/spend, the user
answered `i say later`. These fields remain pending, without invented estimates.

## User: prioritize handoff (verbatim)

```text
Why are you doing a clean code check? Also prioritize outputting the handoff
```

The coordinator explained the fresh-checkout packaging/setup purpose and linked
the handoff immediately. No optimization or runtime changes were made.

## User: fresh-review fixes (verbatim)

```text
The reviewer saved the findings and reproductions in review-49c7048/REVIEW.md. Read that before making the fixes.
```

Read the report before any edit. Resumed the original evaluator specialist for
the input-mutation oracle fix (evaluator.py and tests/evaluator only). Resumed
the original reviewer for independent reproduction and tests/adversarial only.
Coordinator owns optimizer final UTF-8 size guard, records, docs, integration and
Git. No new optimizations, shared helper edits or nested delegation authorized.
Both specialists were instructed to reproduce before fixing and retain reports.
