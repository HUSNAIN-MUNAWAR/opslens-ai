from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import *
from app.security import hash_password
from app.services import forecast_payload

NOW = datetime(2026, 7, 7, 10, 0, 0)
R = random.Random(20260707)
CATEGORIES = ["Consumer Electronics", "Home Appliances", "Mobile Accessories", "Computing", "Audio", "Kitchenware", "Personal Care", "Beverages", "Snacks", "Cleaning", "Baby Care", "Pet Supplies", "Home Decor", "Office Supplies", "Sports", "Automotive", "Health", "Fashion", "Stationery", "Lighting"]
SUPPLIERS = ["NorthStar Imports", "Vertex Distribution", "Atlas Consumer", "Meridian Supply", "Crescent Trading", "Prime Route", "Orbit Wholesale", "Lumen Partners", "Harbor Goods", "BluePeak Logistics"]
BRANCHES = [("Islamabad Branch", "North"), ("Lahore Branch", "Central"), ("Karachi Branch", "South"), ("Rawalpindi Branch", "North"), ("Faisalabad Branch", "Central")]
ORGS = [
    ("Northstar Retail Group", "northstar", "NSR", 320, 6000),
    ("Crescent Commerce Co.", "crescent", "CRC", 120, 3300),
    ("Atlas Distribution Demo", "atlas", "ATD", 120, 3300),
]

ROLE_SPECS = [
    ("Platform Admin", "Cross-workspace platform controls", ["*"]),
    ("Organization Admin", "Organization configuration, users, integrations, reports and approvals", ["dashboard:read", "ai:query", "investigation:manage", "approval:decide", "governance:manage", "export:data", "scenario:manage", "ingestion:manage", "report:manage"]),
    ("Finance Analyst", "Margin, revenue, report, and approval analysis", ["dashboard:read", "ai:query", "investigation:manage", "report:manage", "export:data", "scenario:manage"]),
    ("Operations Manager", "Inventory, alerts, investigations and operational recommendations", ["dashboard:read", "ai:query", "investigation:manage", "scenario:manage", "report:manage"]),
    ("Supply Chain Manager", "Supplier, purchase-order and inventory decisions", ["dashboard:read", "ai:query", "investigation:manage", "scenario:manage"]),
    ("Branch Manager", "Branch-scoped visibility and investigations", ["dashboard:read", "ai:query", "investigation:manage"]),
    ("Reviewer", "Approval and investigation review", ["dashboard:read", "approval:decide", "investigation:manage"]),
    ("Viewer", "Read-only organization visibility", ["dashboard:read"]),
]

