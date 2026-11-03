# MiniVM optimizer assignment

The optimizer selects NLJOIN/HJOIN with a frozen simple cost model, replaces
SORT with IOTA when stored order is guaranteed, then removes a small whitelist
of proven-total dead first definitions. It retains
overwrites that can release older register values. The independent evaluator
compares original/candidate MiniVM execution under frozen schemas.
The starter identity baseline remains preserved in Git.

Python 3.9+, a POSIX system (macOS/Linux), and the supplied MiniVM interpreter are
needed. The entire `bin/`
directory is deliberately excluded from Git and the submission. Restore the
assignment's matching interpreter bundle locally at `bin/minivm` to run checks.

```sh
./optimize examples/programs/q0001.mini examples/schema.json
./optimize --joins-only examples/programs/q0001.mini examples/schema.json
./optimize --no-sorted-order examples/programs/q0001.mini examples/schema.json
./evaluate ./optimize
python3 -m unittest discover -s tests/evaluator -v
python3 -m unittest discover -s tests/adversarial -v
```

For a fresh review, start with [REVIEW_HANDOFF.md](REVIEW_HANDOFF.md).
Implementation is frozen at `49c7048`; submission preparation changes documentation
only. [SETUP.md](SETUP.md) has installation and reproduction commands that write to
temporary paths rather than overwriting historical receipts. [WRITEUP.md](WRITEUP.md)
summarizes the implementation and results; [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)
flags pending publication and AI-usage details.

The original text starter is preserved in commit `b8e7f8a` and checksummed in
`STARTER.sha256`. Original interpreter documentation starts at
[docs/README.md](docs/README.md). Development decisions and known limitations are
in [records/SESSION.md](records/SESSION.md). The historical first-milestone results
are in [records/MILESTONE_1.md](records/MILESTONE_1.md).
The implemented join rule, preconditions and cost-model limitations are in
[docs/optimizer.md](docs/optimizer.md). Historical join-only results are in
[records/join-selection/RESULTS.md](records/join-selection/RESULTS.md).
The archived frequency-based string-cost experiment and policy comparison are in
[records/join-costs/RESULTS.md](records/join-costs/RESULTS.md).
The combined tradeoff supports freezing the simpler rule on scope/complexity
grounds, not a claim of generally better performance. The exact profile experiment
and its tests remain in [experiments/](experiments/README.md).
The conservative dead-code proof and current separately measured contribution
are in [docs/dce.md](docs/dce.md) and [records/dce/RESULTS.md](records/dce/RESULTS.md).
The guaranteed stored-order proof and isolated contribution are in
[docs/sorted-order.md](docs/sorted-order.md) and
[records/sorted-order/RESULTS.md](records/sorted-order/RESULTS.md).

The benchmark runs the eight fixed supplied programs through the public optimizer
interface. It reports every case, including unchanged cases and regressions, and
measures optimizer and VM subprocess wall time separately. This small benchmark
uses exact output comparison; the independent evaluator owns tolerant comparison
and broader semantic testing.

Evaluation failures retain text reproductions in `.evaluation-failures/`, which
is ignored by Git. A nonzero exit distinguishes an optimizer defect (1) from an
incomplete evaluation or infrastructure failure (2). A clean exit means no defect
was found in the finite suite; it does not prove soundness.

Git origin is configured to the requested repository. The user confirmed that
they pushed the baseline commits themselves. GitHub DNS lookup still fails in
this environment, so agent push access and remote history are not independently
verified here. The user will handle further pushes while that restriction remains.
