# Local prototype — Sectional Title Trustee Platform

A **self-contained, local-only** prototype of the MVP triad
([docs/VISION_AND_REQUIREMENTS.md §6](../docs/VISION_AND_REQUIREMENTS.md)) so you can
click through the product and give feedback **before** any AWS resources are deployed.

> This is a throwaway feedback sandbox. It deliberately lives outside the strict
> CI gates (`services/`, `sdlc-agents/`). It mirrors the eventual architecture
> (an LLM provider that becomes Bedrock, a SQLite store that becomes
> DynamoDB/S3, a draft→approve loop that becomes Step Functions) so the port is
> mechanical, not a rewrite.

## What it does (the MVP triad)

1. **Document brain** — load scheme documents, then **ask grounded questions**
   ("what notice period applies to an SGM?"). Retrieval is local keyword RAG.
2. **Inbound email → grounded draft → approve → file + ticket** — paste an
   inbound email; it is classified, a **draft reply** is generated grounded on
   the documents, the **Governance Guardian** screens it (matter-scoped
   resolution-gate, absolute no-gos, defamation warnings), you edit/approve, and
   on approval the exact on-screen text is **filed** to the correspondence
   ledger (it is **not emailed**) and an **auto-ticket** is created.
3. **Trustee task board** — a Kanban of tickets (To&nbsp;Do / In&nbsp;Progress /
   Done) linked back to the source email.

Cross-cutting guardrails are wired in. **Nothing is emailed** — approval _files_
a record. The only action taken without a human click is auto-**filing** a bare
acknowledgement. Money/legal actions without a _matching_ signed resolution (for
that specific unit) are **blocked**, and the seeded demo includes one such
blocked draft so you can see the machinery fire.

## Run it (zero setup, fully offline)

No dependencies — pure Python 3.11+ standard library, so there is **nothing to
pip install** and it works with no proxy/VPN:

```bash
cd prototype
./run.sh            # or: python3 -m app.main
```

Then open <http://localhost:8000>. The **sample scheme** (Acacia Heights — docs,
a signed resolution register, and a few inbound emails) is seeded automatically
on first run. Use **"Reset sample"** in the header to wipe back to that baseline
at any time.

### Optional: use real Claude instead of the offline stub

The LLM sits behind a provider interface. By default it uses a deterministic
**offline stub** (no key, no network). To upgrade to real Claude:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export STAP_LLM=anthropic          # optional; auto-detected if the key is set
```

Everything else stays identical — this is the same swap we'll make to Bedrock.

## Layout

| Path                | Eventual home                        |
| ------------------- | ------------------------------------ |
| `app/llm.py`        | Bedrock (Claude) provider            |
| `app/db.py`         | DynamoDB (tickets/cases) + S3 (docs) |
| `app/rag.py`        | Bedrock Knowledge Base               |
| `app/guardrails.py` | Governance Guardian agent            |
| `app/intake.py`     | Intake Classifier agent              |
| `app/drafting.py`   | Draft Composer agent                 |
| `app/main.py`       | API Gateway + Lambdas                |
| `web/`              | Next.js trustee dashboard            |

## Data

State lives in `prototype/data/app.db` (SQLite) — delete it to reset. Nothing
leaves your machine unless you opt into a real LLM provider.
