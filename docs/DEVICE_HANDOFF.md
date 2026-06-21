# Device handoff — get up and running fast

> **Purpose.** If you are picking this up on a fresh machine (or without the prior
> chat), this is the single source of truth to resume work on the **sectional-title
> trustee platform**. Read top to bottom; every command you need is here.
>
> Last updated: 2026-06-21.

---

## 0. TL;DR — resume in ~10 minutes

```bash
# 1. Clone
git clone git@github.com:Jarod-Smithy/sectional-title-agent-management-platform.git
cd sectional-title-agent-management-platform

# 2. Per-terminal env (corporate proxy + pager hygiene) — see §2
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
export AWS_PAGER="" PAGER=cat GH_PAGER=cat AWS_DEFAULT_PROFILE=stak_aws_dev

# 3. AWS SSO + GitHub auth — see §3
aws sso login --profile stak_aws_dev
gh auth status   # re-auth if needed: gh auth login

# 4. Recreate the git-ignored frontend env file — see §4 (values below)
#    -> frontend/.env.local

# 5. Run the production frontend
cd frontend && npm install && npm run dev   # http://localhost:3000

# 6. (Optional) run the no-login prototype — lives on a WIP branch, see §6
```

---

## 1. Repository & local layout

- **GitHub:** `Jarod-Smithy/sectional-title-agent-management-platform` (SSH remote, default branch `main`).
- **Prior local path (this device):** `…/OneDrive-BMWGroup/Documents Folder Macbook 2025/IDP/gh_repo/sectional-title-agent-platform`.
  On a fresh device just clone anywhere; the OneDrive path is incidental.
- **Two front-ends:**
  - `frontend/` — **production** Next.js 15 app (the real thing). Cognito SRP login. Port 3000.
  - `prototype/` — throwaway demo, **no login**, FastAPI + static web. Ports 8000 / 8010. **Untracked on `main`** — see §6 for where it now lives so it survives this device swap.

---

## 2. Per-terminal environment (important)

Every new terminal on the work machine needs these, otherwise `aws`/`gh` hang behind the
corporate proxy or page output:

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
export AWS_PAGER="" PAGER=cat GH_PAGER=cat
export AWS_DEFAULT_PROFILE=stak_aws_dev
export PATH="$PATH:$HOME/bin"   # if local CLIs were installed under ~/bin
```

Tip: pipe `gh`/`aws` through `| cat` or use `--output json` to avoid pager wedging.

---

## 3. Cloud + auth setup on the new device

- **AWS account:** `596451157763`, AdministratorAccess via **SSO**, profile `stak_aws_dev`.
  - Configure once: `aws configure sso` (or copy `~/.aws/config` profile `stak_aws_dev`).
  - Each session: `aws sso login --profile stak_aws_dev`.
- **Regions:** `af-south-1` = data plane (POPIA) + Cognito; `eu-west-1` = Bedrock inference;
  AgentCore SDLC control plane is **design-only / not deployed**.
- **GitHub CLI:** `gh auth login` (account `Jarod-Smithy`; needs `repo`, `workflow` scopes).
- **SSH key** for git: ensure your `id_ed25519` (or equivalent) is added — `ssh -T git@github.com`.

---

## 4. Recreate `frontend/.env.local` (git-ignored — NOT in the repo)

`.env.local` is intentionally git-ignored, so it does **not** clone down. Recreate it with
these **non-secret public** identifiers (they point the SPA at the live af-south-1 stack):

```env
NEXT_PUBLIC_API_BASE=https://f29y0n9h2d.execute-api.af-south-1.amazonaws.com
NEXT_PUBLIC_COGNITO_REGION=af-south-1
NEXT_PUBLIC_COGNITO_USER_POOL_ID=af-south-1_YNkawy0f9
NEXT_PUBLIC_COGNITO_CLIENT_ID=1g4ori9ppoc432omgiu6s7efsa  # gitleaks:allow
```

> The trailing `# gitleaks:allow` only silences a secret-scanner false positive (this
> public app-client ID is not a credential). Next.js ignores inline `#` comments, so you
> can copy the block verbatim — or drop the comment, either works.
>
> `frontend/.env.example` holds the same keys with placeholder values. The dev server must
> be **restarted** after creating `.env.local` (env is read at server start). If you ever
> lose these IDs, recover them with:
>
> ```bash
> aws cognito-idp list-user-pools --max-results 10 --query "UserPools[].{name:Name,id:Id}"
> aws cognito-idp list-user-pool-clients --user-pool-id af-south-1_YNkawy0f9 \
>   --query "UserPoolClients[].{name:ClientName,id:ClientId}"
> ```

