# Authentication and Authorization

The demo supports login, refresh, logout, current-user lookup, and workspace listing/switching. Tokens carry identity and active organization context; each request resolves membership before reading organization-owned data.

## Roles

Organization Admin can manage workspace-level administration. Finance Analyst, Operations Manager, Supply Chain Manager, Branch Manager, Reviewer, and Viewer are used to demonstrate role-aware UI/service decisions. Branch Managers are additionally constrained to assigned branch scope in relevant operational queries.

API-key records support scope, expiry, last-used, revocation, and audit fields. The sample intentionally does not distribute real keys.

Programmatic API keys are issued once, signed against the configured server secret, and checked for org binding, revocation, expiry, and scope on the example programmatic API route.
