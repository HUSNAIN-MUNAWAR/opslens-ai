# Data Model

The Phase 2 model is centered around organization-owned operational data and traceable decision artifacts.

```mermaid
erDiagram
  ORGANIZATION ||--o{ ORGANIZATION_MEMBERSHIP : contains
  ORGANIZATION ||--o{ BRANCH : owns
  ORGANIZATION ||--o{ PRODUCT : owns
  ORGANIZATION ||--o{ DATA_SOURCE : connects
  ORGANIZATION ||--o{ METRIC_DEFINITION : defines
  ORGANIZATION ||--o{ ALERT : raises
  ORGANIZATION ||--o{ INVESTIGATION : tracks
  ORGANIZATION ||--o{ AI_CONVERSATION : scopes
  ORGANIZATION ||--o{ REPORT : publishes
  ORGANIZATION ||--o{ SCENARIO : simulates
  ALERT ||--o| INVESTIGATION : escalates_to
  AI_QUERY_EXECUTION ||--|| QUERY_PLAN : uses
  AI_QUERY_EXECUTION ||--o| SQL_VALIDATION_RESULT : records
  SCENARIO ||--o{ SCENARIO_ADJUSTMENT : has
  INVESTIGATION ||--o{ APPROVAL_REQUEST : requires
  IMPORT_JOB ||--o{ IMPORT_MAPPING : maps
```

## Core domains

- **Retail data:** branches, regions, suppliers, categories, products, inventory, sales, returns, POs, PO lines, and stock movements.
- **Trust data:** sources, metric definitions, quality issues, validation results, audit events, API keys, and webhook delivery logs.
- **Decision data:** alerts/rules/watchlists, forecasts/anomalies, AI conversations/executions/plans, scenarios, reports/schedules, investigations/approvals.

Every organization-facing record includes or is reached through an organization scope. The service API uses that scope in its lookup and query clauses.
