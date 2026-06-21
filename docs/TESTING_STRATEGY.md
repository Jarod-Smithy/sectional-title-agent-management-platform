# Testing Strategy — Sectional Title Trustee Platform

> Durable record of the platform's test architecture, folded from a principal-SDET
> review. Companion to [AI_NATIVE_SDLC_OPERATING_MODEL.md](AI_NATIVE_SDLC_OPERATING_MODEL.md)
> and the testing ADRs ([0008](adr/0008-agent-eval-gate-contract.md),
> [0009](adr/0009-changed-line-coverage-and-no-decrease.md),
> [0010](adr/0010-mutation-testing-on-safety-modules.md),
> [0011](adr/0011-frontend-test-stack.md)).

## Status legend

Items are tagged with their delivery state so the strategy doubles as a tracker:

- ✅ **Done** — landed and gating.
- 🟡 **Partial** — partially landed; follow-up scoped.
- ⬜ **Planned** — designed, not yet built.

## 0. Executive summary

The backend is a clean Python 3.12 FastAPI hexagonal app under `services/api/app`
with deterministic, offline-by-default seams: a `StubLLM`, a SQLite repo adapter,
and pure domain modules (`guardrails`, `intake`, `rag`, `drafting`). A real test
suite lives in `services/api/tests` (`test_api.py`, `test_domain.py`,
`test_dynamo_repo.py`, `test_bedrock_llm.py`, `test_auth.py`). The CI aggregation
(`All gates` in `.github/workflows/ci.yml`) is well-architected and the
`CognitoVerifier` is fail-closed.

The hardening backlog this strategy drove is largely **delivered**:

| #   | Hardening item                                             | State      | Where                                                   |
| --- | ---------------------------------------------------------- | ---------- | ------------------------------------------------------- |
| 1   | Agent Eval Gate real + blocking                            | ✅ Done    | `eval/run_eval.py`, `eval/golden/`, ADR-0008            |
| 2   | Fix `mutmut` `tests_dir`, scope to safety modules          | ✅ Done    | `pyproject.toml`, ADR-0010                              |
| 3   | Close CODEOWNERS holes (`/policy/`, `/services/**/tests/`) | ✅ Done    | `.github/CODEOWNERS`                                    |
| 4   | `policy/terraform_test.rego` rego unit tests               | ✅ Done    | `policy/terraform_test.rego`                            |
| 5   | Restore `diff-cover --fail-under=100`                      | ✅ Done    | `.github/workflows/ci.yml`, ADR-0009                    |
| 6   | Determinism: inject clock/ID into `intake.case_ref`        | ✅ Done    | `services/api/app/domain/intake.py`                     |
| 7   | Blocking `mutmut` CI job                                   | ⬜ Planned | ADR-0010 (deferred: runtime cost)                       |
| 8   | Restore Checkov `soft_fail:false` + Trivy IaC misconfig    | ⬜ Planned | needs IaC-finding triage first                          |
| 9   | Frontend Vitest + MSW unit/component tests                 | 🟡 Partial | `frontend/` (Vitest+MSW landed; Playwright/axe pending) |
| 10  | Route `date.today()` clock injection (`api/routes.py`)     | ⬜ Planned | needs FastAPI `Depends` seam                            |

**Guiding principle:** _gates are the safety net, not trust._ The default CI run is
**hermetic and $0** — no network, no AWS, no paid tokens — so the $50 lifetime cap
is safe by construction.

## 1. Test pyramid & taxonomy

Target shape — a wide deterministic base, a thin slow top.

