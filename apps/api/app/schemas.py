from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class WorkspaceSwitch(BaseModel):
    organization_id: int


class QuestionRequest(BaseModel):
    question: str = Field(min_length=4, max_length=2000)
    mode: Literal["Executive Brief", "Analyst View", "Data Explorer", "Investigation Mode", "Forecast Explanation", "Data Quality Explanation"] = "Executive Brief"


class ConversationCreate(BaseModel):
    title: str = Field(default="New governed analysis", max_length=180)
    mode: str = "Executive Brief"


class InvestigationCreate(BaseModel):
    title: str
    priority: str = "medium"
    severity: str = "medium"
    category: str = "operations"
    notes: str = ""
    linked_execution_id: int | None = None
    linked_alert_id: int | None = None
    linked_quality_issue_id: int | None = None
    due_date: datetime | None = None


class InvestigationUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    notes: str | None = None
    resolution_summary: str | None = None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    internal: bool = True


class ApprovalDecision(BaseModel):
    note: str = ""


class AlertStateUpdate(BaseModel):
    status: Literal["open", "acknowledged", "snoozed", "resolved"]
    owner_id: int | None = None


class DataQualityStateUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
    owner_id: int | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=4, max_length=180)
    adjustments: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: dict[str, Any] = Field(default_factory=dict)


class ReportCreate(BaseModel):
    name: str = Field(min_length=4, max_length=180)
    report_type: str = "Executive Operations Brief"
    filters: dict[str, Any] = Field(default_factory=dict)


class ScheduleCreate(BaseModel):
    name: str
    report_type: str
    cadence: Literal["daily", "weekly", "monthly"] = "weekly"
    delivery_channel: Literal["in_app", "email_stub", "slack_mock", "webhook_mock"] = "in_app"


class ImportPreviewRequest(BaseModel):
    import_type: Literal["products", "sales", "inventory", "suppliers", "purchase_orders", "returns", "branches"]
    file_name: str = "sample.csv"
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ApiKeyCreate(BaseModel):
    label: str
    scopes: list[str] = Field(default_factory=lambda: ["reports:read"])
    expires_in_days: int = Field(default=90, ge=1, le=365)

class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=4, max_length=180)
    category: str = "inventory"
    severity: Literal["info", "warning", "high", "critical"] = "warning"
    metric_slug: str = "stockout_risk"
    operator: Literal["<", ">", "<=", ">=", "="] = "<"
    threshold: float = 7
    scope_type: str = "organization"
    notification_targets: list[str] = Field(default_factory=lambda: ["in_app"])


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = ""
    criteria: dict[str, Any] = Field(default_factory=dict)
    is_shared: bool = True


class WatchlistItemCreate(BaseModel):
    entity_type: str
    entity_id: str
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScenarioUpdate(BaseModel):
    name: str | None = None
    status: Literal["draft", "in_review", "approved", "rejected", "expired", "archived", "simulated_execution_recorded", "pending_approval"] | None = None
    assumptions: dict[str, Any] | None = None
    adjustments: list[dict[str, Any]] | None = None


class RetentionConfigUpdate(BaseModel):
    audit_retention_days: int = Field(default=365, ge=30, le=3650)
    report_retention_days: int = Field(default=730, ge=30, le=3650)
    import_retention_days: int = Field(default=365, ge=30, le=3650)
    legal_hold_enabled: bool = False


class JsonImportRequest(BaseModel):
    import_type: Literal["products", "sales", "inventory", "suppliers", "purchase_orders", "returns", "branches"]
    file_name: str = "payload.json"
    rows: list[dict[str, Any]]


class IdempotentWriteResponse(BaseModel):
    id: int
    status: str
    audit_event: str | None = None
