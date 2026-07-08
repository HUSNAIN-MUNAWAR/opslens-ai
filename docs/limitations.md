# Limitations

This document describes the Phase 3 implementation boundary for OpsLens AI. The repository is a synthetic-demo, production-oriented reference platform. It distinguishes working deterministic behavior, simulated workflows, optional provider adapters, and future enterprise integration extensions.

## Implemented

- Tenant-scoped FastAPI `/api/v1` routes.
- Synthetic demo data for Northstar Retail Group, Crescent Commerce Co., and Atlas Distribution Demo.
- Deterministic local workflows that do not require external keys.
- Audit events for sensitive workflow actions.
- Clear demo and production-boundary language.

## Production boundary

Before production deployment, configure managed PostgreSQL, Redis, secrets management, TLS, trusted origins, centralized logs, backups, access reviews, incident response, and a dedicated read-only AI query role. Do not claim formal compliance until controls are independently implemented and audited.

## Known limitations

- Forecasts are transparent baseline estimates.
- Scenario execution is simulated.
- External integrations are mocked or adapter boundaries.
- PostgreSQL RLS and dedicated read-only AI roles are documented deployment recommendations unless configured by the operator.
- Some dense visual panels still use synthetic presentation data while Phase 3 live workflow panels expose backend state and mutations.
