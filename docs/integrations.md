# Integrations

OpsLens AI uses adapter boundaries for data sources and notifications. It avoids claiming a live integration where only a product contract exists.

| Adapter | Phase 2 state |
|---|---|
| CSV / column mapping | Implemented local preview and simulated import completion |
| Excel | Architecture target; not implemented in the local flow |
| Shopify / WooCommerce / ERP / S3 / REST | Demo connector records and status models |
| Webhook ingestion | Event and delivery-log model; no public receiver contract yet |
| In-app notifications | Product model and demo UI context |
| Email / Slack / generic webhook | Adapter stub/mock boundary |

Real connectors need credential encryption, retries, dead-letter behavior, incremental cursors, rate-limit handling, webhook signature verification, and observability before production deployment.
