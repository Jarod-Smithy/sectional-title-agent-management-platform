## What & why

<!-- Link the issue this PR resolves. Agents: include the originating intake issue. -->

Resolves #

## Summary

<!-- What changed and why. Keep it grounded in the linked issue's acceptance criteria. -->

## Checklist (gates are also enforced in CI — this is a self-audit)

- [ ] Conventional Commit title (`feat:`, `fix:`, `chore:`…) — drives SemVer/changelog
- [ ] No secrets added (gitleaks / detect-secrets pass)
- [ ] Lint + format clean (ruff/ruff-format, prettier, terraform fmt)
- [ ] Types pass (mypy strict / tsc)
- [ ] Tests added/updated; coverage not reduced on changed modules
- [ ] Security scan clean (no new Critical/High from semgrep/trivy/checkov)
- [ ] Eval gate unaffected or improved (no grounding/citation regression)
- [ ] Docs updated if behaviour or interfaces changed

## Risk & rollback

<!-- Blast radius, feature flags, and how to roll back if the deploy misbehaves. -->

## Agent provenance

<!-- Auto-filled by the SDLC agents: which agent authored / reviewed, and the run id. -->

- Authored by:
- Reviewed by:
- SDLC run:
