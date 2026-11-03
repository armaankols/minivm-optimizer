# MiniVM optimizer assignment

The optimizer first selects NLJOIN/HJOIN with a frozen simple cost model, then
removes a small whitelist of proven-total dead first definitions. It retains
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
./evaluate ./optimize
python3 -m unittest discover -s tests/evaluator -v
python3 -m unittest discover -s tests/adversarial -v
```

To retain historical baseline measurements, use new result paths for this
milestone:

```sh
python3 tools/verify_baseline.py --output records/dce/cli-checks.json
python3 tools/benchmark.py ./optimize --output records/dce/examples-full.json
python3 tools/benchmark.py ./optimize --joins-only --output records/dce/examples-joins-only.json
python3 tools/benchmark_dce.py --output records/dce/benchmark.json
python3 tools/probe_join_scale.py --output records/dce/scale.json
```

Compare the previous rule, current rule, always-HJOIN and always-NLJOIN on the
same eight examples and eleven targeted workloads (reference commit 3155414):

```sh
python3 tools/compare_join_policies.py --output records/dce/join-regressions.json
python3 tools/compare_join_policies.py --holdouts-only --output records/dce/join-holdouts.json
python3 tools/summarize_join_tradeoffs.py
```

The original text starter is preserved in commit `b8e7f8a` and checksummed in
`STARTER.sha256`. Original interpreter documentation starts at
[docs/README.md](docs/README.md). Development decisions and known limitations are
in [records/SESSION.md](records/SESSION.md). The historical first-milestone results
are in [records/MILESTONE_1.md](records/MILESTONE_1.md).
The implemented join rule, preconditions and cost-model limitations are in
[docs/optimizer.md](docs/optimizer.md). Current results are in
[records/join-selection/RESULTS.md](records/join-selection/RESULTS.md).
The archived frequency-based string-cost experiment and policy comparison are in
[records/join-costs/RESULTS.md](records/join-costs/RESULTS.md).
The combined tradeoff supports freezing the simpler rule on scope/complexity
grounds, not a claim of generally better performance. The exact profile experiment
and its tests remain in [experiments/](experiments/README.md).
The conservative dead-code proof and current separately measured contribution
are in [docs/dce.md](docs/dce.md) and [records/dce/RESULTS.md](records/dce/RESULTS.md).

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
