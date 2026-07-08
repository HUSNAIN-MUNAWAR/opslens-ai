# API Guide

This document describes the Phase 3 implementation boundary for OpsLens AI. The repository is a synthetic-demo, production-oriented reference platform. It distinguishes working deterministic behavior, simulated workflows, optional provider adapters, and future enterprise integration extensions.

## Implemented

- Tenant-scoped FastAPI `/api/v1` routes.
- Synthetic demo data for Northstar Retail Group, Crescent Commerce Co., and Atlas Distribution Demo.
- Deterministic local workflows that do not require external keys.
- Audit events for sensitive workflow actions.
- Clear demo and production-boundary language.

## Production boundary

Before production deployment, configure managed PostgreSQL, Redis, secrets management, TLS, trusted origins, centralized logs, backups, access reviews, incident response, and a dedicated read-only AI query role. Do not claim formal compliance until controls are independently implemented and audited.

## Authentication

`POST /api/v1/auth/login` returns access and refresh tokens for demo users. Programmatic access uses scoped API keys with `X-API-Key`.

## Example

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/dashboard/overview
```
