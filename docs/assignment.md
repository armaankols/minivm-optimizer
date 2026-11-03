# Assignment requirements transcript

Source: the supplied single-page `assignment.pdf`. Its SHA-256 is
`00f086154b7de990a61d3cd243710964ecee5be418eec12812d07eae919bf877`.
The original remains outside this repository (at `../assignment.pdf` in the task
workspace); it is excluded from Git under the user's no-binary requirement.
Use the original supplied PDF to resolve any transcription disagreement.

MiniVM is a simplified column virtual machine. Legacy programs waste cycles;
the task is an optimizer that uses fewer instruction cycles without changing
results, and an evaluator that tests optimizer soundness. Estimated scope: 2–3 hours.

## Deliverables

1. All code, scripts, prompts, docs and logs behind the optimizer and evaluator,
   plus Git history, committing as work progresses. Do not send any binary files,
   including `bin/minivm`.
2. Which AI models were used, roughly how many tokens or how much spend, and what
   would be done with a few days and unlimited compute/tokens. AI use is necessary.

## Optimize requirements (transcribed)

- `./optimize program.mini schema.json` prints an optimized program.
  schema.json has the tables, constraints and stats of the data it will run on.
- Same results on any data with the tables and constraints in schema.json.
- Order does not matter unless the input program specifies it.
- Numbers must agree within 1e-6 relative.
- At most 60 seconds per program.

## Evaluate requirements (transcribed)

- `./evaluate OPTIMIZER` tests any program with the same interface as optimize.
  Exits 0 if it finds no defects, non-zero otherwise.
- At most 15 minutes.
- It may use `bin/minivm`.

The supplied bundle contains interpreter builds, docs, examples/data and stubs.
Start at `docs/README.md`; ask the assignment provider for a build if the VM does
not run. No interpreter source was supplied.

The assignment does not give a precise relative-error formula, a formal criterion
for ordering intent, or equivalence rules for failing/resource-limited originals.
Those are documented implementation interpretations in `records/CONTRACT.md`,
not extra guarantees attributed to the PDF.
