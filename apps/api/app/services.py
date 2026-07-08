from __future__ import annotations

from datetime import datetime, timedelta
from statistics import pstdev
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Alert, AlertRule, AnomalyRecord, Branch, DataQualityIssue, DataSource, ForecastRun, InventoryRecord,
    MetricDefinition, Product, ProductCategory, Return, SalesTransaction, Supplier,
    Investigation, Report, Scenario, User,
)

NOW = datetime(2026, 7, 7, 10, 0, 0)


def money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def _branch_scope(user: Any | None) -> int | None:
    if user is not None and getattr(user, "role_name", "") == "Branch Manager":
        assigned_branch_id = getattr(user, "assigned_branch_id", None)
        if assigned_branch_id:
            return int(assigned_branch_id)
    return None


def _quality_notices(db: Session, organization_id: int, tables: list[str]) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(DataQualityIssue).where(
            DataQualityIssue.organization_id == organization_id,
            DataQualityIssue.status.in_(["open", "acknowledged"]),
            DataQualityIssue.affected_table.in_(tables),
        )
    ).all()
    return [
        {
            "severity": item.severity,
            "message": f"{item.issue_type}: {item.remediation}",
            "affected_table": item.affected_table,
            "quality_issue_id": item.id,
        }
        for item in rows
    ]


def overview(db: Session, organization_id: int, user: Any | None = None) -> dict[str, Any]:
    since = NOW - timedelta(days=30)
    branch_id = _branch_scope(user)
    sales_filter = [SalesTransaction.organization_id == organization_id, SalesTransaction.occurred_at >= since]
    inventory_filter = [InventoryRecord.organization_id == organization_id]
    return_filter = [Return.organization_id == organization_id, Return.occurred_at >= since]
    if branch_id:
        sales_filter.append(SalesTransaction.branch_id == branch_id)
        inventory_filter.append(InventoryRecord.branch_id == branch_id)
        return_filter.append(Return.branch_id == branch_id)
    revenue = db.scalar(select(func.sum(SalesTransaction.quantity * SalesTransaction.unit_price - SalesTransaction.discount_amount)).where(*sales_filter)) or 0
    cost = db.scalar(select(func.sum(SalesTransaction.quantity * SalesTransaction.unit_cost)).where(*sales_filter)) or 0
    inventory = db.scalar(select(func.sum(InventoryRecord.inventory_value)).where(*inventory_filter)) or 0
    returns = db.scalar(select(func.sum(Return.amount)).where(*return_filter)) or 0
    risk = select(func.count(InventoryRecord.id)).join(Product, Product.id == InventoryRecord.product_id).where(*inventory_filter, InventoryRecord.available_units <= Product.reorder_point)
    risk_count = db.scalar(risk) or 0
    open_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.organization_id == organization_id, Alert.status.in_(["open", "acknowledged"]))) or 0
    q_notices = _quality_notices(db, organization_id, ["inventory_records", "sales_transactions", "returns"])
    return {
        "kpis": [
            {"label": "Revenue", "value": money(revenue), "display": f"PKR {revenue / 1_000_000:.2f}M", "delta": 8.4, "trend": "up", "metric": "revenue"},
            {"label": "Gross margin", "value": money((revenue - cost) / revenue * 100 if revenue else 0), "display": f"{(revenue - cost) / revenue * 100 if revenue else 0:.1f}%", "delta": -2.1, "trend": "down", "metric": "gross_margin"},
            {"label": "Inventory value", "value": money(inventory), "display": f"PKR {inventory / 1_000_000:.2f}M", "delta": 1.8, "trend": "up", "metric": "inventory_value"},
            {"label": "Stockout risk", "value": risk_count, "display": str(risk_count), "delta": 12.0, "trend": "up", "metric": "stockout_risk"},
            {"label": "Return rate", "value": money(returns / revenue * 100 if revenue else 0), "display": f"{returns / revenue * 100 if revenue else 0:.1f}%", "delta": 0.7, "trend": "up", "metric": "return_rate"},
        ],
        "what_changed": "Gross margin declined because discount intensity rose in Consumer Electronics while supplier cost and delivery variance remained elevated. Inventory data has one delayed-refresh warning that is carried into governed answers.",
        "attention": [
            {"priority": "Critical", "title": "Stock cover needs approval-controlled action", "detail": "High-velocity SKUs are below their reorder policy.", "action": "Open Decision Workbench"},
            {"priority": "High", "title": "Category-level margin erosion", "detail": "Discounts and landed-cost pressure are both present.", "action": "Create investigation"},
            {"priority": "High", "title": "Supplier delivery variance", "detail": "At-risk purchase orders require supply-chain review.", "action": "View supplier watchlist"},
        ],
        "open_alert_count": open_alerts,
        "data_quality_notices": q_notices,
    }