METRICS = [
    ("Revenue", "revenue", "Net realized sales after discounts.", "SUM(quantity × unit_price − discount_amount)", ["sales_transactions"], ["branch", "category", "supplier"], [], "Revenue is the certified source for sales comparisons."),
    ("Gross Profit", "gross_profit", "Realized revenue less product cost.", "Revenue − SUM(quantity × unit_cost)", ["sales_transactions"], ["branch", "category"], ["revenue"], "Builds directly on Revenue."),
    ("Gross Margin", "gross_margin", "Gross profit as a percentage of realized revenue.", "Gross Profit / Revenue", ["sales_transactions", "products"], ["branch", "category", "supplier"], ["revenue", "gross_profit"], "Uses Revenue and Gross Profit."),
    ("Discount Rate", "discount_rate", "Discounts relative to list-value sales.", "SUM(discount_amount) / gross sales", ["sales_transactions"], ["branch", "category"], ["revenue"], "Useful for margin investigation."),
    ("Return Rate", "return_rate", "Returned value relative to realized sales.", "SUM(returns.amount) / Revenue", ["returns", "sales_transactions"], ["branch", "category"], ["revenue"], "Highlights abnormal return behavior."),
    ("Average Order Value", "average_order_value", "Average realized transaction value.", "Revenue / transactions", ["sales_transactions"], ["branch"], ["revenue"], "Order-value benchmark."),
    ("Units Sold", "units_sold", "Units sold in selected scope.", "SUM(quantity)", ["sales_transactions"], ["branch", "product", "category"], [], "Demand volume measure."),
    ("Inventory Value", "inventory_value", "Current inventory at unit cost.", "SUM(available_units × unit_cost)", ["inventory_records", "products"], ["branch", "product"], [], "Inventory exposure measure."),
    ("Stock Cover Days", "stock_cover", "Estimated days until inventory depletion.", "available_units / trailing daily units", ["inventory_records", "sales_transactions"], ["branch", "product"], ["units_sold"], "Transparent demand-velocity calculation."),
    ("Stockout Risk", "stockout_risk", "Risk based on stock cover, demand and supplier lead time.", "risk(stock_cover, demand_velocity, supplier_lead_time)", ["inventory_records", "suppliers", "sales_transactions"], ["branch", "product"], ["stock_cover", "units_sold"], "Used by the stockout alert rule."),
    ("Sell-through Rate", "sell_through_rate", "Units sold relative to sellable stock.", "units_sold / (units_sold + available_units)", ["sales_transactions", "inventory_records"], ["branch", "product"], ["units_sold"], "Inventory velocity measure."),
    ("Dead-stock Value", "dead_stock_value", "Inventory value with no recent demand.", "inventory_value where 30d units_sold = 0", ["inventory_records", "sales_transactions"], ["branch", "product"], ["inventory_value", "units_sold"], "Inventory recovery opportunity."),
    ("Overstock Risk", "overstock_risk", "Excess inventory against demand velocity.", "stock_cover > policy threshold", ["inventory_records", "sales_transactions"], ["branch", "product"], ["stock_cover"], "Supports reorder policy review."),
    ("Supplier Lead Time", "supplier_lead_time", "Expected delivery lead time.", "AVG(received_date − created_at)", ["purchase_orders"], ["supplier"], [], "Supplier delivery baseline."),
    ("Supplier On-time Delivery", "supplier_ontime_rate", "Percent of POs received on or before expected date.", "on-time POs / received POs", ["purchase_orders"], ["supplier"], ["supplier_lead_time"], "Supplier SLA proxy."),
    ("Purchase Order Variance", "purchase_order_variance", "Received quantity variance against ordered quantity.", "received_units − ordered_units", ["purchase_order_line_items"], ["supplier", "branch"], [], "Procurement variance metric."),
    ("Branch Performance Index", "branch_performance_index", "Composite of revenue, margin and returns.", "weighted(revenue, margin, return_rate)", ["sales_transactions", "returns"], ["branch"], ["revenue", "gross_margin", "return_rate"], "Executive branch comparison."),
    ("Category Performance Index", "category_performance_index", "Composite category sales and margin health.", "weighted(revenue, gross_margin)", ["sales_transactions", "products"], ["category"], ["revenue", "gross_margin"], "Category review signal."),
    ("Demand Volatility", "demand_volatility", "Variation in daily units sold.", "stdev(daily_units_sold)", ["sales_transactions"], ["product", "branch"], ["units_sold"], "Forecast confidence input."),
    ("Revenue Forecast", "revenue_forecast", "Trend-based revenue estimate.", "exponential_smoothing(revenue)", ["sales_transactions"], ["branch", "category"], ["revenue"], "Baseline forecast only."),
    ("Margin Forecast", "margin_forecast", "Trend-based margin estimate.", "exponential_smoothing(gross_margin)", ["sales_transactions"], ["branch", "category"], ["gross_margin"], "Baseline forecast only."),
]


