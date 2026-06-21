# stak-api — Dashboard API service

Productionised backend for the trustee platform. This is the **Dashboard API
Lambda** from [`docs/SOLUTION_DESIGN.md` §5](../../docs/SOLUTION_DESIGN.md): a
single FastAPI application that serves the trustee dashboard REST API.

It lifts the proven domain logic from [`prototype/app`](../../prototype/app)
(intake → RAG → draft → Governance Guardian → ticketing) behind clean **ports**
so the same code runs three ways:

| Environment | Persistence (`Repository` port) | LLM (`LLM` port) |
| ----------- | ------------------------------- | ---------------- |
| Local dev   | SQLite                          | offline stub     |
| AWS         | DynamoDB                        | Bedrock (Claude) |

## Architecture (hexagonal)

```
app/
  settings.py        env-driven config (pydantic-settings)
  schemas.py         pydantic request/response models (field-compatible with the prototype)
  ports/             interfaces the domain depends on
    repository.py    Repository Protocol (persistence)
    llm.py           LLM Protocol (draft / answer / classify)
  adapters/          concrete implementations of the ports
    sqlite_repo.py   local dev store
    stub_llm.py      offline deterministic LLM
  domain/            pure business logic (no I/O), ported from the prototype
    intake.py guardrails.py rag.py drafting.py
  api/               FastAPI routers + dependency wiring
  main.py            app factory + Mangum handler
```

The **`Repository`** and **`LLM`** ports are the only seams that change between
local and AWS — domain code never imports `boto3` or `sqlite3` directly.

## Run locally

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/health   ·   http://localhost:8000/docs
```

Or with Docker:

```bash
docker compose up --build      # from services/api
```

## Test

```bash
pytest                          # unit + API tests
ruff check . && mypy app        # lint + types
```

## Cost posture

Nothing here costs money locally. The AWS adapters (DynamoDB, Bedrock) target
**free-tier** usage; see [`infra/`](../../infra) for the cost-guardrails that
cap spend (project budget: **$50 total**).