def revenue_trend(db: Session, organization_id: int, user: Any | None = None) -> list[dict[str, Any]]:
    start = NOW - timedelta(days=42)
    clauses = [SalesTransaction.organization_id == organization_id, SalesTransaction.occurred_at >= start]
    if _branch_scope(user):
        clauses.append(SalesTransaction.branch_id == _branch_scope(user))
    rows = db.execute(
        select(func.date(SalesTransaction.occurred_at), func.sum(SalesTransaction.quantity * SalesTransaction.unit_price - SalesTransaction.discount_amount))
        .where(*clauses)
        .group_by(func.date(SalesTransaction.occurred_at))
        .order_by(func.date(SalesTransaction.occurred_at))
    ).all()
    return [{"date": str(day), "revenue": money(value)} for day, value in rows]


def branch_comparison(db: Session, organization_id: int, user: Any | None = None) -> list[dict[str, Any]]:
    since = NOW - timedelta(days=30)
    clauses = [SalesTransaction.organization_id == organization_id, SalesTransaction.occurred_at >= since, Branch.organization_id == organization_id]
    if _branch_scope(user):
        clauses.append(SalesTransaction.branch_id == _branch_scope(user))
    rows = db.execute(
        select(Branch.id, Branch.name, func.sum(SalesTransaction.quantity * SalesTransaction.unit_price - SalesTransaction.discount_amount), func.sum(SalesTransaction.quantity * SalesTransaction.unit_cost))
        .join(SalesTransaction, SalesTransaction.branch_id == Branch.id)
        .where(*clauses)
        .group_by(Branch.id, Branch.name)
        .order_by(func.sum(SalesTransaction.quantity * SalesTransaction.unit_price - SalesTransaction.discount_amount).desc())
    ).all()
    return [{"branch_id": branch_id, "branch": name, "revenue": money(revenue), "margin": money((revenue-cost)/revenue*100 if revenue else 0), "status": "watch" if "Islamabad" in name else "healthy"} for branch_id, name, revenue, cost in rows]


def category_performance(db: Session, organization_id: int) -> list[dict[str, Any]]:
    since = NOW - timedelta(days=30)
    rows = db.execute(
        select(ProductCategory.name, func.sum(SalesTransaction.quantity * SalesTransaction.unit_price - SalesTransaction.discount_amount), func.sum(SalesTransaction.quantity * SalesTransaction.unit_cost))
        .join(Product, Product.id == SalesTransaction.product_id)
        .join(ProductCategory, Product.category_id == ProductCategory.id)
        .where(SalesTransaction.organization_id == organization_id, Product.organization_id == organization_id, ProductCategory.organization_id == organization_id, SalesTransaction.occurred_at >= since)
        .group_by(ProductCategory.name)
        .order_by(func.sum(SalesTransaction.quantity * SalesTransaction.unit_price - SalesTransaction.discount_amount).desc())
        .limit(12)
    ).all()
    return [{"category": name, "revenue": money(revenue), "margin": money((revenue-cost)/revenue*100 if revenue else 0), "anomaly": name in {"Consumer Electronics", "Home Appliances"}} for name, revenue, cost in rows]


def stockout_risks(db: Session, organization_id: int, user: Any | None = None) -> list[dict[str, Any]]:
    clauses = [InventoryRecord.organization_id == organization_id, Product.organization_id == organization_id, Branch.organization_id == organization_id, Supplier.organization_id == organization_id, InventoryRecord.available_units <= Product.reorder_point]
    if _branch_scope(user):
        clauses.append(InventoryRecord.branch_id == _branch_scope(user))
    rows = db.execute(
        select(Product.sku, Product.name, Branch.name, Supplier.name, InventoryRecord.available_units, Product.reorder_point, Product.unit_cost)
        .join(Product, Product.id == InventoryRecord.product_id)
        .join(Branch, Branch.id == InventoryRecord.branch_id)
        .join(Supplier, Supplier.id == Product.supplier_id)
        .where(*clauses)
        .order_by(InventoryRecord.available_units.asc())
        .limit(24)
    ).all()
    return [{"sku": sku, "product": product, "branch": branch, "supplier": supplier, "available": available, "reorder_point": reorder, "days_cover": max(1, round(available/max(1, reorder/4), 1)), "risk": "critical" if available < max(2, reorder*.2) else "high", "recommended_order": max(reorder*3-available, 0), "unit_cost": cost} for sku, product, branch, supplier, available, reorder, cost in rows]


def supplier_risk(db: Session, organization_id: int) -> list[dict[str, Any]]:
    rows = db.execute(select(Supplier.name, Supplier.lead_time_days, Supplier.on_time_rate, Supplier.risk_score).where(Supplier.organization_id == organization_id).order_by(Supplier.risk_score.desc()).limit(10)).all()
    return [{"supplier": name, "lead_time_days": lead, "on_time_rate": round(rate*100, 1), "risk_score": round(score, 1), "status": "at risk" if score > 65 else "monitor"} for name, lead, rate, score in rows]


def evaluate_alert_rules(db: Session, organization_id: int) -> dict[str, Any]:
    """Evaluate deterministic demo rules against real seeded operational data.

    The evaluator is intentionally idempotent for open/acknowledged alerts: running it refreshes
    evidence on an existing entity/rule pair rather than continuously creating duplicate cards.
    A future worker can call the same service on a schedule.
    """
    rules = db.scalars(select(AlertRule).where(AlertRule.organization_id == organization_id, AlertRule.status == "active")).all()
    existing = {
        (row.rule_id, row.entity_type, row.entity_id): row
        for row in db.scalars(select(Alert).where(Alert.organization_id == organization_id, Alert.status.in_(["open", "acknowledged", "snoozed"]))).all()
    }
    created = 0
    refreshed = 0
    triggered: list[dict[str, Any]] = []

    def emit(rule: AlertRule, entity_type: str, entity_id: str, title: str, description: str, evidence: dict[str, Any]) -> None:
        nonlocal created, refreshed
        key = (rule.id, entity_type, entity_id)
        alert = existing.get(key)
        if alert:
            alert.severity = rule.severity
            alert.title = title
            alert.description = description
            alert.evidence = evidence
            refreshed += 1
        else:
            db.add(Alert(
                organization_id=organization_id,
                rule_id=rule.id,
                severity=rule.severity,
                title=title,
                description=description,
                status="open",
                entity_type=entity_type,
                entity_id=entity_id,
                confidence=0.86,
                evidence=evidence,
            ))
            created += 1
        triggered.append({"rule": rule.name, "entity_type": entity_type, "entity_id": entity_id, "severity": rule.severity})

    for rule in rules:
        if rule.metric_slug == "stockout_risk":
            for risk in stockout_risks(db, organization_id)[:10]:
                if risk["days_cover"] < rule.threshold:
                    entity_id = f"{risk['sku']}:{risk['branch']}"
                    emit(rule, "inventory", entity_id, f"Forecasted stockout: {risk['sku']} at {risk['branch']}", f"Stock cover is {risk['days_cover']} days against the {rule.threshold}-day rule threshold.", risk)
        elif rule.metric_slug == "freshness":
            for source in db.scalars(select(DataSource).where(DataSource.organization_id == organization_id)):
                if source.freshness_hours > rule.threshold or source.status in {"delayed", "failing"}:
                    emit(rule, "data_source", str(source.id), f"Data freshness exceeds SLA: {source.name}", f"{source.name} is {source.freshness_hours:.1f} hours behind its expected refresh schedule.", {"source": source.name, "freshness_hours": source.freshness_hours, "status": source.status})
        elif rule.metric_slug == "gross_margin":
            for category in category_performance(db, organization_id):
                if category["anomaly"]:
                    emit(rule, "category", category["category"], f"Margin decline watch: {category['category']}", f"Category margin is {category['margin']:.1f}% and is flagged against its synthetic baseline.", category)
    db.flush()
    return {"created": created, "refreshed": refreshed, "triggered": triggered, "evaluated_rule_count": len(rules)}


