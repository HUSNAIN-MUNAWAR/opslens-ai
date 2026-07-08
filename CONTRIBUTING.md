# Contributing to OpsLens AI

Thanks for your interest in contributing.

## Principles

- Keep the default demo path runnable without external credentials.
- Preserve tenant scoping, read-only SQL execution, evidence packaging, and audit visibility.
- Prefer small, reviewable pull requests with focused commit history.
- Update docs and screenshots when user-visible behavior changes.

## Local development

1. Copy `.env.example` to `.env`.
2. Start the API from `apps/api`.
3. Start the web app from `apps/web`.
4. Seed the deterministic demo data before validating workflows.

## Before opening a pull request

- Run backend tests, lint, and typing checks.
- Run frontend lint, type checks, build, and browser tests when dependencies are available.
- Document any limitations you could not verify locally.
- Avoid committing secrets, local databases, caches, screenshots with personal data, or environment-specific lockfile URLs.

## Pull request expectations

- Explain what changed and why.
- Call out any risk to governance, authorization, or data quality behavior.
- Include updated screenshots for meaningful UI changes.
- Be explicit when a feature is simulated or bounded to demo mode.

## Scope guardrails

- Do not market the demo as certified, compliant, or production deployed unless the code and docs genuinely support that claim.
- Do not remove warnings that help users distinguish deterministic demo behavior from real integrations.