| Layer               | ~Share | Where                                               | Tooling                                       | Budget |
| ------------------- | ------ | --------------------------------------------------- | --------------------------------------------- | ------ |
| Unit (Python)       | 45%    | `services/api/tests/test_domain.py` (+ split files) | pytest                                        | <10s   |
| Unit (TS)           | 15%    | `frontend/**/*.test.tsx`                            | Vitest + Testing Library                      | <15s   |
| Integration         | 20%    | `test_api.py`, `test_dynamo_repo.py`                | TestClient + SQLite + StubLLM; moto           | <20s   |
| Contract            | 5%     | `test_contract.py` (planned)                        | schemathesis on OpenAPI; `openapi-typescript` | <30s   |
| LLM-output / Eval   | 5%     | `eval/run_eval.py` + `eval/golden/`                 | custom harness vs StubLLM                     | <15s   |
| Regression / golden | 4%     | `test_golden_*.py` (planned)                        | syrupy snapshots                              | <10s   |
| Property-based      | 3%     | `test_props.py` (planned)                           | Hypothesis                                    | <30s   |
| Mutation            | gate   | safety modules only                                 | mutmut                                        | <5min  |
| E2E                 | 2%     | `frontend/e2e/*.spec.ts`                            | Playwright + seeded local API                 | <90s   |
| Security/authz      | 1%     | per-route 401/403 matrix                            | pytest + RSA/JWKS injection                   | <15s   |
| Performance         | smoke  | `tests/perf/*.js` (planned)                         | k6/Locust local, advisory                     | manual |
| Infra/policy        | gate   | `policy/terraform_test.rego`                        | conftest verify                               | <20s   |

**The riskiest units** are the pure domain modules: `guardrails.screen()` (5
resolution-trigger categories × matter-scoping), `intake.classify_intent` (max-score
tie-break), and `rag.chunk_document`/`search` (recursive split, BM25, overlap). These
deserve dedicated table-driven unit files split out of the single `test_domain.py`.

## 2. Determinism & $0 mechanics

Default CI is hermetic: every layer runs with `STAK_LLM_PROVIDER=stub`,
`STAK_REPO_BACKEND=sqlite`, `STAK_AUTH_ENABLED` toggled per-test,
`STAK_SERVE_STATIC=false` — exactly the env the `client` fixture sets in
`services/api/tests/conftest.py`.

| Concern      | $0 mechanism                                                            |
| ------------ | ----------------------------------------------------------------------- |
| LLM          | `StubLLM` (deterministic); `BedrockLLM` only behind `@pytest.mark.live` |
| Persistence  | SQLite in `tmp_path`; DynamoDB via `moto`                               |
| Cognito      | RSA keypair + injected `_StubJWKClient` — no pool, no JWKS fetch        |
| Bedrock      | injected fake boto3 client                                              |
| Frontend API | MSW mocks; Playwright hits a local uvicorn app with seeded SQLite       |

**Nondeterminism register:**

1. ✅ `intake.case_ref()` — now accepts injectable `now` and `token_factory` seams
   (defaults preserve production behaviour), so case refs are reproducible.
2. ⬜ `routes.add_document` / `analyze_document` — still use `date.today()`; inject a
   clock dependency (FastAPI `Depends`) or freeze with `freezegun`/`time-machine`.
3. SQLite `created_at` timestamps — normalize/freeze in snapshots.
4. **RAG ordering ties** — `rag.search` sorts by score desc; equal scores rely on
   Python's stable sort over corpus order. Assert ordering only where scores differ,
   or add a deterministic tie-breaker (title) before snapshotting.

**Opt-in real-service marker (OFF by default):** a `live` pytest marker, excluded by
default `addopts = "-m 'not live'"`, lets a human run `pytest -m live` locally with
credentials while CI never spends. This keeps the $50 lifetime cap safe by construction.

## 3. Auth testing strategy

The repo already solved the hard part — promote and extend it. `test_auth.py` mints
RS256 tokens with an in-process keypair, feeds the public key via `_StubJWKClient`,
and swaps `app.state.verifier` in an `auth_client` fixture. This is the correct $0,
no-pool approach.

Recommended hardening (⬜ planned):

1. **Promote** `keypair` / `mint_token` / `_StubJWKClient` / `auth_token` into the
   shared `conftest.py` so every file can request an authenticated client.
2. **A 401/200 matrix** parametrized over the full route table (`test_authz_matrix.py`)
   — `/api/health` public, everything else 401 without a token and not-401 with one.