---

## 5. Logging in to the production frontend

- **URL:** http://localhost:3000/login
- **User:** `trustee.chair@example.com` (exists in pool `af-south-1_YNkawy0f9`, status CONFIRMED).
- **Password:** it was created during deployment — no one set a memorable one. Set your own
  permanent password (≥12 chars; upper + lower + number + symbol). **Type it directly in the
  terminal — never paste secrets into chat:**

  ```bash
  aws cognito-idp admin-set-user-password \
    --user-pool-id af-south-1_YNkawy0f9 \
    --username trustee.chair@example.com \
    --password 'YOUR_PASSWORD_HERE' \
    --permanent
  ```

- **Cognito app client:** `1g4ori9ppoc432omgiu6s7efsa` (`stak-dev-dashboard`), public SRP
  client, no secret, flows `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH`. MFA is OFF.
- **API CORS:** HTTP API `f29y0n9h2d` allows origin `*` with `authorization`/`content-type`
  headers and GET/POST/PUT/DELETE — so dashboard calls from `localhost:3000` work after login.
- **Cosmetic warning** in the console — `'get'/'remove' is not exported from 'js-cookie'`
  (amazon-cognito-identity-js expects js-cookie 2.x named exports; we pin 3.0.8 for a CVE and
  use **in-memory** tokens, so this is non-fatal). Do not "fix" by downgrading js-cookie.

### Known bug just fixed (context)

`frontend/src/lib/config.ts` previously read env vars via a **dynamic** key
(`process.env[key]`). Next.js only inlines `NEXT_PUBLIC_*` when referenced **statically**, so
in the browser every value was `undefined` and fell back to placeholders like
`local-client-id` → login failed with _"Value 'local-client-id' at 'clientId' failed to satisfy
constraint"_. Fixed to static `process.env.NEXT_PUBLIC_*` access. (Landed via PR — see §8.)

---

## 6. The prototype + agent prompts (untracked local work — preserved on a branch)

`prototype/` and `docs/prompts/` are **untracked on `main`** by design. To make sure they
survive the device swap they were pushed to a recovery branch:

- **Branch:** `wip/local-prototype-and-prompts`
- Recover on the new device:
  ```bash
  git fetch origin
  git checkout wip/local-prototype-and-prompts   # prototype/ + docs/prompts/ are here
  ```
- Run the prototype (no login): `cd prototype && ./run.sh` (see `prototype/README.md`).
  Serves on http://localhost:8000 (and a second instance on :8010 was used for demos).

> Keep these **off `main`** unless you deliberately decide to productionize them — they will
> not pass main's Python/diff-cover/diff-budget gates as-is.

---

## 7. Running, testing, and the CI gates

- **Frontend dev:** `cd frontend && npm run dev` (port 3000).
- **Node tests:** `npm run typecheck && npm test` (Vitest + MSW). E2E (Playwright) is not in CI.
- **Python API:** under `services/api/`. Tests via `pytest`; type-check `mypy` (strict).
- **Agent Eval Gate:** `python eval/run_eval.py --ci` (deterministic, zero-spend).
- **Branch protection on `main`:** required check `All gates`; strict + linear history (squash
  only); enforce_admins; code-owner review required (owner-authored PRs by `Jarod-Smithy`
  auto-waive the code-owner review).
- **Gates ("All gates"):** lint-format, commitlint (Conventional Commits, body lines <100
  chars), python (mypy strict + pytest + **diff-cover `--fail-under=100`** on changed lines),
  node, security (Semgrep/Trivy/Checkov — Checkov still `soft_fail:true`), policy (Conftest),
  diff-budget (50 files / 1500 lines; override with label `oversized-change-approved`), eval
  (LIVE/BLOCKING), SBOM/sign/SLSA.
- **pre-commit gotcha:** ruff-format + prettier reformat on commit, so the **first** commit may
  abort with "files were modified by this hook" → just `git add -A` the reformatted files and
  commit again.

---

## 8. Current state (what's done, what's in flight)