def seed_database(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.scalar(select(Organization.id).limit(1)):
            return
        roles: dict[str, Role] = {}
        for name, description, permissions in ROLE_SPECS:
            role = Role(name=name, description=description, permissions=permissions)
            db.add(role)
            db.flush()
            roles[name] = role
        for code in ["dashboard:read", "ai:query", "investigation:manage", "approval:decide", "governance:manage", "export:data", "scenario:manage", "ingestion:manage", "report:manage"]:
            db.add(Permission(code=code, description=code.replace(":", " ").title()))

        organizations: list[Organization] = []
        for name, slug, _, _, _ in ORGS:
            org = Organization(name=name, slug=slug, is_demo=True)
            db.add(org)
            db.flush()
            organizations.append(org)

        # The named demo accounts all start in Northstar; the admin can switch to all three synthetic workspaces.
        admin = User(organization_id=organizations[0].id, role_id=roles["Organization Admin"].id, email="admin@opslens.demo", full_name="Amina Siddiqui", password_hash=hash_password("DemoPass123!"))
        finance = User(organization_id=organizations[0].id, role_id=roles["Finance Analyst"].id, email="finance@opslens.demo", full_name="Hamza Khan", password_hash=hash_password("DemoPass123!"))
        ops = User(organization_id=organizations[0].id, role_id=roles["Operations Manager"].id, email="ops@opslens.demo", full_name="Sara Malik", password_hash=hash_password("DemoPass123!"))
        branch_manager = User(organization_id=organizations[0].id, role_id=roles["Branch Manager"].id, email="branch.manager@opslens.demo", full_name="Bilal Ahmed", password_hash=hash_password("DemoPass123!"))
        viewer = User(organization_id=organizations[0].id, role_id=roles["Viewer"].id, email="viewer@opslens.demo", full_name="Noor Fatima", password_hash=hash_password("DemoPass123!"))
        supply = User(organization_id=organizations[0].id, role_id=roles["Supply Chain Manager"].id, email="supply@opslens.demo", full_name="Zain Raza", password_hash=hash_password("DemoPass123!"))
        db.add_all([admin, finance, ops, branch_manager, viewer, supply])
        db.flush()
        for org in organizations:
            db.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role_id=roles["Organization Admin"].id))
        for user in [finance, ops, branch_manager, viewer, supply]:
            db.add(OrganizationMembership(organization_id=organizations[0].id, user_id=user.id, role_id=user.role_id))

        org_payloads: list[dict[str, object]] = []
        for org, (_, _, prefix, product_count, sales_count) in zip(organizations, ORGS, strict=True):
            regions: dict[str, Region] = {}
            for name in ["North", "Central", "South"]:
                region = Region(organization_id=org.id, name=name)
                db.add(region)
                db.flush()
                regions[name] = region
            branches: list[Branch] = []
            for index, (name, region_name) in enumerate(BRANCHES):
                display = name if org == organizations[0] else f"{org.name.split()[0]} {name}"
                branch = Branch(organization_id=org.id, name=display, city=name.split()[0], region_id=regions[region_name].id)
                db.add(branch)
                db.flush()
                branches.append(branch)
            categories: list[ProductCategory] = []
            for name in CATEGORIES:
                category = ProductCategory(organization_id=org.id, name=name)
                db.add(category)
                db.flush()
                categories.append(category)
            suppliers: list[Supplier] = []
            for index, name in enumerate(SUPPLIERS):
                delay = 5 if index == 0 else (3 if index == 3 else 0)
                supplier = Supplier(organization_id=org.id, name=name, lead_time_days=7+index%6+delay, on_time_rate=0.71 if index == 0 else round(0.86+R.random()*.12, 2), risk_score=86 if index == 0 else (72 if index == 3 else round(18+R.random()*43, 1)))
                db.add(supplier)
                db.flush()
                suppliers.append(supplier)
            products: list[Product] = []
            for i in range(product_count):
                category = categories[i % len(categories)]
                supplier = suppliers[i % len(suppliers)]
                cost = round(R.uniform(250, 9000), 2)
                price = round(cost * R.uniform(1.18, 1.75), 2)
                if org == organizations[0] and i in (3, 57):
                    price = round(cost*.93, 2)
                product = Product(organization_id=org.id, category_id=category.id, supplier_id=supplier.id, sku=f"{prefix}-{i+1000:04d}", name=f"{category.name} {['Core','Plus','Essential','Pro'][i%4]} {i+1}", unit_cost=cost, list_price=price, reorder_point=R.randint(12, 48))
                db.add(product)
                db.flush()
                products.append(product)
            for product in products:
                for branch in branches:
                    low = org == organizations[0] and ((product.id % 37 == 0 and branch == branches[0]) or (product.id % 53 == 0 and branch == branches[1]))
                    units = R.randint(0, max(2, product.reorder_point//3)) if low else R.randint(product.reorder_point, product.reorder_point*12)
                    db.add(InventoryRecord(organization_id=org.id, branch_id=branch.id, product_id=product.id, available_units=units, reserved_units=R.randint(0,4), inventory_value=round(units*product.unit_cost, 2), snapshot_date=NOW))
            db.flush()
            sales: list[SalesTransaction] = []
            for i in range(sales_count):
                day = NOW-timedelta(days=R.randint(0,89), hours=R.randint(0,23))
                product = products[(i*7+i//11) % len(products)]
                branch = branches[(i*3+i//17) % len(branches)]
                qty = R.randint(1,5)
                discount = round(product.list_price*qty*(R.uniform(.06,.19) if (org == organizations[0] and product.category_id == categories[0].id and branch == branches[0] and day > NOW-timedelta(days=14)) else R.uniform(0,.07)), 2)
                sales.append(SalesTransaction(organization_id=org.id, branch_id=branch.id, product_id=product.id, quantity=qty, unit_price=product.list_price, unit_cost=product.unit_cost, discount_amount=discount, occurred_at=day))
            db.add_all(sales)
            db.flush()
            for index, sale in enumerate(sales[::37]):
                abnormal = org == organizations[0] and sale.branch_id == branches[0].id and index % 3 == 0
                amount = round((sale.unit_price*sale.quantity-sale.discount_amount)*(0.92 if abnormal else R.uniform(.5,.95)), 2)
                db.add(Return(organization_id=org.id, sale_id=sale.id, branch_id=sale.branch_id, reason="Damaged on arrival" if abnormal else "Customer return", amount=amount, occurred_at=sale.occurred_at+timedelta(days=R.randint(1,8))))
            for i in range(52):
                supplier = suppliers[i % len(suppliers)]
                branch = branches[i % len(branches)]
                expected = NOW + timedelta(days=R.randint(-9, 16))
                late = supplier == suppliers[0] and i % 2 == 0
                po = PurchaseOrder(organization_id=org.id, supplier_id=supplier.id, branch_id=branch.id, status="late" if late else ("open" if expected > NOW else "received"), expected_date=expected, received_date=None if expected > NOW else expected+timedelta(days=5 if late else 0))
                db.add(po)
                db.flush()
                for j in range(3):
                    product = products[(i*5+j) % len(products)]
                    db.add(PurchaseOrderLineItem(purchase_order_id=po.id, product_id=product.id, ordered_units=R.randint(40,180), received_units=0 if po.status != "received" else R.randint(35,170)))
            org_payloads.append({"org": org, "branches": branches, "products": products, "suppliers": suppliers})

        # Assign the branch manager only after the Northstar branch set exists.
        branch_manager.assigned_branch_id = org_payloads[0]["branches"][0].id  # type: ignore[index]

        for org_info in org_payloads:
            org = org_info["org"]  # type: ignore[assignment]
            branches = org_info["branches"]  # type: ignore[assignment]
            suppliers = org_info["suppliers"]  # type: ignore[assignment]
            is_primary = org == organizations[0]
            source_specs = [
                ("Retail warehouse", "PostgreSQL", "healthy", 0.2),
                ("Inventory snapshots", "CSV / warehouse", "delayed" if is_primary else "healthy", 14.0 if is_primary else 0.4),
                ("Sales POS feed", "ERP connector", "healthy", 0.15),
                ("Supplier PO feed", "ERP connector", "failing" if is_primary else "demo_connected", 17.0 if is_primary else 1.0),
                ("Shopify storefront", "Shopify demo connector", "demo_connected", 0.0),
            ]
            sources: list[DataSource] = []
            for name, typ, status, freshness in source_specs:
                source = DataSource(organization_id=org.id, name=name, source_type=typ, status=status, last_synced_at=NOW-timedelta(hours=freshness), last_success_at=NOW-timedelta(hours=freshness if status != "failing" else 20), schema_name="retail", freshness_hours=freshness, config={"mode": "demo_connector" if "connector" in typ.lower() else "synthetic"})
                db.add(source)
                db.flush()
                sources.append(source)
            for name, slug, description, formula, tables, dimensions, deps, strategy in METRICS:
                db.add(MetricDefinition(organization_id=org.id, name=name, slug=slug, description=description, formula=formula, source_tables=tables, dimensions=dimensions, valid_filters=["date_range", "branch", "category", "supplier"], time_grain="day", owner="Analytics Engineering", status="certified", data_quality_status="warning" if slug in {"stock_cover", "stockout_risk"} and is_primary else "healthy", last_calculated_at=NOW-timedelta(minutes=8), example_questions=[f"Show {name.lower()} by branch", f"Explain the change in {name.lower()}"], dependencies=deps, certified=True))
            rule1 = AlertRule(organization_id=org.id, name="Forecasted stock cover below 7 days", category="Inventory", severity="critical", metric_slug="stockout_risk", operator="<", threshold=7, scope_type="product", notification_targets=["in_app", "slack_mock"])
            rule2 = AlertRule(organization_id=org.id, name="Margin decline above 2 points", category="Margin", severity="high", metric_slug="gross_margin", operator="<", threshold=-2, scope_type="category", notification_targets=["in_app", "email_stub"])
            rule3 = AlertRule(organization_id=org.id, name="Data freshness exceeds SLA", category="Data quality", severity="high", metric_slug="freshness", operator=">", threshold=12, scope_type="data_source", notification_targets=["in_app", "webhook_mock"])
            db.add_all([rule1, rule2, rule3])
            db.flush()
            alerts = [
                (rule1, "critical", f"Stockout exposure in {branches[0].name}", "High-velocity SKUs are forecast to fall below reorder policy.", "branch", str(branches[0].id), {"days_cover": 3.2, "forecast_horizon": 14}),
                (rule2, "high", "Margin erosion in Consumer Electronics", "Discount rate outpaced price realization in the last 14 days.", "category", "Consumer Electronics", {"margin_delta": -2.1}),
                (rule3, "high", "Inventory snapshot freshness delayed", "Inventory source is 14 hours behind the expected refresh schedule.", "data_source", str(sources[1].id), {"freshness_hours": sources[1].freshness_hours}),
                (None, "medium", "Abnormal returns pattern", f"{branches[0].name} return behavior exceeds peer baseline.", "branch", str(branches[0].id), {"baseline_ratio": 2.4}),
            ]
            created_alerts: list[Alert] = []
            for rule, severity, title, description, entity_type, entity_id, evidence in alerts:
                item = Alert(organization_id=org.id, rule_id=rule.id if rule else None, severity=severity, title=title, description=description, entity_type=entity_type, entity_id=entity_id, confidence=.96 if severity == "critical" else .89, evidence=evidence)
                db.add(item)
                db.flush()
                created_alerts.append(item)
            high_risk_watchlist = Watchlist(organization_id=org.id, owner_id=admin.id, name="High-risk inventory", description="Critical stock cover and forecast exposure", criteria={"metric": "stockout_risk", "severity": ["critical", "high"]}, is_shared=True)
            supplier_watchlist = Watchlist(organization_id=org.id, owner_id=admin.id, name="Supplier performance", description="Lead-time and on-time-delivery watch", criteria={"metric": "supplier_ontime_rate"}, is_shared=True)
            quality_watchlist = Watchlist(organization_id=org.id, owner_id=admin.id, name="Data-quality risks", description="Freshness, mapping and import quality", criteria={"category": "data_quality"}, is_shared=True)
            db.add_all([high_risk_watchlist, supplier_watchlist, quality_watchlist])
            db.flush()
            db.add_all([
                WatchlistItem(organization_id=org.id, watchlist_id=high_risk_watchlist.id, entity_type="alert", entity_id=str(created_alerts[0].id), label=created_alerts[0].title, metadata_json={"reason": "stockout risk", "synthetic": True}),
                WatchlistItem(organization_id=org.id, watchlist_id=supplier_watchlist.id, entity_type="supplier", entity_id=str(suppliers[0].id), label=suppliers[0].name, metadata_json={"risk_score": suppliers[0].risk_score}),
                WatchlistItem(organization_id=org.id, watchlist_id=quality_watchlist.id, entity_type="data_source", entity_id=str(sources[1].id), label=sources[1].name, metadata_json={"freshness_hours": sources[1].freshness_hours}),
            ])
            primary_quality = [
                (sources[1], "Inventory snapshot delayed by 14 hours", "inventory_records", "high", 320, "Refresh the inventory snapshot before approving replenishment action.", ["stock_cover", "stockout_risk"]),
                (sources[3], "Supplier mapping missing for 16 products", "products", "critical", 16, "Map supplier references, re-run validation, and review affected stockout recommendations.", ["supplier_lead_time", "stockout_risk"]),
                (sources[0], "Duplicate transaction import detected", "sales_transactions", "warning", 7, "Deduplicate source transaction IDs before publishing financial metrics.", ["revenue", "gross_margin"]),
                (sources[0], "Negative unit price in supplier file", "sales_transactions", "critical", 1, "Quarantine the record and confirm the supplier import transformation.", ["revenue", "gross_margin"]),
                (sources[0], "Missing category mapping", "products", "warning", 9, "Complete product taxonomy mapping before category performance review.", ["category_performance_index"]),
            ]
            for source, issue, table, severity, count, remediation, related in primary_quality if is_primary else primary_quality[:2]:
                db.add(DataQualityIssue(organization_id=org.id, data_source_id=source.id, issue_type=issue, affected_table=table, severity=severity, affected_records=count, remediation=remediation, related_metrics=related, owner_id=admin.id))
            payload = forecast_payload(db, org.id, "revenue", 14)
            forecast = ForecastRun(organization_id=org.id, metric_slug="revenue_forecast", scope_type="organization", scope_id=str(org.id), horizon_days=14, method="exponential_smoothing_baseline", data_quality_status="warning" if is_primary else "healthy", payload=payload)
            db.add(forecast)
            db.flush()
            db.add_all([
                AnomalyRecord(organization_id=org.id, metric_slug="return_rate", severity="high", anomaly_type="return_spike", entity_type="branch", entity_id=str(branches[0].id), observed_value=7.8, baseline_value=3.2, z_score=3.1, explanation="Damaged-on-arrival returns are above the branch peer baseline.", evidence={"branch": branches[0].name, "ratio": 2.4}),
                AnomalyRecord(organization_id=org.id, metric_slug="gross_margin", severity="high", anomaly_type="margin_decline", entity_type="category", entity_id="Consumer Electronics", observed_value=21.1, baseline_value=28.0, z_score=-2.8, explanation="Discount intensity and landed-cost pressure created a category-level margin deviation.", evidence={"discount_rate": 14.2, "baseline": 7.1}),
                AnomalyRecord(organization_id=org.id, metric_slug="demand_volatility", severity="critical", anomaly_type="demand_spike", entity_type="product", entity_id="top-stockout-sku", observed_value=182, baseline_value=98, z_score=3.5, explanation="Seven-day demand velocity is above its trailing baseline while stock cover is declining.", evidence={"days_cover": 3.2, "supplier_delay_days": 5.2}),
            ])
            inv = Investigation(organization_id=org.id, title="Investigate Consumer Electronics margin erosion", category="margin", priority="high", severity="high", status="investigating", owner_id=finance.id if is_primary else admin.id, linked_alert_id=created_alerts[1].id, linked_forecast_id=forecast.id, due_date=NOW+timedelta(days=3), notes="Validate discount policy and supplier landed-cost variance.")
            db.add(inv)
            db.flush()
            approval = ApprovalRequest(organization_id=org.id, investigation_id=inv.id, requested_by_id=ops.id if is_primary else admin.id, status="pending", recommendation="Simulated inventory transfer of 40 units from Lahore to Islamabad.", policy_name="Inventory transfer above threshold", required_role="Operations Manager", expires_at=NOW+timedelta(days=2))
            db.add(approval)
            db.flush()
            db.add(ApprovalEvent(approval_request_id=approval.id, actor_id=ops.id if is_primary else admin.id, decision="submitted", note="Awaiting organization approval", step=1))
            db.add(Scenario(organization_id=org.id, owner_id=ops.id if is_primary else admin.id, name="Transfer 40 units to reduce Islamabad stockout risk", status="pending_approval", assumptions={"source_branch": branches[1].name, "target_branch": branches[0].name, "units": 40}, impact={"stockout_risk_delta": -4, "revenue_protection": 182000}, is_simulated=True))
            db.add(Report(organization_id=org.id, created_by_id=admin.id, name="Executive Operations Brief — Weekly", report_type="Executive Operations Brief", filters={"range": "last_30_days"}, content={"quality_notice": "Inventory source delayed by 14 hours"}, version=1))
            db.add(ScheduledReport(organization_id=org.id, report_type="Executive Operations Brief", name="Monday executive brief", cadence="weekly", next_run_at=NOW+timedelta(days=7), delivery_channel="in_app", is_simulated=True))
            job = ImportJob(organization_id=org.id, created_by_id=admin.id, source_type="csv", import_type="products", status="completed", file_name="supplier-products-demo.csv", records_total=48, records_valid=46, records_invalid=2, preview=[{"sku": f"{org.slug.upper()}-9001", "name": "Imported demo product", "unit_cost": 780}], validation_errors=[{"row": 7, "message": "Missing supplier reference"}], rollback_available=True)
            db.add(job)
            db.flush()
            for source_column, target_field in [("vendor_sku", "sku"), ("item_name", "name"), ("cost_pkr", "unit_cost"), ("supplier_code", "supplier")]:
                db.add(ImportMapping(import_job_id=job.id, source_column=source_column, target_field=target_field, transformation="trim / normalize" if target_field in {"sku", "name"} else "decimal cast", validation="required"))
            for source_kind, source_ref, target_kind, target_ref in [("CSV upload", job.file_name, "Import job", str(job.id)), ("Import job", str(job.id), "Metric", "inventory_value"), ("Metric", "stockout_risk", "Alert", str(created_alerts[0].id)), ("Alert", str(created_alerts[0].id), "Investigation", str(inv.id)), ("Investigation", str(inv.id), "Report", "Executive Operations Brief")]:
                db.add(LineageEvent(organization_id=org.id, source_kind=source_kind, source_ref=source_ref, target_kind=target_kind, target_ref=target_ref, metadata_json={"synthetic": True}))
            db.add(ApiKey(organization_id=org.id, user_id=admin.id, label="Demo reporting integration", prefix="ops_live_", scopes=["reports:read", "metrics:read"], expires_at=NOW+timedelta(days=90), last_used_at=NOW-timedelta(hours=2)))
            db.add(Notification(organization_id=org.id, user_id=admin.id, title="Critical stockout review", body="A simulated inventory transfer is awaiting approval.", type="critical"))
            db.add(WebhookDeliveryLog(organization_id=org.id, event_type="alert.created", destination="slack-compatible://mock", status="simulated", attempts=0, payload={"alert": created_alerts[0].title}))
            for action, resource in [("workspace.seed", f"organization:{org.id}"), ("alert.created", f"alert:{created_alerts[0].id}"), ("data_quality.issue_created", "inventory_records"), ("scenario.created", "demo-scenario"), ("report.generated", "Executive Operations Brief")]:
                db.add(AuditEvent(organization_id=org.id, actor_email=admin.email, action=action, resource_type="workspace", resource_id=resource, request_id="seed", metadata_json={"demo": True, "synthetic": True}))
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed_database(args.reset)
    print("OpsLens Phase 3 synthetic demo workspace is ready.")


if __name__ == "__main__":
    main()
