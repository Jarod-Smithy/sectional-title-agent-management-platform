# Tooling

Shared developer + agent tooling for the AI-native SDLC.

| File | Purpose |
|------|---------|
| [setup.sh](setup.sh) | One-time setup: installs `pre-commit` and the git hooks |

The enforced gates live in [../.pre-commit-config.yaml](../.pre-commit-config.yaml) and are
mirrored in CI at [../.github/workflows/ci.yml](../.github/workflows/ci.yml).

## What the hooks enforce

| Concern | Tool |
|---------|------|
| Secrets | gitleaks + detect-secrets + detect-private-key |
| Python lint/format | ruff + ruff-format |
| Python types | mypy (strict) |
| JS/TS/MD/YAML format | prettier |
| IaC format + security | terraform fmt + tfsec |
| SAST | semgrep (`p/ci`, `p/secrets`) |
| Commit messages | commitlint (Conventional Commits) |

> These hooks are **non-bypassable**: CI re-runs every check, so `git commit --no-verify`
> cannot land non-compliant code on `main`.
