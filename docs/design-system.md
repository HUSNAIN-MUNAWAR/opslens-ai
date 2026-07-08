# Design System

This document describes the Phase 3 implementation boundary for OpsLens AI. The repository is a synthetic-demo, production-oriented reference platform. It distinguishes working deterministic behavior, simulated workflows, optional provider adapters, and future enterprise integration extensions.

## Implemented

- Tenant-scoped FastAPI `/api/v1` routes.
- Synthetic demo data for Northstar Retail Group, Crescent Commerce Co., and Atlas Distribution Demo.
- Deterministic local workflows that do not require external keys.
- Audit events for sensitive workflow actions.
- Clear demo and production-boundary language.

## Production boundary

Before production deployment, configure managed PostgreSQL, Redis, secrets management, TLS, trusted origins, centralized logs, backups, access reviews, incident response, and a dedicated read-only AI query role. Do not claim formal compliance until controls are independently implemented and audited.

## Tokens

- Graphite and charcoal backgrounds.
- Warm off-white surfaces.
- Emerald healthy states.
- Amber review states.
- Coral critical states.
- Focus-visible controls and reduced-motion-friendly UI.

## Component patterns

Metric cards, alert badges, data-quality badges, query-plan cards, SQL validation cards, evidence cards, scenario impact cards, approval timelines, report status blocks, source freshness indicators, empty states, loading skeletons, permission states, degraded-service banners, and command-palette items.
