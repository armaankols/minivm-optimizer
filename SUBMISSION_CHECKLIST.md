# Submission checklist

New optimizations are frozen at implementation commit `49c7048`.
Start with [REVIEW_HANDOFF.md](REVIEW_HANDOFF.md) and [WRITEUP.md](WRITEUP.md).

| Item | Status and evidence |
|---|---|
| Specification and interfaces | [Requirements transcript](docs/assignment.md), original MiniVM docs and [contract](records/CONTRACT.md). Original PDF remains outside Git. |
| Setup | [SETUP.md](SETUP.md): Python standard library, POSIX and the original local interpreter bundle. No binaries submitted. |
| Fresh-checkout verification | Full-history local clone at `49c7048`: 75 evaluator + 75 adversarial tests passed; public evaluator passed 26 cases / 70 executions. Clean Git status before and after. [Receipt](records/submission-audit/clean-checkout.json). Same macOS host; network installation and other platforms unverified. |
| Identity and incorrect optimizers | Baseline receipts and witnesses retained; replay with `tools/verify_baseline.py`. Identity accepted, five deliberate defective optimizers rejected. |
| Reproducible results | Fixed workloads, holdouts, seeds, raw JSON, failure fixtures and commands retained. [Current results](records/sorted-order/RESULTS.md), [join tradeoffs](records/join-costs/RESULTS.md). Reproduction commands corrected from `python 3` to `python3`; use temporary result paths in SETUP. |
| Narrative and limitations | [WRITEUP.md](WRITEUP.md), handoff and per-rule proofs cover implementation, evaluator, measurements, join regressions, error preservation and memory lifetime. |
| AI use | [AI_USAGE.md](AI_USAGE.md) describes roles and future work. Exact model/reasoning settings and rough usage/spend remain **pending user information**, as requested by the user. |
| Prompts and logs | Curated prompts, assignments, decisions, commands, results and available specialist reports retained. A complete provider conversation/tool export is not available in the repository. User can supply it if available; do not describe these curated records as exhaustive. |
| Git history and binaries | At frozen commit: 10 commits, 34 starter hashes verified, 195 historical blobs checked as UTF-8 without NUL, no binary blobs or tracked bin files. [Audit](records/submission-audit/git-audit.json). Preparation adds text documentation and receipts only. |
| Publication | Requested origin configured. User confirmed earlier pushes. Latest remote state cannot be checked here because GitHub DNS fails. User handles pushes and should confirm the final branch/commit is accessible. No history rewriting. |

## Information still needed from the user

- Exact models/reasoning settings and approximate token usage or spend, or an
  explicit statement that telemetry is unavailable. User said they will provide it later.
- A complete conversation export if available, to supplement the curated prompts/logs.
- Confirmation that the final commits have been pushed and the submission reviewer
  can access the intended branch. Any portal-specific packaging instructions have
  not been supplied.

These items must not be filled with guesses. Finite test coverage, ambiguous error
and resource equivalence, VM output typing and cross-platform validation remain
technical limitations, not fields the user is expected to resolve.