- **Merged:** PRs #9–#16. Increments 7, C (Cognito JWT enforcement), D (production frontend),
  E parts 1&2 (Agent Eval Gate + gate hardening), and the docs/ADR fold (PR #16).
- **Live dev resources:** Cognito pool `af-south-1_YNkawy0f9`, client
  `1g4ori9ppoc432omgiu6s7efsa`, user `trustee.chair@example.com`; HTTP API
  `https://f29y0n9h2d.execute-api.af-south-1.amazonaws.com`. All within Cognito free tier.
- **In flight (this handoff):** PR for the `config.ts` env-inlining fix + this handoff doc.
  Check `gh pr list` on the new device; if not yet merged, merge it then `git pull`.

---

## 9. TODO — pick up here

### Immediate (next session)

- [ ] **Confirm end-to-end login** on production frontend after setting the password
      (§4 + §5), and click through the 5 trustee tabs to confirm live API data loads.
- [ ] **Merge the in-flight `config.ts` fix PR** (if not already merged) and `git pull main`.
- [ ] Decide whether `prototype/` + `docs/prompts/` should stay on the WIP branch or be
      formally productionized (they are recovery-only right now).
- [ ] Fix doc inconsistency: `frontend/README.md` mentions `NEXT_PUBLIC_COGNITO_POOL_ID` but
      `config.ts` reads `NEXT_PUBLIC_COGNITO_USER_POOL_ID` (config.ts is authoritative).

### Deferred backlog (from repo memory `stak-deferred-backlog.md`)

**CI / supply-chain hardening**

- [ ] Flip Checkov `soft_fail: true` → `false` + add Trivy IaC misconfig scan (needs baseline
      finding triage first, else it blocks every PR — do in a dedicated infra-hardening PR).
- [ ] Add a (non-blocking, scheduled) mutmut mutation-testing job on the 3 scoped safety
      modules (`domain/guardrails.py`, `domain/intake.py`, `security/cognito.py`).
- [ ] Make Conftest/OPA plan-render terragrunt-aware (real `terraform show -json` plan).

**App seams / determinism**

- [ ] `services/api/app/routes.py` `date.today()` clock injection (~line 92) — inject a clock
      via a `Depends`/module seam for deterministic tests.

**Auth (Cognito)**

- [ ] Enable **TOTP (software-token) MFA** for the user pool (free; currently
      `mfa_configuration = "OFF"`, `checkov:skip CKV_AWS_171`) — for prod-hardening / POPIA.
- [ ] Leave Cognito Advanced Security OFF (only paid Cognito feature) unless threat model demands.

**Data plane (DynamoDB)**

- [ ] Customer-managed KMS key (CMK) for the table (POPIA key custody; ~$1/mo — defer under cap).
- [ ] Enable point-in-time recovery (PITR) when there is real production data.

**Networking / VPC**

- [ ] Keep Lambda **out of a VPC** (decision 21 Jun 2026: managed services via IAM+TLS, nothing
      network-reachable to isolate). If ever VPC'd: DynamoDB gateway endpoint is free, but
      Bedrock + Cognito JWKS need interface endpoints ($) or NAT (~$32/mo) — conflicts with cap.

**Agent runtime (AgentCore harness — DESIGN ONLY)**

- [ ] Write the ADR: "Agent runtime = AgentCore harness (bundles Identity/Memory/Gateway/Obs);
      app inference = direct Bedrock adapter; defer standing up the harness under the cost cap;
      region TBD (prefer eu-west-1, NOT af-south-1)."
- [ ] Verify the GA region for AgentCore before any PoC; keep separate from af-south-1 data plane.

**Bedrock go-live (Increment 7 / "B")** — inference proven, apply deferred (do with user present)

- [ ] `terragrunt apply` with `bedrock_enabled=true` (least-priv InvokeModel IAM; zero standing cost).
- [ ] Set Lambda `STAK_LLM_PROVIDER=bedrock` (+ `STAK_BEDROCK_MODEL_TIER=fast` for cheap Haiku).
- [ ] Mint a trustee token, `POST /api/ask` once (bounded), verify grounded answer, then revert
      provider→stub to restore the zero-spend posture. Must use the **geo inference-profile** ID
      (`eu.anthropic.claude-…`); on-demand model IDs are rejected for modern Claude.

---

## 10. Hard constraints (do not violate)

- **$50 TOTAL lifetime cloud spend cap; default posture is zero-spend.** Keep provider `stub`,
  `bedrock_enabled=false`, MFA off, AWS-owned KMS, PITR off, no standing AgentCore.
- **Do not weaken CI gates.** Keep diff-cover at 100% on changed Python lines.
- **Never paste secrets** (passwords/tokens) into chat — type them directly into the terminal.
- **Only stage intended files** — `prototype/` and `docs/prompts/` are deliberately untracked
  on `main`; always `git add` explicit paths, never `git add -A` on `main`.
- **Conventional Commits**, body lines < 100 chars; squash-merge only (linear history).

```

```
