# Alerting and Watchlists

Alert rules have scope, threshold, category, severity, and notification-target intent. Alert instances have acknowledgement, assignment, snooze, resolution, investigation conversion, and audit states.

## Categories

Inventory, revenue, margin, returns, supplier, data quality, forecast deviation, demand anomaly, branch performance, purchase order, and integration health.

## Example rule patterns

- Stock cover below a policy threshold.
- Forecasted stockout within a chosen horizon.
- Margin decline beyond baseline.
- Return rate above baseline.
- Supplier lead time above SLA.
- Inventory freshness beyond expected refresh.

Watchlists package recurring operational priorities such as high-risk inventory, supplier performance, branch margin, data-quality risk, and executive priorities.

## Deterministic evaluation boundary

`POST /api/v1/alerts/evaluate` runs the seeded, deterministic rule evaluator. It evaluates the active rule set against tenant-scoped inventory, margin, and source-freshness evidence; it refreshes matching alert instances idempotently and records lifecycle audit events. Notification targets remain in-app, email-adapter stub, Slack-compatible mock, or generic-webhook mock until a delivery provider is configured.