def alerts(db: Session, organization_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(select(Alert).where(Alert.organization_id == organization_id).order_by(Alert.created_at.desc()).limit(50)).all()
    return [{"id": row.id, "severity": row.severity, "title": row.title, "description": row.description, "status": row.status, "confidence": row.confidence, "entity_type": row.entity_type, "evidence": row.evidence} for row in rows]


def metric_catalog(db: Session, organization_id: int) -> list[dict[str, Any]]:
    metrics = db.scalars(select(MetricDefinition).where((MetricDefinition.organization_id == organization_id) | (MetricDefinition.organization_id.is_(None))).order_by(MetricDefinition.name)).all()
    return [{"id": m.id, "name": m.name, "slug": m.slug, "description": m.description, "formula": m.formula, "source_tables": m.source_tables, "dimensions": m.dimensions, "valid_filters": m.valid_filters, "time_grain": m.time_grain, "owner": m.owner, "status": m.status, "data_quality_status": m.data_quality_status, "last_calculated_at": m.last_calculated_at, "example_questions": m.example_questions, "dependencies": m.dependencies, "certified": m.certified} for m in metrics]


def metric_graph(db: Session, organization_id: int) -> dict[str, Any]:
    metrics = metric_catalog(db, organization_id)
    nodes = [{"id": m["slug"], "label": m["name"], "type": "metric"} for m in metrics]
    edges = []
    for metric in metrics:
        for dependency in metric.get("dependencies", []):
            edges.append({"source": dependency, "target": metric["slug"]})
    edges.extend([{"source": "gross_margin", "target": "margin_decline_alert"}, {"source": "margin_decline_alert", "target": "investigation"}])
    return {"nodes": nodes, "edges": edges}


def data_quality_overview(db: Session, organization_id: int) -> dict[str, Any]:
    issues = db.scalars(select(DataQualityIssue).where(DataQualityIssue.organization_id == organization_id).order_by(DataQualityIssue.created_at.desc())).all()
    active = [issue for issue in issues if issue.status != "resolved"]
    critical = [issue for issue in active if issue.severity == "critical"]
    sources = db.scalars(select(DataSource).where(DataSource.organization_id == organization_id)).all()
    score = max(56, 100 - len(active)*5 - len(critical)*8)
    return {
        "overall_score": score,
        "freshness_score": max(60, 98 - len([s for s in sources if s.status == "delayed"])*18),
        "completeness_score": max(60, 97 - len([i for i in active if "Missing" in i.issue_type])*8),
        "consistency_score": max(60, 96 - len([i for i in active if "Duplicate" in i.issue_type])*6),
        "accuracy_proxy_score": 88,
        "active_issue_count": len(active),
        "critical_source_count": len([s for s in sources if s.status in {"failing", "delayed"}]),
        "issues": [{"id": i.id, "issue_type": i.issue_type, "affected_table": i.affected_table, "severity": i.severity, "status": i.status, "affected_records": i.affected_records, "remediation": i.remediation, "related_metrics": i.related_metrics} for i in issues],
        "sources": [{"id": s.id, "name": s.name, "source_type": s.source_type, "status": s.status, "last_synced_at": s.last_synced_at, "freshness_hours": s.freshness_hours} for s in sources],
        "trend": [{"day": str((NOW - timedelta(days=i)).date()), "score": max(58, score - (i % 4) + 2)} for i in reversed(range(14))],
    }


def alerts_and_watchlists(db: Session, organization_id: int, user_id: int) -> dict[str, Any]:
    from app.models import AlertRule, Watchlist, WatchlistItem
    rules = db.scalars(select(AlertRule).where(AlertRule.organization_id == organization_id).order_by(AlertRule.name)).all()
    watchlists = db.scalars(select(Watchlist).where(Watchlist.organization_id == organization_id).order_by(Watchlist.created_at.desc())).all()
    return {
        "alerts": alerts(db, organization_id),
        "rules": [{"id": r.id, "name": r.name, "category": r.category, "severity": r.severity, "metric_slug": r.metric_slug, "operator": r.operator, "threshold": r.threshold, "scope_type": r.scope_type, "status": r.status, "notification_targets": r.notification_targets} for r in rules],
        "watchlists": [{"id": w.id, "name": w.name, "description": w.description, "criteria": w.criteria, "shared": w.is_shared, "owner_id": w.owner_id, "items": [{"id": item.id, "entity_type": item.entity_type, "entity_id": item.entity_id, "label": item.label, "status": item.status} for item in db.scalars(select(WatchlistItem).where(WatchlistItem.watchlist_id == w.id, WatchlistItem.status == "active")).all()]} for w in watchlists],
    }


def _daily_revenue(db: Session, organization_id: int) -> list[float]:
    start = NOW - timedelta(days=30)
    rows = db.execute(
        select(func.date(SalesTransaction.occurred_at), func.sum(SalesTransaction.quantity*SalesTransaction.unit_price - SalesTransaction.discount_amount))
        .where(SalesTransaction.organization_id == organization_id, SalesTransaction.occurred_at >= start)
        .group_by(func.date(SalesTransaction.occurred_at)).order_by(func.date(SalesTransaction.occurred_at))
    ).all()
    return [float(v) for _, v in rows]


def forecast_payload(db: Session, organization_id: int, metric_slug: str = "revenue", horizon_days: int = 14) -> dict[str, Any]:
    historical = _daily_revenue(db, organization_id)
    if not historical:
        historical = [100000.0] * 14
    alpha = 0.35
    smoothed = historical[0]
    for value in historical:
        smoothed = alpha * value + (1-alpha) * smoothed
    volatility = pstdev(historical[-14:]) if len(historical) > 2 else smoothed * .08
    forecast = [round(smoothed * (1 + i*.005), 2) for i in range(1, horizon_days+1)]
    quality = _quality_notices(db, organization_id, ["sales_transactions", "inventory_records"])
    return {
        "metric_slug": metric_slug,
        "horizon_days": horizon_days,
        "method": "exponential_smoothing_baseline",
        "label": "Baseline forecast — synthetic workspace",
        "history": [{"index": i+1, "value": round(v, 2)} for i, v in enumerate(historical[-21:])],
        "forecast": [{"day": i+1, "value": value, "lower": round(max(0, value-volatility), 2), "upper": round(value+volatility, 2)} for i, value in enumerate(forecast)],
        "assumptions": ["Historical sales pattern is stable", "No unmodeled promotions", "Supplier lead time remains within current baseline"],
        "quality_notices": quality,
        "explanation": "The projection uses a transparent exponentially weighted baseline. It is a decision-support estimate, not a production accuracy claim.",
    }


def anomaly_payload(db: Session, organization_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(select(AnomalyRecord).where(AnomalyRecord.organization_id == organization_id).order_by(AnomalyRecord.created_at.desc())).all()
    return [{"id": row.id, "metric_slug": row.metric_slug, "severity": row.severity, "anomaly_type": row.anomaly_type, "entity_type": row.entity_type, "entity_id": row.entity_id, "observed_value": row.observed_value, "baseline_value": row.baseline_value, "z_score": row.z_score, "explanation": row.explanation, "evidence": row.evidence} for row in rows]


def scenario_impact(db: Session, organization_id: int, adjustments: list[dict[str, Any]]) -> dict[str, Any]:
    base = overview(db, organization_id)
    revenue = float(base["kpis"][0]["value"])
    margin = float(base["kpis"][1]["value"])
    stockout = float(base["kpis"][3]["value"])
    inventory = float(base["kpis"][2]["value"])
    effect = {"revenue": 0.0, "margin": 0.0, "stockout": 0.0, "inventory": 0.0, "supplier_exposure": 0.0}
    for adjustment in adjustments:
        kind = adjustment.get("type", "")
        value = float(adjustment.get("value", 0) or 0)
        if kind == "transfer_inventory":
            effect["stockout"] -= max(1, value / 20)
            effect["supplier_exposure"] -= value / 30
        elif kind == "increase_reorder":
            effect["stockout"] -= max(1, value / 25)
            effect["inventory"] += value * 600
        elif kind == "discount_change":
            effect["revenue"] += revenue * (value / 100) * .35
            effect["margin"] -= value * .55
        elif kind == "demand_change":
            effect["revenue"] += revenue * (value / 100)
            effect["stockout"] += value / 7
        elif kind == "supplier_delay":
            effect["stockout"] += max(1, value * .8)
            effect["supplier_exposure"] += value
        elif kind == "safety_stock":
            effect["stockout"] -= max(1, value / 18)
            effect["inventory"] += value * 450
    return {
        "baseline": {"revenue": revenue, "gross_margin": margin, "stockout_risk": stockout, "inventory_value": inventory},
        "projected": {"revenue": money(revenue + effect["revenue"]), "gross_margin": money(margin + effect["margin"]), "stockout_risk": max(0, round(stockout + effect["stockout"])), "inventory_value": money(inventory + effect["inventory"]), "supplier_exposure": money(max(0, effect["supplier_exposure"]))},
        "assurance": "Simulation only — no operational inventory, supplier, pricing, or ERP record is mutated.",
    }


def global_search(db: Session, organization_id: int, term: str, *, include_users: bool = False) -> list[dict[str, Any]]:
    """Search only entity records that belong to the active workspace.

    The route intentionally returns compact navigation metadata rather than raw records; each
    deeper page must still enforce its own organization/role checks.
    """
    term = term.strip().lower()
    if not term:
        return []
    pattern = f"%{term}%"
    results: list[dict[str, Any]] = []
    for p in db.scalars(select(Product).where(Product.organization_id == organization_id, (Product.name.ilike(pattern)) | (Product.sku.ilike(pattern))).limit(6)):
        results.append({"type": "Product", "name": p.name, "meta": p.sku, "status": "active", "href": f"/demo/inventory?sku={p.sku}"})
    for branch in db.scalars(select(Branch).where(Branch.organization_id == organization_id, (Branch.name.ilike(pattern)) | (Branch.city.ilike(pattern))).limit(5)):
        results.append({"type": "Branch", "name": branch.name, "meta": branch.city, "status": "active", "href": "/demo"})
    for category in db.scalars(select(ProductCategory).where(ProductCategory.organization_id == organization_id, ProductCategory.name.ilike(pattern)).limit(5)):
        results.append({"type": "Category", "name": category.name, "meta": "Product category", "status": "active", "href": "/demo/margin"})
    for supplier in db.scalars(select(Supplier).where(Supplier.organization_id == organization_id, Supplier.name.ilike(pattern)).limit(6)):
        results.append({"type": "Supplier", "name": supplier.name, "meta": f"Risk score {supplier.risk_score}", "status": "watch", "href": "/demo/alerts"})
    for alert in db.scalars(select(Alert).where(Alert.organization_id == organization_id, Alert.title.ilike(pattern)).limit(6)):
        results.append({"type": "Alert", "name": alert.title, "meta": alert.severity, "status": alert.status, "href": "/demo/alerts"})
    for investigation in db.scalars(select(Investigation).where(Investigation.organization_id == organization_id, Investigation.title.ilike(pattern)).limit(5)):
        results.append({"type": "Investigation", "name": investigation.title, "meta": investigation.status, "status": investigation.severity, "href": "/demo/investigations"})
    for report in db.scalars(select(Report).where(Report.organization_id == organization_id, Report.name.ilike(pattern)).limit(5)):
        results.append({"type": "Report", "name": report.name, "meta": report.report_type, "status": report.status, "href": "/demo/reports"})
    for scenario in db.scalars(select(Scenario).where(Scenario.organization_id == organization_id, Scenario.name.ilike(pattern)).limit(5)):
        results.append({"type": "Scenario", "name": scenario.name, "meta": "simulated decision", "status": scenario.status, "href": "/demo/workbench"})
    metric_query = select(MetricDefinition).where((MetricDefinition.organization_id == organization_id) | (MetricDefinition.organization_id.is_(None)), MetricDefinition.name.ilike(pattern)).limit(5)
    for metric in db.scalars(metric_query):
        results.append({"type": "Metric", "name": metric.name, "meta": metric.slug, "status": metric.data_quality_status, "href": "/demo/metrics"})
    for source in db.scalars(select(DataSource).where(DataSource.organization_id == organization_id, DataSource.name.ilike(pattern)).limit(5)):
        results.append({"type": "Data source", "name": source.name, "meta": source.source_type, "status": source.status, "href": "/demo/data-quality"})
    if include_users:
        for user in db.scalars(select(User).where(User.organization_id == organization_id, (User.full_name.ilike(pattern)) | (User.email.ilike(pattern))).limit(5)):
            results.append({"type": "User", "name": user.full_name, "meta": user.email, "status": "active" if user.is_active else "inactive", "href": "/demo/governance"})
    return results[:30]


def operation_console(db: Session, organization_id: int) -> dict[str, Any]:
    executed = db.scalar(select(func.count()).select_from(ForecastRun).where(ForecastRun.organization_id == organization_id)) or 0
    blocked = db.scalar(select(func.count()).select_from(AnomalyRecord).where(AnomalyRecord.organization_id == organization_id, AnomalyRecord.severity == "critical")) or 0
    return {
        "health": [
            {"service": "API", "status": "healthy", "detail": "Request ID and structured-log boundary enabled"},
            {"service": "Database", "status": "healthy", "detail": "Scoped persistence boundary available"},
            {"service": "Redis", "status": "configured", "detail": "Background work boundary is configured in Docker"},
            {"service": "Alert engine", "status": "healthy", "detail": "Deterministic rule evaluation in demo mode"},
            {"service": "Forecast engine", "status": "healthy", "detail": "Baseline forecast service"},
        ],
        "ai_governance": {"total_questions": 24, "supported_questions": 19, "unsupported_questions": 5, "blocked_unsafe_requests": 3, "sql_validation_failures": 2, "average_query_time_ms": 184, "average_result_size": 18, "data_quality_warnings_triggered": 7, "forecast_runs": executed, "critical_anomalies": blocked},
        "cost_model": {"label": "Demo usage telemetry and estimated cost model", "estimated_llm_tokens": 0, "estimated_sql_ms": 184, "rows_scanned_estimate": 12600, "report_generation_ms": 312, "exports": 3, "active_users": 5},
    }


def import_preview(rows: list[dict[str, Any]], import_type: str) -> dict[str, Any]:
    required = {
        "products": {"sku", "name", "unit_cost", "list_price"},
        "sales": {"sku", "quantity", "unit_price", "occurred_at"},
        "inventory": {"sku", "branch", "available_units"},
        "suppliers": {"name", "lead_time_days"},
        "purchase_orders": {"supplier", "branch", "expected_date"},
        "returns": {"sale_id", "amount", "occurred_at"},
        "branches": {"name", "city"},
    }[import_type]
    issues = []
    valid = 0
    for index, row in enumerate(rows):
        absent = sorted(field for field in required if row.get(field) in (None, ""))
        if absent:
            issues.append({"row": index + 1, "fields": absent, "message": "Missing required target field"})
        else:
            valid += 1
    columns = list(rows[0].keys()) if rows else sorted(required)
    mapping = [{"source_column": col, "target_field": col if col in required else "unmapped", "transformation": "identity", "validation": "required" if col in required else "optional"} for col in columns]
    return {"records_total": len(rows), "records_valid": valid, "records_invalid": len(rows)-valid, "preview": rows[:10], "errors": issues[:20], "mapping": mapping, "status": "ready" if not issues else "validation_failed"}


def question_plan(question: str, organization_id: int) -> dict[str, Any]:
    q = question.lower().strip()
    base = {"organization_id": organization_id, "filters": {"organization_id": organization_id}, "date_range": {"relative": "last_30_days"}, "row_limit": 24, "requires_followup": False, "confidence": 0.91, "explanation_strategy": "grounded_evidence_summary"}
    if any(term in q for term in ["stockout", "stock out", "reorder", "inventory decisions", "stock cover"]):
        return {**base, "kind": "stockout", "intent": "stockout_risk", "metrics": ["Stock cover days", "Stockout risk"], "allowed_tables": ["inventory_records", "products", "branches", "suppliers"], "dimensions": ["sku", "branch", "supplier"], "aggregation": "ranked detail", "ranking": "available_units ascending", "sql": "SELECT p.sku, p.name, b.name AS branch, i.available_units, p.reorder_point FROM inventory_records i JOIN products p ON p.id = i.product_id JOIN branches b ON b.id = i.branch_id WHERE i.organization_id = :organization_id AND i.available_units <= p.reorder_point ORDER BY i.available_units ASC LIMIT 24"}
    if "return" in q:
        return {**base, "kind": "returns", "intent": "return_rate", "metrics": ["Return rate", "Revenue"], "allowed_tables": ["returns", "branches"], "dimensions": ["branch"], "aggregation": "sum", "ranking": "return value descending", "sql": "SELECT b.name AS branch, SUM(r.amount) AS return_value FROM returns r JOIN branches b ON b.id = r.branch_id WHERE r.organization_id = :organization_id GROUP BY b.name ORDER BY return_value DESC LIMIT 12"}
    if any(term in q for term in ["margin", "underperform", "gross"]):
        return {**base, "kind": "margin", "intent": "gross_margin", "metrics": ["Gross margin", "Revenue", "Discount rate"], "allowed_tables": ["sales_transactions", "products", "product_categories"], "dimensions": ["category"], "aggregation": "sum", "ranking": "revenue descending", "sql": "SELECT c.name AS category, SUM(s.quantity * s.unit_price - s.discount_amount) AS revenue, SUM(s.quantity * s.unit_cost) AS cost FROM sales_transactions s JOIN products p ON p.id = s.product_id JOIN product_categories c ON c.id = p.category_id WHERE s.organization_id = :organization_id GROUP BY c.name ORDER BY revenue DESC LIMIT 12"}
    if any(term in q for term in ["supplier", "delivery", "delay", "lead time"]):
        return {**base, "kind": "supplier", "intent": "supplier_risk", "metrics": ["Supplier lead time", "Supplier on-time delivery"], "allowed_tables": ["suppliers"], "dimensions": ["supplier"], "aggregation": "ranked detail", "ranking": "risk score descending", "sql": "SELECT name, lead_time_days, on_time_rate, risk_score FROM suppliers WHERE organization_id = :organization_id ORDER BY risk_score DESC LIMIT 12"}
    if any(term in q for term in ["forecast", "predict", "projection"]):
        return {**base, "kind": "forecast", "intent": "revenue_forecast", "metrics": ["Revenue forecast", "Demand volatility"], "allowed_tables": ["sales_transactions"], "dimensions": ["day"], "aggregation": "baseline forecast", "ranking": "time ascending", "sql": "SELECT DATE(occurred_at) AS day, SUM(quantity * unit_price - discount_amount) AS revenue FROM sales_transactions WHERE organization_id = :organization_id GROUP BY DATE(occurred_at) ORDER BY day DESC LIMIT 30"}
    if any(term in q for term in ["data quality", "freshness", "quality issue", "missing data"]):
        return {**base, "kind": "data_quality", "intent": "data_quality", "metrics": ["Data quality status"], "allowed_tables": ["data_quality_issues", "data_sources"], "dimensions": ["source", "severity"], "aggregation": "issue detail", "ranking": "severity", "sql": "SELECT issue_type, affected_table, severity, affected_records FROM data_quality_issues WHERE organization_id = :organization_id ORDER BY severity DESC LIMIT 24"}
    if "islamabad" in q or "lahore" in q or "compare" in q or "branch" in q:
        return {**base, "kind": "branch", "intent": "branch_comparison", "metrics": ["Revenue", "Gross margin", "Return rate"], "allowed_tables": ["sales_transactions", "branches"], "dimensions": ["branch"], "aggregation": "sum", "ranking": "revenue descending", "sql": "SELECT b.name, SUM(s.quantity * s.unit_price - s.discount_amount) AS revenue, SUM(s.quantity * s.unit_cost) AS cost FROM sales_transactions s JOIN branches b ON b.id = s.branch_id WHERE s.organization_id = :organization_id GROUP BY b.name ORDER BY revenue DESC LIMIT 12"}
    return {**base, "kind": "unanswerable", "intent": "unsupported", "metrics": [], "allowed_tables": [], "dimensions": [], "aggregation": "", "ranking": "", "sql": None, "confidence": 0.12, "requires_followup": True, "explanation_strategy": "safe_redirect"}
