# eval

Golden-set **agent evaluation harness** ([docs/SOLUTION_DESIGN.md §14](../docs/SOLUTION_DESIGN.md)).
This is a **blocking CI gate**: a change that regresses grounding/citation accuracy fails the build.

Planned contents (P2/P3):

| Path               | Purpose                                                                      |
| ------------------ | ---------------------------------------------------------------------------- |
| `run_eval.py`      | CI entrypoint (`--ci`); referenced by `.github/workflows/ci.yml`             |
| `golden/`          | Versioned representative cases (intents, expected sources, rubrics)          |
| `metrics/`         | Grounding, citation-accuracy, classification, date-correctness, LLM-as-judge |
| `requirements.txt` | Eval deps                                                                    |

Hard thresholds (§14.3): grounded-citation rate **100%**, fabricated-citation rate **0%**,
date-version retrieval correctness **100%**.

> Human-owned via CODEOWNERS so agents cannot weaken their own evaluation (R2).
