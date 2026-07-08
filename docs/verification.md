# Verification

## Phase 3 local verification results

Executed in the current build environment.

| Check | Result |
|---|---|
| Backend unit/integration tests | `C:\Users\EliteBook\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q` passed: **17 passed** |
| Backend lint | `C:\Users\EliteBook\AppData\Local\Programs\Python\Python312\python.exe -m ruff check .` passed |
| Backend typing | `C:\Users\EliteBook\AppData\Local\Programs\Python\Python312\python.exe -m mypy app` passed |
| Fresh Alembic migration | Not rerun in this launch pass |
| Seed verification | Not rerun manually in this launch pass; API tests exercise seeded deterministic flows through app startup |
| Frontend dependencies | `npm ci` could not be completed in this environment. The lockfile was corrected from internal registry URLs to `registry.npmjs.org`, but package extraction did not finish cleanly here. |
| Frontend ESLint | Not run in this launch pass because `npm ci` did not complete |
| Frontend TypeScript | Not run in this launch pass because `npm ci` did not complete |
| Frontend production build | Not run in this launch pass because `npm ci` did not complete |
| Browser tests | Not run in this launch pass because `npm ci` did not complete |
| Screenshot generation | Existing real screenshot set preserved and organized under `assets/screenshots`; one screenshot was visually spot-checked against the local repository asset set. |
| Docker Compose | Not verified because Docker is not available in this environment. |

## Launch-pass fixes applied during verification

- Backend test isolation now uses unique temp-backed SQLite database files in `tests/test_api.py` and `tests/test_phase3_workflows.py`, avoiding Windows file-lock failures on fixed shared paths.
- `apps/web/package-lock.json` was normalized to public `registry.npmjs.org` tarball URLs so the repository no longer depends on environment-specific internal package sources.
- `docker-compose.yml` now uses `NEXT_PUBLIC_API_BASE_URL`, matching the web client configuration.

## Smoke coverage included in backend tests

- Login and workspace membership.
- Workspace switch and cross-tenant denial.
- Dashboard metrics.
- Governed Copilot question and unsupported-question block.
- SQL governance with mutation, multi-statement, dangerous function, and tenant-scope tests.
- Data-quality lifecycle.
- Scenario creation and multi-step approval.
- Report generation and CSV export.
- CSV/JSON import preview, commit, and rollback simulation.
- API key creation, programmatic access, and revocation.
- Alert rule evaluation and watchlist membership.
- Database health and evidence-package export.
