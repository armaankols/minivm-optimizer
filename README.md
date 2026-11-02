# MiniVM optimizer assignment

The first milestone retains the supplied identity optimizer and builds an
independent evaluator. No optimization rewrites are included yet.

Python 3.9+, a POSIX system (macOS/Linux), and the supplied MiniVM interpreter are
needed. The entire `bin/`
directory is deliberately excluded from Git and the submission. Restore the
assignment's matching interpreter bundle locally at `bin/minivm` to run checks.

```sh
./optimize examples/programs/q0001.mini examples/schema.json
./evaluate ./optimize
python3 -m unittest discover -s tests/evaluator -v
python3 -m unittest discover -s tests/adversarial -v
python3 tools/benchmark.py ./optimize --output records/benchmark-baseline.json
```

The original text starter is preserved in commit `b8e7f8a` and checksummed in
`STARTER.sha256`. Original interpreter documentation starts at
[docs/README.md](docs/README.md). Development decisions and known limitations are
in [records/SESSION.md](records/SESSION.md).

The benchmark runs the eight fixed supplied programs through the public optimizer
interface. It reports every case, including unchanged cases and regressions, and
measures optimizer and VM subprocess wall time separately. This small benchmark
uses exact output comparison; the independent evaluator owns tolerant comparison
and broader semantic testing.

Evaluation failures retain text reproductions in `.evaluation-failures/`, which
is ignored by Git. A nonzero exit distinguishes an optimizer defect (1) from an
incomplete evaluation or infrastructure failure (2). A clean exit means no defect
was found in the finite suite; it does not prove soundness.

Git origin is configured to the requested repository. At setup, GitHub DNS lookup
failed and the configured GitHub CLI token was reported invalid. Remote history
and push access remain unverified; local commits must not be mistaken for pushes.