3. **Fail-closed paths** (keep + extend): 503 when `auth_enabled` but `verifier is
None`; 401 on garbage/expired/wrong-issuer/wrong-client/id-token/bad-signature.
   Add clock-skew at the `exp` boundary and **algorithm confusion** (reject `alg:none`
   / HS256-signed-with-public-key — `CognitoVerifier.verify` pins `algorithms=["RS256"]`).
4. **Authorization (403)** — when trustee-vs-admin authorization lands (Dev Console /
   `assist/config` kill-switch), add 403 cases for a valid token lacking the group.
   `Principal.groups` plumbing already exists.

## 4. Frontend testing (activates the `node` gate)

The Next.js (App Router, TS) app mirrors the prototype across 5 surfaces + admin Dev
Console, with Cognito SRP login. All-$0 stack:

| Concern        | Tool                                                 | State                  |
| -------------- | ---------------------------------------------------- | ---------------------- |
| Component/unit | Vitest + `@testing-library/react`                    | 🟡 landed              |
| API mocking    | MSW                                                  | 🟡 landed              |
| E2E            | Playwright (vs `next start` + local uvicorn StubLLM) | ⬜ planned (not in CI) |
| A11y           | `@axe-core/playwright` + `vitest-axe`                | ⬜ planned             |
| Type contract  | `openapi-typescript` (client types from API schema)  | ⬜ planned             |

The `node` gate already runs `npm run typecheck` + `npm test --if-present`. Keep
Playwright e2e in a **separate** `frontend-e2e` job so it doesn't slow the fast path.
Do **not** drive real Cognito SRP in e2e: run the API with `STAK_AUTH_ENABLED=false`
for the happy path, or seed a token minted from the same RSA test keypair. Reserve a
real SRP login for an opt-in `@live` Playwright project.

## 5. Test data / fixtures (POPIA-safe)

`seed.py` loads a synthetic, anonymised corpus ("Acacia Heights Body Corporate",
fictional senders, a deliberate Governance-Guardian BLOCK demo). It is the canonical
fixture source — already POPIA-safe.

- **Single source of synthetic truth:** factor the seed tuples into a shared fixtures
  module reused by integration tests _and_ the eval golden set.
- **Factory helpers:** `make_email()`, `make_resolution()`, `make_draft()` builders.
- **POPIA guardrail test:** a meta-test asserting no fixture contains a real-looking
  SA ID / phone / out-of-allowlist email domain (regex scan over fixtures).
- **Agent sandboxes use synthetic data only** — never production tables.

## 6. Coverage policy

| Policy                           | State                        | Gate                         |
| -------------------------------- | ---------------------------- | ---------------------------- |
| Project floor `fail_under = 90`  | ✅                           | `pytest --cov`               |
| Changed-line coverage = **100**  | ✅ (was 90 bootstrap)        | `diff-cover` (PR) — ADR-0009 |
| Coverage-cannot-decrease ratchet | ⬜ planned                   | new gate — ADR-0009          |
| Mutation score on safety modules | 🟡 config done; job deferred | ADR-0010                     |

100% on _changed lines_ is reasonable because the diff-budget caps PRs at 50
files/1500 lines. **Exemptions must be line-level `# pragma: no cover`, never
file-level** — already used at the JWKS-fetch failure path and behind the `live`
marker for real-AWS branches.

## 7. CI wiring

Map of test type → job (blocking unless noted):

