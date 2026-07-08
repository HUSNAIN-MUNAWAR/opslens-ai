from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    """Return a naive UTC value for the current DateTime columns without deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Organization(Base, Timestamped):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="active")


class Role(Base, Timestamped):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(240), default="")
    permissions: Mapped[list] = mapped_column(JSON, default=list)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(96), unique=True)
    description: Mapped[str] = mapped_column(String(240))


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    assigned_branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OrganizationMembership(Base, Timestamped):
    __tablename__ = "organization_memberships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(24), default="active")
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_region_org_name"),)


class Branch(Base, Timestamped):
    __tablename__ = "branches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="active")
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_branch_org_name"),)


class ProductCategory(Base):
    __tablename__ = "product_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(96))
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_category_org_name"),)


class Supplier(Base, Timestamped):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    on_time_rate: Mapped[float] = mapped_column(Float, default=0.95)
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_supplier_org_name"),)


class Product(Base, Timestamped):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("product_categories.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    sku: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(180))
    unit_cost: Mapped[float] = mapped_column(Float)
    list_price: Mapped[float] = mapped_column(Float)
    reorder_point: Mapped[int] = mapped_column(Integer, default=20)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("organization_id", "sku", name="uq_product_org_sku"),)


class InventoryRecord(Base, Timestamped):
    __tablename__ = "inventory_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    available_units: Mapped[int] = mapped_column(Integer)
    reserved_units: Mapped[int] = mapped_column(Integer, default=0)
    inventory_value: Mapped[float] = mapped_column(Float)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("organization_id", "branch_id", "product_id", name="uq_inventory_org_branch_product"),)


class SalesTransaction(Base):
    __tablename__ = "sales_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[float] = mapped_column(Float)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Return(Base):
    __tablename__ = "returns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales_transactions.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    reason: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class PurchaseOrder(Base, Timestamped):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    status: Mapped[str] = mapped_column(String(30), default="open")
    expected_date: Mapped[datetime] = mapped_column(DateTime)
    received_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PurchaseOrderLineItem(Base):
    __tablename__ = "purchase_order_line_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    ordered_units: Mapped[int] = mapped_column(Integer)
    received_units: Mapped[int] = mapped_column(Integer, default=0)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    movement_type: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


class AlertRule(Base, Timestamped):
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    metric_slug: Mapped[str] = mapped_column(String(96))
    operator: Mapped[str] = mapped_column(String(12), default="<")
    threshold: Mapped[float] = mapped_column(Float, default=0)
    scope_type: Mapped[str] = mapped_column(String(32), default="organization")
    status: Mapped[str] = mapped_column(String(24), default="active")
    notification_targets: Mapped[list] = mapped_column(JSON, default=list)


class Alert(Base, Timestamped):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open")
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class Watchlist(Base, Timestamped):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)




class WatchlistItem(Base, Timestamped):
    __tablename__ = "watchlist_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="active")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("watchlist_id", "entity_type", "entity_id", name="uq_watchlist_entity"),)


class DataQualityIssue(Base, Timestamped):
    __tablename__ = "data_quality_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(96))
    affected_table: Mapped[str] = mapped_column(String(96))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="open")
    affected_records: Mapped[int] = mapped_column(Integer, default=0)
    remediation: Mapped[str] = mapped_column(Text)
    related_metrics: Mapped[list] = mapped_column(JSON, default=list)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ForecastRun(Base, Timestamped):
    __tablename__ = "forecast_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    metric_slug: Mapped[str] = mapped_column(String(96))
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[str] = mapped_column(String(96))
    horizon_days: Mapped[int] = mapped_column(Integer, default=14)
    method: Mapped[str] = mapped_column(String(96), default="exponential_smoothing_baseline")
    data_quality_status: Mapped[str] = mapped_column(String(24), default="healthy")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AnomalyRecord(Base, Timestamped):
    __tablename__ = "anomaly_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    metric_slug: Mapped[str] = mapped_column(String(96))
    severity: Mapped[str] = mapped_column(String(20))
    anomaly_type: Mapped[str] = mapped_column(String(96))
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str] = mapped_column(String(96))
    observed_value: Mapped[float] = mapped_column(Float)
    baseline_value: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class Scenario(Base, Timestamped):
    __tablename__ = "scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(24), default="draft")
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict)
    impact: Mapped[dict] = mapped_column(JSON, default=dict)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)


class ScenarioAdjustment(Base, Timestamped):
    __tablename__ = "scenario_adjustments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"), index=True)
    adjustment_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Investigation(Base, Timestamped):
    __tablename__ = "investigations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(64), default="operations")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    linked_execution_id: Mapped[int | None] = mapped_column(ForeignKey("ai_query_executions.id"), nullable=True)
    linked_alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True)
    linked_quality_issue_id: Mapped[int | None] = mapped_column(ForeignKey("data_quality_issues.id"), nullable=True)
    linked_forecast_id: Mapped[int | None] = mapped_column(ForeignKey("forecast_runs.id"), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    resolution_summary: Mapped[str] = mapped_column(Text, default="")


class InvestigationComment(Base, Timestamped):
    __tablename__ = "investigation_comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalRequest(Base, Timestamped):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    investigation_id: Mapped[int | None] = mapped_column(ForeignKey("investigations.id"), nullable=True)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("scenarios.id"), nullable=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    recommendation: Mapped[str] = mapped_column(Text)
    policy_name: Mapped[str] = mapped_column(String(120), default="Standard operational review")
    required_role: Mapped[str] = mapped_column(String(64), default="Organization Admin")
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalEvent(Base, Timestamped):
    __tablename__ = "approval_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_request_id: Mapped[int] = mapped_column(ForeignKey("approval_requests.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text, default="")
    step: Mapped[int] = mapped_column(Integer, default=1)


class AIConversation(Base, Timestamped):
    __tablename__ = "ai_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(180))
    mode: Mapped[str] = mapped_column(String(40), default="Executive Brief")


class AIMessage(Base, Timestamped):
    __tablename__ = "ai_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)


class AIQueryExecution(Base, Timestamped):
    __tablename__ = "ai_query_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"))
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_names: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    answer: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    mode: Mapped[str] = mapped_column(String(40), default="Executive Brief")


class QueryPlan(Base, Timestamped):
    __tablename__ = "query_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    execution_id: Mapped[int | None] = mapped_column(ForeignKey("ai_query_executions.id"), nullable=True)
    user_question: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(96))
    selected_metrics: Mapped[list] = mapped_column(JSON, default=list)
    allowed_tables: Mapped[list] = mapped_column(JSON, default=list)
    dimensions: Mapped[list] = mapped_column(JSON, default=list)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    date_range: Mapped[dict] = mapped_column(JSON, default=dict)
    aggregation: Mapped[str] = mapped_column(String(64), default="")
    ranking: Mapped[str] = mapped_column(String(64), default="")
    row_limit: Mapped[int] = mapped_column(Integer, default=100)
    requires_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    explanation_strategy: Mapped[str] = mapped_column(String(160), default="grounded_summary")


class SQLValidationResult(Base, Timestamped):
    __tablename__ = "sql_validation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("ai_query_executions.id"))
    is_valid: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    tables: Mapped[list] = mapped_column(JSON, default=list)
    row_limit: Mapped[int] = mapped_column(Integer, default=500)
    complexity_score: Mapped[int] = mapped_column(Integer, default=0)
    parser: Mapped[str] = mapped_column(String(32), default="sqlglot")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_email: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(96), index=True)
    resource_type: Mapped[str] = mapped_column(String(96))
    resource_id: Mapped[str] = mapped_column(String(96))
    request_id: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DataSource(Base, Timestamped):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    schema_name: Mapped[str] = mapped_column(String(80), default="public")
    freshness_hours: Mapped[float] = mapped_column(Float, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class MetricDefinition(Base, Timestamped):
    __tablename__ = "metric_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(96))
    slug: Mapped[str] = mapped_column(String(96), index=True)
    description: Mapped[str] = mapped_column(Text)
    formula: Mapped[str] = mapped_column(Text)
    source_tables: Mapped[list] = mapped_column(JSON, default=list)
    dimensions: Mapped[list] = mapped_column(JSON, default=list)
    valid_filters: Mapped[list] = mapped_column(JSON, default=list)
    time_grain: Mapped[str] = mapped_column(String(32), default="day")
    owner: Mapped[str] = mapped_column(String(96), default="Analytics")
    status: Mapped[str] = mapped_column(String(24), default="certified")
    data_quality_status: Mapped[str] = mapped_column(String(24), default="healthy")
    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    example_questions: Mapped[list] = mapped_column(JSON, default=list)
    access_restrictions: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    certified: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_metric_org_slug"),)


class ApiKey(Base, Timestamped):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Report(Base, Timestamped):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(180))
    report_type: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(32), default="generated")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ScheduledReport(Base, Timestamped):
    __tablename__ = "scheduled_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(96))
    name: Mapped[str] = mapped_column(String(180))
    cadence: Mapped[str] = mapped_column(String(32), default="weekly")
    next_run_at: Mapped[datetime] = mapped_column(DateTime)
    delivery_channel: Mapped[str] = mapped_column(String(40), default="in_app")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ImportJob(Base, Timestamped):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[str] = mapped_column(String(64))
    import_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="preview")
    file_name: Mapped[str] = mapped_column(String(180), default="")
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    records_valid: Mapped[int] = mapped_column(Integer, default=0)
    records_invalid: Mapped[int] = mapped_column(Integer, default=0)
    preview: Mapped[list] = mapped_column(JSON, default=list)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    rollback_available: Mapped[bool] = mapped_column(Boolean, default=True)


class ImportMapping(Base, Timestamped):
    __tablename__ = "import_mappings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    source_column: Mapped[str] = mapped_column(String(120))
    target_field: Mapped[str] = mapped_column(String(120))
    transformation: Mapped[str] = mapped_column(String(180), default="identity")
    validation: Mapped[str] = mapped_column(String(180), default="required")


class LineageEvent(Base, Timestamped):
    __tablename__ = "lineage_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    source_kind: Mapped[str] = mapped_column(String(80))
    source_ref: Mapped[str] = mapped_column(String(120))
    target_kind: Mapped[str] = mapped_column(String(80))
    target_ref: Mapped[str] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Notification(Base, Timestamped):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(40), default="info")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WebhookDeliveryLog(Base, Timestamped):
    __tablename__ = "webhook_delivery_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(96))
    destination: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(32), default="simulated")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
