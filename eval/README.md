# eval

Golden-set **agent evaluation harness** ([docs/SOLUTION_DESIGN.md §14](../docs/SOLUTION_DESIGN.md)).
This is a **blocking CI gate**: a change that regresses grounding/citation accuracy fails the build.

The harness is **deterministic and zero-spend** — it exercises the real BM25
retrieval (`app.domain.rag`) and the grounded `StubLLM` answer path over the
versioned golden cases, so it never calls a paid model or the network.

| Path               | Purpose                                                               |
| ------------------ | --------------------------------------------------------------------- |
| `run_eval.py`      | CI entrypoint (`--ci`); referenced by `.github/workflows/ci.yml`      |
| `golden/*.json`    | Versioned suites: corpus documents + cases (expected sources / facts) |
| `test_run_eval.py` | Pytest coverage of the harness (runs in the `python` gate)            |
| `requirements.txt` | Eval deps (`-e ./services/api` — pulls in `app` + pydantic)           |

Run locally:

```bash
python eval/run_eval.py --ci   # exits non-zero on any threshold breach
```

Hard thresholds (§14.3), enforced by `--ci`: grounded-citation rate **100%**,
fabricated-citation rate **0%**, date-version retrieval correctness **100%**.

> Human-owned via CODEOWNERS so agents cannot weaken their own evaluation (R2).