| Test type                        | Job                      | Blocking                      | $0  |
| -------------------------------- | ------------------------ | ----------------------------- | --- |
| Lint/format/secrets/SAST/mypy    | `lint-format`            | ✅                            | ✅  |
| Python unit+integration+coverage | `python`                 | ✅                            | ✅  |
| Diff-cover (changed lines → 100) | `python` (PR)            | ✅                            | ✅  |
| Mutation (scoped)                | `mutation` (planned)     | ⬜                            | ✅  |
| Contract (schemathesis)          | `python` (planned)       | ⬜                            | ✅  |
| Property-based (Hypothesis)      | `python` (planned)       | ⬜                            | ✅  |
| Eval gate (golden)               | `eval`                   | ✅                            | ✅  |
| Frontend unit/component/a11y     | `node`                   | 🟡                            | ✅  |
| Frontend e2e (Playwright)        | `frontend-e2e` (planned) | ⬜                            | ✅  |
| Security SAST/SCA/secret         | `security`               | ✅                            | ✅  |
| IaC misconfig (Checkov/Trivy)    | `security`               | 🟡 (Checkov `soft_fail:true`) | ✅  |
| Policy rego unit tests           | `policy`                 | ✅                            | ✅  |
| Performance/load (k6)            | nightly/manual           | advisory                      | ✅  |
| Live AWS/Bedrock/Cognito         | `@live` marker           | OFF in CI                     | $   |

**The eval gate** imports the same domain code the product uses (real brain), runs
`StubLLM` + BM25 over a deterministic golden set, and enforces three thresholds:
**grounded-citation 100% / fabricated-citation 0% / date-version 100%**. It is
CODEOWNERS-protected so an agent cannot soften thresholds. See ADR-0008.

**Mutation** is the anti-gate-gaming net: it stops an agent writing assertion-free
tests that inflate coverage. The config is fixed and scoped to `domain/guardrails.py`,
`domain/intake.py`, `security/cognito.py`; the blocking CI job is deferred pending a
runtime/Actions-minute measurement (consider scheduled, not per-PR). See ADR-0010.

## 8. AI-native SDLC fit

For "gates are the safety net" to hold once agents author product code:

1. **CODEOWNERS fences everything an agent could use to weaken its own net** — now
   includes `/policy/` and `/services/**/tests/` (with the tests rule last for
   last-match-wins precedence) alongside `/.github/`, `/eval/`, `/infra/`.
2. **Reviewer agent** reviews _product_ diffs but must never approve diffs touching
   CODEOWNERS-protected paths — those require the human owner.
3. **Testing stays a deterministic gate, not an LLM agent** — thresholds and gate
   logic are pass/fail scripts and human-owned. An LLM may later _propose_ new golden
   cases, but never edit thresholds.
4. **Anti-gate-gaming = mutation + eval**, both human-owned and (eventually) blocking.

## 9. Phased plan ($0-first)

- **P0.5 — Hardening (largely done):** eval gate real + blocking ✅; mutmut config ✅;
  diff-cover 100 ✅; rego unit tests ✅; CODEOWNERS holes closed ✅; `case_ref`
  determinism ✅. Remaining: blocking mutation job, Checkov/Trivy strictness, route
  clock injection, split `test_domain.py`, auth matrix.
- **P1 — Frontend activation ($0):** Vitest + TL + MSW 🟡; Playwright e2e + axe;
  `openapi-typescript` client + schemathesis contract job; prompt-injection fixtures
  into `/api/inbox` + `/api/ask`.
- **P2 — Depth ($0 local / opt-in real):** Hypothesis property tests; syrupy golden
  snapshots; k6/Locust local perf smoke (advisory); coverage-cannot-decrease ratchet;
  opt-in `@live` Bedrock/Cognito/terratest suites (OFF in CI).

**Diff-budget discipline:** land each item as its own PR, well under 50 files/1500
lines.

## 10. Risks

- **Nondeterminism blocks golden/eval/mutation** until route `date.today()` is
  injected — do that before landing route-level snapshots, or normalize in-test.
- **RAG retrieval ties** rely on stable sort — add a deterministic tie-breaker before
  snapshotting ordering.
- **`test_api.py` conditional asserts** (`if blocked:` / `if clean:`) can pass
  vacuously — replace with explicit fixtures that guarantee both states.
- **Guardrail logic is regex-based** — high-value mutation + property-fuzz target;
  small wording changes can silently open a no-go path.
- **`@live` cost cap:** any real-AWS test must stay behind the `live` marker excluded
  by default `addopts`, or the $50 lifetime cap is at risk.
