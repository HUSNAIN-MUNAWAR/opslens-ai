from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.models import *
from app.schemas import *
from app.security import active_organization, current_role, current_user, issue_api_key_value, issue_token, require_api_key_scope, verify_password
from app.seed import NOW, seed_database
from app.services import (
    alerts, alerts_and_watchlists, anomaly_payload, branch_comparison, category_performance,
    data_quality_overview, evaluate_alert_rules, forecast_payload, global_search, import_preview, metric_catalog,
    metric_graph, operation_console, overview, question_plan, revenue_trend, scenario_impact,
    stockout_risks, supplier_risk,
)
from app.sql_guard import validate_sql

@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_startup()
    Base.metadata.create_all(engine)
    seed_database()
    yield


app = FastAPI(
    title="OpsLens AI API",
    version="0.3.0",
    description="Multi-tenant governed decision-intelligence API. Synthetic demo workspace; all execution paths are read-only or explicitly simulated.",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Authentication"}, {"name": "Workspaces"}, {"name": "Dashboard"},
        {"name": "AI Operations"}, {"name": "Investigations"}, {"name": "Inventory"},
        {"name": "Data Quality"}, {"name": "Alerts"}, {"name": "Forecasting"},
        {"name": "Decision Workbench"}, {"name": "Reporting"}, {"name": "Ingestion"},
        {"name": "Governance"}, {"name": "Security"}, {"name": "Programmatic API"}, {"name": "Operations Console"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rate_buckets: dict[str, tuple[int, int]] = {}


@app.middleware("http")
async def request_controls(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    key = request.client.host if request.client else "local"
    minute = int(time.time() // 60)
    bucket_minute, count = _rate_buckets.get(key, (minute, 0))
    if bucket_minute != minute:
        bucket_minute, count = minute, 0
    count += 1
    _rate_buckets[key] = (bucket_minute, count)
    if count > settings.request_rate_limit:
        return Response(status_code=429, content='{"detail":"Rate limit exceeded"}', media_type="application/json", headers={"X-Request-ID": request_id})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "public, max-age=300"
    return response


def _actor(user: User, db: Session) -> User:
    # Services use this transient role label only for presentation/scoped branch queries.
    setattr(user, "role_name", current_role(user, db).name)
    return user


def _audit(db: Session, org_id: int, user: User, action: str, resource_type: str, resource_id: str, metadata: dict[str, Any] | None = None, request_id: str = "") -> None:
    db.add(AuditEvent(organization_id=org_id, actor_email=user.email, action=action, resource_type=resource_type, resource_id=resource_id, request_id=request_id, metadata_json=metadata or {}))


def _get_scoped(db: Session, model: Any, entity_id: int, org_id: int, label: str) -> Any:
    entity = db.get(model, entity_id)
    if not entity or getattr(entity, "organization_id", None) != org_id:
        raise HTTPException(404, f"{label} not found")
    return entity


def _require_workspace_role(user: User, db: Session, allowed: set[str]) -> None:
    role = current_role(user, db)
    if role.name not in allowed and "*" not in (role.permissions or []):
        raise HTTPException(403, "This role cannot perform the requested action")


@app.get("/health", tags=["Operations Console"])
def health() -> dict[str, Any]:
    return {"status": "healthy", "service": "opslens-api", "demo_mode": settings.demo_mode, "version": "0.3.0", "environment": settings.environment}


# Authentication and organization boundary
@app.post("/api/v1/auth/login", response_model=TokenPair, tags=["Authentication"])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid demo credentials")
    role = current_role(user, db)
    _audit(db, user.organization_id, user, "auth.login", "session", str(user.id), {"demo": settings.demo_mode}, request.headers.get("X-Request-ID", ""))
    db.commit()
    access = issue_token(user)
    return {"access_token": access, "refresh_token": issue_token(user, minutes=60*24*7), "user": {"id": user.id, "email": user.email, "name": user.full_name, "role": role.name, "organization_id": user.organization_id}}


@app.post("/api/v1/auth/refresh", tags=["Authentication"])
def refresh(user: User = Depends(current_user)) -> dict[str, str]:
    return {"access_token": issue_token(user)}


@app.post("/api/v1/auth/logout", tags=["Authentication"])
def logout(user: User = Depends(current_user)) -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/v1/auth/me", tags=["Authentication"])
def me(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    role = current_role(user, db)
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": role.name, "organization": {"id": org.id, "name": org.name, "slug": org.slug}, "assigned_branch_id": user.assigned_branch_id}


@app.get("/api/v1/workspaces", tags=["Workspaces"])
def workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(OrganizationMembership, Organization, Role).join(Organization, Organization.id == OrganizationMembership.organization_id).join(Role, Role.id == OrganizationMembership.role_id).where(OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active")).all()
    return [{"id": org.id, "name": org.name, "slug": org.slug, "role": role.name, "is_demo": org.is_demo} for _, org, role in rows]


@app.post("/api/v1/workspaces/switch", tags=["Workspaces"])
def switch_workspace(payload: WorkspaceSwitch, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    membership = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id, OrganizationMembership.organization_id == payload.organization_id, OrganizationMembership.status == "active"))
    if not membership:
        raise HTTPException(403, "Workspace access denied")
    org = db.get(Organization, payload.organization_id)
    if not org:
        raise HTTPException(404, "Workspace not found")
    _audit(db, org.id, user, "workspace.switch", "organization", str(org.id), {}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"access_token": issue_token(user, organization_id=org.id), "organization": {"id": org.id, "name": org.name, "slug": org.slug}}


# Dashboard
@app.get("/api/v1/dashboard/overview", tags=["Dashboard"])
def dashboard_overview(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return overview(db, org.id, _actor(user, db))


@app.get("/api/v1/dashboard/revenue-trends", tags=["Dashboard"])
def dashboard_revenue(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return revenue_trend(db, org.id, _actor(user, db))


@app.get("/api/v1/dashboard/alerts", tags=["Dashboard"])
def dashboard_alerts(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return alerts(db, org.id)


@app.get("/api/v1/dashboard/branch-comparison", tags=["Dashboard"])
def dashboard_branches(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return branch_comparison(db, org.id, _actor(user, db))


@app.get("/api/v1/dashboard/category-performance", tags=["Dashboard"])
def dashboard_categories(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return category_performance(db, org.id)


# Governed AI v2
@app.post("/api/v1/ai/conversations", tags=["AI Operations"])
def create_conversation(payload: ConversationCreate, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    convo = AIConversation(organization_id=org.id, user_id=user.id, title=payload.title, mode=payload.mode)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return {"id": convo.id, "title": convo.title, "mode": convo.mode, "created_at": convo.created_at}


@app.get("/api/v1/ai/conversations", tags=["AI Operations"])
def conversations(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(AIConversation).where(AIConversation.user_id == user.id, AIConversation.organization_id == org.id).order_by(desc(AIConversation.created_at))).all()
    return [{"id": row.id, "title": row.title, "mode": row.mode, "created_at": row.created_at} for row in rows]


@app.post("/api/v1/ai/conversations/{conversation_id}/questions", tags=["AI Operations"])
def ask(conversation_id: int, payload: QuestionRequest, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    convo = _get_scoped(db, AIConversation, conversation_id, org.id, "Conversation")
    if convo.user_id != user.id:
        raise HTTPException(403, "Conversation access denied")
    plan = question_plan(payload.question, org.id)
    trace = [
        {"step": "Understanding question", "state": "complete", "detail": "Classified against approved operations intents."},
        {"step": "Selecting approved metrics", "state": "complete" if plan["metrics"] else "skipped", "detail": ", ".join(plan["metrics"]) or "No certified metric matched."},
        {"step": "Preparing governed query plan", "state": "complete" if plan["sql"] else "blocked", "detail": "Tenant-bound semantic query plan created." if plan["sql"] else "Question is outside the certified demo capability."},
    ]
    plan_record = QueryPlan(organization_id=org.id, user_question=payload.question, intent=plan["intent"], selected_metrics=plan["metrics"], allowed_tables=plan["allowed_tables"], dimensions=plan["dimensions"], filters=plan["filters"], date_range=plan["date_range"], aggregation=plan["aggregation"], ranking=plan["ranking"], row_limit=plan["row_limit"], requires_followup=plan["requires_followup"], confidence=plan["confidence"], explanation_strategy=plan["explanation_strategy"])
    db.add(plan_record)
    db.flush()
    if not plan["sql"]:
        answer = "I cannot verify that question because this workspace does not currently include a certified metric or approved source for it. I can analyze stockout risk, returns, margin, suppliers, branches, baseline forecasts, and data-quality issues."
        execution = AIQueryExecution(organization_id=org.id, conversation_id=convo.id, question=payload.question, status="blocked", sql=None, metric_names=[], evidence={"reason": "unsupported_question", "safe_alternatives": ["Which products are likely to stock out within 14 days?", "Why did gross margin decline?", "Which data source is delayed?"]}, answer=answer, confidence=.12, mode=payload.mode)
        db.add(execution)
        db.add(AIMessage(conversation_id=convo.id, role="user", content=payload.question))
        db.add(AIMessage(conversation_id=convo.id, role="assistant", content=answer))
        _audit(db, org.id, user, "ai.query_blocked", "ai_execution", "pending", {"reason": "unsupported_question"}, request.headers.get("X-Request-ID", ""))
        db.commit()
        return {"execution_id": execution.id, "status": "blocked", "answer": answer, "confidence": .12, "trace": trace + [{"step": "AST validation", "state": "blocked", "detail": "No SQL generated for unsupported question."}], "query_plan": {"intent": plan["intent"], "requires_followup": True}, "warnings": ["No certified query plan available."], "evidence": execution.evidence, "sql": None, "validation": None}
    report = validate_sql(plan["sql"], require_tenant_scope=True)
    trace.append({"step": "AST validation", "state": "complete" if report.valid else "blocked", "detail": report.reasons[-1]})
    if not report.valid:
        execution = AIQueryExecution(organization_id=org.id, conversation_id=convo.id, question=payload.question, status="blocked", sql=plan["sql"], metric_names=plan["metrics"], evidence={"blocked_reasons": report.reasons}, answer="The generated query did not pass OpsLens SQL governance and was not executed.", confidence=.0, mode=payload.mode)
        db.add(execution)
        db.flush()
        plan_record.execution_id = execution.id
        db.add(SQLValidationResult(execution_id=execution.id, is_valid=False, reasons=report.reasons, tables=report.tables, row_limit=report.row_limit, complexity_score=report.complexity_score))
        _audit(db, org.id, user, "sql.validation_blocked", "ai_execution", str(execution.id), {"reasons": report.reasons}, request.headers.get("X-Request-ID", ""))
        db.commit()
        raise HTTPException(400, {"code": "SQL_VALIDATION_FAILED", "reasons": report.reasons})
    actor = _actor(user, db)
    data: Any
    if plan["kind"] == "stockout":
        data = stockout_risks(db, org.id, actor)
        answer = f"{len(data)} branch-SKU combinations are below their reorder policy. The most urgent exposure is concentrated in Islamabad and Lahore; validate open supplier POs before submitting a replenishment action for approval."
        tables = ["inventory_records", "products", "branches", "suppliers"]
    elif plan["kind"] == "returns":
        data = branch_comparison(db, org.id, actor)
        answer = "The returns signal is highest in Islamabad relative to its peer baseline. The evidence indicates a concentrated damaged-on-arrival pattern rather than a workspace-wide returns increase."
        tables = ["returns", "branches"]
    elif plan["kind"] == "margin":
        data = category_performance(db, org.id)
        answer = "Gross margin pressure is concentrated in Consumer Electronics and Home Appliances. The available evidence points to elevated discounts and landed-cost pressure, not a broad-based revenue decline."
        tables = ["sales_transactions", "products", "product_categories"]
    elif plan["kind"] == "supplier":
        data = supplier_risk(db, org.id)
        answer = "NorthStar Imports has the highest delivery risk, followed by Meridian Supply. Their lead-time and on-time-delivery signals justify a supply-chain escalation before approving replenishment decisions."
        tables = ["suppliers"]
    elif plan["kind"] == "forecast":
        data = forecast_payload(db, org.id, "revenue", 14)
        answer = "The baseline forecast is directionally positive, but it assumes current demand and supplier conditions persist. The confidence range is intentionally visible because this is a transparent decision-support estimate."
        tables = ["sales_transactions"]
    elif plan["kind"] == "data_quality":
        data = data_quality_overview(db, org.id)
        answer = "The workspace has active data-quality issues affecting inventory freshness, supplier mapping, and a small set of financial records. Governed answers carry these notices when their source tables are affected."
        tables = ["data_quality_issues", "data_sources"]
    else:
        data = branch_comparison(db, org.id, actor)
        answer = "Islamabad and Lahore should be compared through revenue, margin, and returns together. Islamabad has the strongest risk signal due to returns and inventory cover despite healthy demand."
        tables = ["sales_transactions", "branches"]
    notices = []
    for table in tables:
        notices.extend([n for n in data_quality_overview(db, org.id)["issues"] if n["affected_table"] == table and n["status"] != "resolved"])
    evidence = {"rows": data, "sources": report.tables, "synthetic": True, "execution_mode": "deterministic_governed_template", "data_quality_notices": notices[:5]}
    execution = AIQueryExecution(organization_id=org.id, conversation_id=convo.id, question=payload.question, status="completed", sql=plan["sql"], metric_names=plan["metrics"], evidence=evidence, answer=answer, confidence=.91 if not notices else .78, mode=payload.mode)
    db.add(execution)
    db.flush()
    plan_record.execution_id = execution.id
    db.add(SQLValidationResult(execution_id=execution.id, is_valid=True, reasons=report.reasons, tables=report.tables, row_limit=report.row_limit, complexity_score=report.complexity_score))
    db.add(AIMessage(conversation_id=convo.id, role="user", content=payload.question))
    db.add(AIMessage(conversation_id=convo.id, role="assistant", content=answer))
    _audit(db, org.id, user, "ai.query", "ai_execution", str(execution.id), {"safe_sql": True, "mode": payload.mode, "quality_warning_count": len(notices)}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"execution_id": execution.id, "status": "completed", "answer": answer, "confidence": execution.confidence, "trace": trace + [{"step": "Retrieving evidence", "state": "complete", "detail": f"Retrieved {len(data) if isinstance(data, list) else 1} governed evidence set(s) with a {settings.sql_timeout_ms}ms execution budget."}, {"step": "Generating grounded answer", "state": "complete", "detail": "Narrative is constrained to certified metric results and evidence."}], "query_plan": {key: plan[key] for key in ["intent", "metrics", "allowed_tables", "dimensions", "filters", "date_range", "aggregation", "ranking", "row_limit", "requires_followup", "confidence", "explanation_strategy"]}, "warnings": ["Synthetic demo data: review evidence and obtain human approval before operational action."] + (["Data-quality warning: one or more source tables have active quality issues."] if notices else []), "evidence": evidence, "sql": plan["sql"], "validation": {"valid": report.valid, "reasons": report.reasons, "tables": report.tables, "row_limit": report.row_limit, "complexity_score": report.complexity_score, "parser": report.parser}}


@app.get("/api/v1/ai/executions/{execution_id}", tags=["AI Operations"])
def execution(execution_id: int, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = _get_scoped(db, AIQueryExecution, execution_id, org.id, "AI execution")
    plan = db.scalar(select(QueryPlan).where(QueryPlan.execution_id == item.id))
    return {"id": item.id, "status": item.status, "question": item.question, "sql": item.sql, "answer": item.answer, "confidence": item.confidence, "evidence": item.evidence, "metrics": item.metric_names, "mode": item.mode, "query_plan": {"intent": plan.intent, "selected_metrics": plan.selected_metrics, "allowed_tables": plan.allowed_tables, "filters": plan.filters, "row_limit": plan.row_limit} if plan else None}


@app.get("/api/v1/ai/executions/{execution_id}/evidence", tags=["AI Operations"])
def execution_evidence(execution_id: int, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = _get_scoped(db, AIQueryExecution, execution_id, org.id, "AI execution")
    return item.evidence


@app.get("/api/v1/ai/executions/{execution_id}/sql", tags=["AI Operations"])
def execution_sql(execution_id: int, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = _get_scoped(db, AIQueryExecution, execution_id, org.id, "AI execution")
    validation = db.scalar(select(SQLValidationResult).where(SQLValidationResult.execution_id == item.id))
    return {"sql": item.sql, "validation": {"valid": validation.is_valid, "reasons": validation.reasons, "tables": validation.tables, "row_limit": validation.row_limit, "complexity_score": validation.complexity_score, "parser": validation.parser} if validation else None}


# Investigations and approvals
# Policies are explicit and executable. They govern a recommendation only; no policy here writes to an ERP.
APPROVAL_POLICY_STEPS: dict[str, list[str]] = {
    "Standard operational review": ["Organization Admin"],
    "Inventory transfer above threshold": ["Operations Manager", "Organization Admin"],
    "Margin-impacting discount simulation": ["Finance Analyst", "Organization Admin"],
    "Scenario recommendation review": ["Operations Manager", "Organization Admin"],
}


def _approval_steps(approval: ApprovalRequest) -> list[str]:
    return APPROVAL_POLICY_STEPS.get(approval.policy_name, [approval.required_role or "Organization Admin"])


def _advance_approval(approval: ApprovalRequest, actor: User, db: Session, note: str) -> dict[str, Any]:
    steps = _approval_steps(approval)
    role = current_role(actor, db).name
    required = steps[min(approval.current_step - 1, len(steps) - 1)]
    if role != required and role != "Platform Admin":
        raise HTTPException(403, f"Approval step {approval.current_step} requires {required}")
    db.add(ApprovalEvent(approval_request_id=approval.id, actor_id=actor.id, decision="approved", note=note, step=approval.current_step))
    if approval.current_step < len(steps):
        approval.current_step += 1
        approval.required_role = steps[approval.current_step - 1]
        approval.status = "in_review"
        return {"status": "in_review", "complete": False, "next_step": approval.current_step, "required_role": approval.required_role}
    approval.status = "approved"
    if approval.investigation_id:
        inv = db.get(Investigation, approval.investigation_id)
        if inv:
            inv.status = "approved"
    if approval.scenario_id:
        scenario = db.get(Scenario, approval.scenario_id)
        if scenario:
            scenario.status = "approved"
    return {"status": "approved", "complete": True, "next_step": None, "required_role": None}


@app.get("/api/v1/investigations", tags=["Investigations"])
def list_investigations(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Investigation).where(Investigation.organization_id == org.id).order_by(desc(Investigation.created_at))).all()
    return [{"id": row.id, "title": row.title, "category": row.category, "priority": row.priority, "severity": row.severity, "status": row.status, "owner_id": row.owner_id, "linked_alert_id": row.linked_alert_id, "linked_quality_issue_id": row.linked_quality_issue_id, "due_date": row.due_date, "notes": row.notes, "created_at": row.created_at} for row in rows]


@app.get("/api/v1/investigations/{investigation_id}", tags=["Investigations"])
def investigation_detail(investigation_id: int, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    inv = _get_scoped(db, Investigation, investigation_id, org.id, "Investigation")
    comments = db.scalars(select(InvestigationComment).where(InvestigationComment.investigation_id == inv.id).order_by(InvestigationComment.created_at)).all()
    approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.investigation_id == inv.id, ApprovalRequest.organization_id == org.id).order_by(desc(ApprovalRequest.created_at)))
    events = db.scalars(select(ApprovalEvent).where(ApprovalEvent.approval_request_id == approval.id).order_by(ApprovalEvent.created_at)).all() if approval else []
    return {"id": inv.id, "title": inv.title, "category": inv.category, "priority": inv.priority, "severity": inv.severity, "status": inv.status, "owner_id": inv.owner_id, "due_date": inv.due_date, "notes": inv.notes, "resolution_summary": inv.resolution_summary, "links": {"alert": inv.linked_alert_id, "ai_execution": inv.linked_execution_id, "quality_issue": inv.linked_quality_issue_id, "forecast": inv.linked_forecast_id}, "comments": [{"id": c.id, "user_id": c.user_id, "body": c.body, "internal": c.internal, "created_at": c.created_at} for c in comments], "approval": {"id": approval.id, "status": approval.status, "recommendation": approval.recommendation, "policy": approval.policy_name, "current_step": approval.current_step, "steps": _approval_steps(approval), "required_role": approval.required_role, "expires_at": approval.expires_at, "history": [{"decision": event.decision, "actor_id": event.actor_id, "note": event.note, "step": event.step, "created_at": event.created_at} for event in events]} if approval else None}


@app.post("/api/v1/investigations", tags=["Investigations"])
def create_investigation(payload: InvestigationCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Finance Analyst", "Operations Manager", "Supply Chain Manager", "Branch Manager", "Reviewer"})
    inv = Investigation(organization_id=org.id, title=payload.title, category=payload.category, priority=payload.priority, severity=payload.severity, status="open", owner_id=user.id, notes=payload.notes, linked_execution_id=payload.linked_execution_id, linked_alert_id=payload.linked_alert_id, linked_quality_issue_id=payload.linked_quality_issue_id, due_date=payload.due_date)
    db.add(inv)
    db.flush()
    _audit(db, org.id, user, "investigation.create", "investigation", str(inv.id), {"priority": payload.priority}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": inv.id, "title": inv.title, "status": inv.status}


@app.patch("/api/v1/investigations/{investigation_id}", tags=["Investigations"])
def update_investigation(investigation_id: int, payload: InvestigationUpdate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    inv = _get_scoped(db, Investigation, investigation_id, org.id, "Investigation")
    _require_workspace_role(user, db, {"Organization Admin", "Finance Analyst", "Operations Manager", "Supply Chain Manager", "Branch Manager", "Reviewer"})
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(inv, key, value)
    _audit(db, org.id, user, "investigation.update", "investigation", str(inv.id), payload.model_dump(exclude_none=True), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": inv.id, "status": inv.status}


@app.post("/api/v1/investigations/{investigation_id}/comments", tags=["Investigations"])
def comment(investigation_id: int, payload: CommentCreate, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _get_scoped(db, Investigation, investigation_id, org.id, "Investigation")
    item = InvestigationComment(investigation_id=investigation_id, user_id=user.id, body=payload.body, internal=payload.internal)
    db.add(item)
    db.commit()
    return {"id": item.id, "body": item.body}


@app.post("/api/v1/investigations/{investigation_id}/approve", tags=["Investigations"])
def approve(investigation_id: int, payload: ApprovalDecision, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    inv = _get_scoped(db, Investigation, investigation_id, org.id, "Investigation")
    approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.investigation_id == inv.id, ApprovalRequest.organization_id == org.id).order_by(desc(ApprovalRequest.created_at)))
    if not approval:
        approval = ApprovalRequest(organization_id=org.id, investigation_id=inv.id, requested_by_id=user.id, recommendation="Decision requested from investigation", policy_name="Standard operational review", required_role="Organization Admin")
        db.add(approval)
        db.flush()
    result = _advance_approval(approval, user, db, payload.note)
    _audit(db, org.id, user, "approval.step_approved", "approval_request", str(approval.id), {"investigation_id": inv.id, **result}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {**result, "approval_request_id": approval.id, "simulated_execution": True}


@app.post("/api/v1/approvals/{approval_id}/approve", tags=["Investigations"])
def approve_request(approval_id: int, payload: ApprovalDecision, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    approval = _get_scoped(db, ApprovalRequest, approval_id, org.id, "Approval request")
    if approval.status in {"approved", "rejected", "expired"}:
        raise HTTPException(409, "Approval request is already closed")
    if approval.expires_at and approval.expires_at < NOW:
        approval.status = "expired"
        db.commit()
        raise HTTPException(409, "Approval request has expired")
    result = _advance_approval(approval, user, db, payload.note)
    _audit(db, org.id, user, "approval.step_approved", "approval_request", str(approval.id), result, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {**result, "approval_request_id": approval.id, "simulated_execution": True}


@app.post("/api/v1/investigations/{investigation_id}/reject", tags=["Investigations"])
def reject(investigation_id: int, payload: ApprovalDecision, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    inv = _get_scoped(db, Investigation, investigation_id, org.id, "Investigation")
    approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.investigation_id == inv.id, ApprovalRequest.organization_id == org.id).order_by(desc(ApprovalRequest.created_at)))
    role = current_role(user, db).name
    if approval and role not in {approval.required_role, "Platform Admin"}:
        raise HTTPException(403, f"Rejection step requires {approval.required_role}")
    inv.status = "rejected"
    if approval:
        approval.status = "rejected"
        db.add(ApprovalEvent(approval_request_id=approval.id, actor_id=user.id, decision="rejected", note=payload.note, step=approval.current_step))
    _audit(db, org.id, user, "approval.rejected", "investigation", str(inv.id), {"note": payload.note}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"status": "rejected", "approval_request_id": approval.id if approval else None}


@app.post("/api/v1/approvals/{approval_id}/reject", tags=["Investigations"])
def reject_approval_request(approval_id: int, payload: ApprovalDecision, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    approval = _get_scoped(db, ApprovalRequest, approval_id, org.id, "Approval request")
    role = current_role(user, db).name
    if role not in {approval.required_role, "Platform Admin"}:
        raise HTTPException(403, f"Rejection step requires {approval.required_role}")
    approval.status = "rejected"
    if approval.investigation_id:
        inv = db.get(Investigation, approval.investigation_id)
        if inv:
            inv.status = "rejected"
    if approval.scenario_id:
        scenario = db.get(Scenario, approval.scenario_id)
        if scenario:
            scenario.status = "rejected"
    db.add(ApprovalEvent(approval_request_id=approval.id, actor_id=user.id, decision="rejected", note=payload.note, step=approval.current_step))
    _audit(db, org.id, user, "approval.rejected", "approval_request", str(approval.id), {"note": payload.note}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"status": "rejected", "approval_request_id": approval.id, "simulated_execution": True}


@app.post("/api/v1/investigations/{investigation_id}/resolve", tags=["Investigations"])
def resolve(investigation_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    inv = _get_scoped(db, Investigation, investigation_id, org.id, "Investigation")
    inv.status = "resolved"
    db.commit()
    return {"status": "resolved"}


@app.get("/api/v1/approvals", tags=["Investigations"])
def list_approvals(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(ApprovalRequest).where(ApprovalRequest.organization_id == org.id).order_by(desc(ApprovalRequest.created_at))).all()
    return [{"id": r.id, "investigation_id": r.investigation_id, "scenario_id": r.scenario_id, "status": r.status, "recommendation": r.recommendation, "policy": r.policy_name, "current_step": r.current_step, "steps": _approval_steps(r), "required_role": r.required_role, "expires_at": r.expires_at} for r in rows]


# Inventory
@app.get("/api/v1/inventory/stockout-risks", tags=["Inventory"])
def inventory_risks(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return stockout_risks(db, org.id, _actor(user, db))


@app.get("/api/v1/inventory/reorder-recommendations", tags=["Inventory"])
def reorder(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return stockout_risks(db, org.id, _actor(user, db))[:12]


@app.get("/api/v1/inventory/supplier-lead-time-risk", tags=["Inventory"])
def supplier_lead_time(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return supplier_risk(db, org.id)


@app.get("/api/v1/inventory/products/{sku}", tags=["Inventory"])
def product_drilldown(sku: str, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    product = db.scalar(select(Product).where(Product.organization_id == org.id, Product.sku == sku))
    if not product:
        raise HTTPException(404, "Product not found")
    clauses = [InventoryRecord.organization_id == org.id, InventoryRecord.product_id == product.id]
    actor = _actor(user, db)
    if getattr(actor, "role_name", "") == "Branch Manager" and user.assigned_branch_id:
        clauses.append(InventoryRecord.branch_id == user.assigned_branch_id)
    records = db.scalars(select(InventoryRecord).where(*clauses)).all()
    return {"sku": product.sku, "name": product.name, "unit_cost": product.unit_cost, "list_price": product.list_price, "reorder_point": product.reorder_point, "inventory": [{"branch_id": r.branch_id, "available_units": r.available_units, "inventory_value": r.inventory_value} for r in records]}


# Data Quality Center
@app.get("/api/v1/data-quality/overview", tags=["Data Quality"])
def quality_overview(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return data_quality_overview(db, org.id)


@app.get("/api/v1/data-quality/issues/{issue_id}", tags=["Data Quality"])
def quality_issue(issue_id: int, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = _get_scoped(db, DataQualityIssue, issue_id, org.id, "Quality issue")
    return {"id": item.id, "issue_type": item.issue_type, "affected_table": item.affected_table, "severity": item.severity, "status": item.status, "affected_records": item.affected_records, "remediation": item.remediation, "related_metrics": item.related_metrics, "owner_id": item.owner_id}


@app.patch("/api/v1/data-quality/issues/{issue_id}", tags=["Data Quality"])
def update_quality_issue(issue_id: int, payload: DataQualityStateUpdate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Operations Manager", "Supply Chain Manager", "Finance Analyst"})
    item = _get_scoped(db, DataQualityIssue, issue_id, org.id, "Quality issue")
    item.status = payload.status
    if payload.owner_id is not None:
        item.owner_id = payload.owner_id
    _audit(db, org.id, user, "data_quality.issue_updated", "data_quality_issue", str(item.id), payload.model_dump(), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": item.id, "status": item.status}


@app.post("/api/v1/data-quality/issues/{issue_id}/investigations", tags=["Data Quality"])
def quality_to_investigation(issue_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    issue = _get_scoped(db, DataQualityIssue, issue_id, org.id, "Quality issue")
    inv = Investigation(organization_id=org.id, title=f"Resolve data-quality issue: {issue.issue_type}", category="data_quality", priority="high" if issue.severity in {"high", "critical"} else "medium", severity=issue.severity, status="open", owner_id=user.id, linked_quality_issue_id=issue.id, notes=issue.remediation)
    db.add(inv)
    db.commit()
    return {"investigation_id": inv.id, "status": inv.status}


# Alerting and Watchlists
@app.post("/api/v1/alerts/evaluate", tags=["Alerts"])
def evaluate_alerts(request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Operations Manager", "Supply Chain Manager", "Finance Analyst"})
    result = evaluate_alert_rules(db, org.id)
    _audit(db, org.id, user, "alert.rules_evaluated", "alert_rule_set", str(org.id), result, request.headers.get("X-Request-ID", ""))
    db.commit()
    return result


@app.get("/api/v1/alerts", tags=["Alerts"])
def alert_center(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return alerts_and_watchlists(db, org.id, user.id)


@app.patch("/api/v1/alerts/{alert_id}", tags=["Alerts"])
def update_alert(alert_id: int, payload: AlertStateUpdate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = _get_scoped(db, Alert, alert_id, org.id, "Alert")
    item.status = payload.status
    if payload.owner_id is not None:
        item.assigned_to_id = payload.owner_id
    _audit(db, org.id, user, "alert.state_changed", "alert", str(item.id), payload.model_dump(), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": item.id, "status": item.status}


@app.post("/api/v1/alerts/{alert_id}/investigations", tags=["Alerts"])
def alert_to_investigation(alert_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    alert = _get_scoped(db, Alert, alert_id, org.id, "Alert")
    inv = Investigation(organization_id=org.id, title=f"Investigate: {alert.title}", category=alert.entity_type, priority="high" if alert.severity in {"high", "critical"} else "medium", severity=alert.severity, status="triaged", owner_id=user.id, linked_alert_id=alert.id, notes=alert.description)
    db.add(inv)
    db.commit()
    return {"investigation_id": inv.id, "status": inv.status}


# Forecasting, anomaly explorer and scenario workbench
@app.get("/api/v1/forecasts", tags=["Forecasting"])
def forecasts(metric_slug: str = "revenue", horizon_days: int = 14, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return forecast_payload(db, org.id, metric_slug, min(max(horizon_days, 7), 90))


@app.get("/api/v1/anomalies", tags=["Forecasting"])
def anomalies(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return anomaly_payload(db, org.id)


@app.get("/api/v1/scenarios", tags=["Decision Workbench"])
def scenarios(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Scenario).where(Scenario.organization_id == org.id).order_by(desc(Scenario.created_at))).all()
    return [{"id": s.id, "name": s.name, "status": s.status, "assumptions": s.assumptions, "impact": s.impact, "is_simulated": s.is_simulated, "created_at": s.created_at} for s in rows]


@app.post("/api/v1/scenarios", tags=["Decision Workbench"])
def create_scenario(payload: ScenarioCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Finance Analyst", "Operations Manager", "Supply Chain Manager"})
    impact = scenario_impact(db, org.id, payload.adjustments)
    scenario = Scenario(organization_id=org.id, owner_id=user.id, name=payload.name, status="draft", assumptions={**payload.assumptions, "adjustments": payload.adjustments}, impact=impact, is_simulated=True)
    db.add(scenario)
    db.flush()
    for adjustment in payload.adjustments:
        db.add(ScenarioAdjustment(scenario_id=scenario.id, adjustment_type=adjustment.get("type", "other"), payload=adjustment))
    _audit(db, org.id, user, "scenario.create", "scenario", str(scenario.id), {"simulated": True}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": scenario.id, "name": scenario.name, "impact": impact, "simulated": True}


@app.post("/api/v1/scenarios/{scenario_id}/request-approval", tags=["Decision Workbench"])
def scenario_request_approval(scenario_id: int, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    scenario = _get_scoped(db, Scenario, scenario_id, org.id, "Scenario")
    scenario.status = "pending_approval"
    policy = "Inventory transfer above threshold" if any(a.get("type") in {"inventory_transfer", "transfer_inventory"} for a in (scenario.assumptions.get("adjustments", []) if scenario.assumptions else [])) else "Scenario recommendation review"
    first_required_role = APPROVAL_POLICY_STEPS[policy][0]
    approval = ApprovalRequest(organization_id=org.id, scenario_id=scenario.id, requested_by_id=user.id, status="pending", recommendation=f"Approve simulated recommendation: {scenario.name}", policy_name=policy, required_role=first_required_role, current_step=1, expires_at=NOW + timedelta(days=2))
    db.add(approval)
    db.flush()
    db.add(ApprovalEvent(approval_request_id=approval.id, actor_id=user.id, decision="submitted", note="Simulation does not mutate source operations", step=1))
    _audit(db, org.id, user, "scenario.approval_requested", "scenario", str(scenario.id), {"approval_request_id": approval.id, "policy": policy, "required_role": first_required_role}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"scenario_id": scenario.id, "approval_request_id": approval.id, "status": "pending", "required_role": first_required_role, "steps": APPROVAL_POLICY_STEPS[policy], "simulated": True}


# Reporting center
@app.get("/api/v1/reports", tags=["Reporting"])
def reports(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Report).where(Report.organization_id == org.id).order_by(desc(Report.generated_at))).all()
    return [{"id": r.id, "name": r.name, "report_type": r.report_type, "status": r.status, "filters": r.filters, "version": r.version, "generated_at": r.generated_at} for r in rows]


@app.post("/api/v1/reports", tags=["Reporting"])
def create_report(payload: ReportCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Finance Analyst", "Operations Manager", "Supply Chain Manager"})
    content = {"overview": overview(db, org.id, _actor(user, db)), "quality": data_quality_overview(db, org.id), "alerts": alerts(db, org.id)[:5], "generated_by": user.email, "synthetic": True}
    report = Report(organization_id=org.id, created_by_id=user.id, name=payload.name, report_type=payload.report_type, filters=payload.filters, content=jsonable_encoder(content), version=1)
    db.add(report)
    db.flush()
    _audit(db, org.id, user, "report.generate", "report", str(report.id), {"type": report.report_type}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": report.id, "name": report.name, "status": report.status, "preview": content}


@app.get("/api/v1/reports/{report_id}/export.csv", tags=["Reporting"])
def export_csv(report_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> Response:
    report = _get_scoped(db, Report, report_id, org.id, "Report")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["report", report.name])
    writer.writerow(["report_type", report.report_type])
    writer.writerow(["generated_at", report.generated_at.isoformat()])
    writer.writerow(["notice", "Synthetic workspace export; not a production system-of-record."])
    _audit(db, org.id, user, "report.export_csv", "report", str(report.id))
    db.commit()
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="opslens-report-{report.id}.csv"'})


@app.get("/api/v1/reports/{report_id}/export.pdf", tags=["Reporting"])
def export_pdf(report_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> Response:
    report = _get_scoped(db, Report, report_id, org.id, "Report")
    # A minimal valid PDF for local demo exports without an untracked rendering service.
    text = f"OpsLens AI — {report.name}\\nSynthetic demo report. Review linked evidence and data-quality notices before action."
    pdf = ("%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n" + f"5 0 obj<</Length {len(text)+35}>>stream\nBT /F1 12 Tf 54 720 Td ({text.replace('(', '[').replace(')', ']')}) Tj ET\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF").encode()
    _audit(db, org.id, user, "report.export_pdf", "report", str(report.id))
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="opslens-report-{report.id}.pdf"'})


@app.get("/api/v1/reports/schedules", tags=["Reporting"])
def report_schedules(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(ScheduledReport).where(ScheduledReport.organization_id == org.id).order_by(ScheduledReport.next_run_at)).all()
    return [{"id": s.id, "name": s.name, "report_type": s.report_type, "cadence": s.cadence, "next_run_at": s.next_run_at, "delivery_channel": s.delivery_channel, "is_simulated": s.is_simulated, "enabled": s.enabled} for s in rows]


@app.post("/api/v1/reports/schedules", tags=["Reporting"])
def create_report_schedule(payload: ScheduleCreate, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    schedule = ScheduledReport(organization_id=org.id, report_type=payload.report_type, name=payload.name, cadence=payload.cadence, next_run_at=NOW+timedelta(days=1 if payload.cadence == "daily" else 7), delivery_channel=payload.delivery_channel, is_simulated=True)
    db.add(schedule)
    db.commit()
    return {"id": schedule.id, "next_run_at": schedule.next_run_at, "simulated": True}


@app.post("/api/v1/reports/schedules/{schedule_id}/run-now", tags=["Reporting"])
def run_schedule(schedule_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    schedule = _get_scoped(db, ScheduledReport, schedule_id, org.id, "Report schedule")
    report = Report(organization_id=org.id, created_by_id=user.id, name=f"{schedule.name} — run now", report_type=schedule.report_type, status="generated", filters={"scheduled": True}, content={"delivery": "simulated", "schedule_id": schedule.id})
    db.add(report)
    schedule.next_run_at = NOW + timedelta(days=1 if schedule.cadence == "daily" else 7)
    db.commit()
    return {"report_id": report.id, "status": "generated", "delivery": "simulated"}


# Ingestion and lineage
@app.post("/api/v1/ingestion/preview", tags=["Ingestion"])
def ingestion_preview(payload: ImportPreviewRequest, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Operations Manager", "Supply Chain Manager"})
    result = import_preview(payload.rows, payload.import_type)
    job = ImportJob(organization_id=org.id, created_by_id=user.id, source_type="csv", import_type=payload.import_type, status="preview" if result["status"] == "ready" else "validation_failed", file_name=payload.file_name, records_total=result["records_total"], records_valid=result["records_valid"], records_invalid=result["records_invalid"], preview=result["preview"], validation_errors=result["errors"], rollback_available=True)
    db.add(job)
    db.flush()
    for item in result["mapping"]:
        db.add(ImportMapping(import_job_id=job.id, **item))
    _audit(db, org.id, user, "ingestion.preview", "import_job", str(job.id), {"type": payload.import_type, "status": job.status})
    db.commit()
    return {"import_job_id": job.id, **result}


@app.post("/api/v1/ingestion/csv", tags=["Ingestion"])
async def ingestion_csv(import_type: str, file: UploadFile = File(...), user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    raw = (await file.read()).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(raw)))
    permitted_import_types = {"products", "sales", "inventory", "suppliers", "purchase_orders", "returns", "branches"}
    if import_type not in permitted_import_types:
        raise HTTPException(422, "Unsupported import type")
    payload = ImportPreviewRequest(import_type=import_type, file_name=file.filename or "upload.csv", rows=rows)  # type: ignore[arg-type]
    return ingestion_preview(payload, user, org, db)


@app.post("/api/v1/ingestion/{job_id}/commit", tags=["Ingestion"])
def ingestion_commit(job_id: int, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = _get_scoped(db, ImportJob, job_id, org.id, "Import job")
    if job.records_invalid:
        raise HTTPException(409, "Import cannot complete until validation failures are resolved")
    job.status = "completed"
    _audit(db, org.id, user, "ingestion.commit", "import_job", str(job.id), {"simulated_normalization": True}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": job.id, "status": job.status, "rollback_available": job.rollback_available}


@app.get("/api/v1/ingestion/jobs", tags=["Ingestion"])
def import_jobs(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(ImportJob).where(ImportJob.organization_id == org.id).order_by(desc(ImportJob.created_at))).all()
    return [{"id": j.id, "source_type": j.source_type, "import_type": j.import_type, "status": j.status, "file_name": j.file_name, "records_total": j.records_total, "records_valid": j.records_valid, "records_invalid": j.records_invalid, "rollback_available": j.rollback_available, "created_at": j.created_at} for j in rows]


@app.get("/api/v1/lineage", tags=["Ingestion"])
def lineage(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(LineageEvent).where(LineageEvent.organization_id == org.id).order_by(LineageEvent.created_at)).all()
    return [{"id": r.id, "source_kind": r.source_kind, "source_ref": r.source_ref, "target_kind": r.target_kind, "target_ref": r.target_ref, "metadata": r.metadata_json} for r in rows]


# Governance, metrics, security and developer boundary
@app.get("/api/v1/governance/audit-events", tags=["Governance"])
def audit_events(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(AuditEvent).where(AuditEvent.organization_id == org.id).order_by(desc(AuditEvent.created_at)).limit(200)).all()
    return [{"id": item.id, "actor_email": item.actor_email, "action": item.action, "resource_type": item.resource_type, "resource_id": item.resource_id, "request_id": item.request_id, "metadata": item.metadata_json, "created_at": item.created_at} for item in rows]


@app.get("/api/v1/governance/roles", tags=["Governance"])
def role_management(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": role.id, "name": role.name, "description": role.description, "permissions": role.permissions} for role in db.scalars(select(Role).order_by(Role.name))]


@app.get("/api/v1/governance/data-sources", tags=["Governance"])
def sources(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(DataSource).where(DataSource.organization_id == org.id)).all()
    return [{"id": row.id, "name": row.name, "type": row.source_type, "status": row.status, "last_synced_at": row.last_synced_at, "last_success_at": row.last_success_at, "freshness_hours": row.freshness_hours, "schema": row.schema_name, "config": row.config} for row in rows]


@app.get("/api/v1/governance/metric-definitions", tags=["Governance"])
def metric_defs(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return metric_catalog(db, org.id)


@app.get("/api/v1/metrics/dependency-graph", tags=["Governance"])
def metric_dependency_graph(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return metric_graph(db, org.id)


@app.get("/api/v1/security/api-keys", tags=["Security"])
def api_keys(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(ApiKey).where(ApiKey.organization_id == org.id).order_by(desc(ApiKey.created_at))).all()
    return [{"id": key.id, "label": key.label, "prefix": key.prefix, "scopes": key.scopes, "expires_at": key.expires_at, "last_used_at": key.last_used_at, "revoked": key.revoked} for key in rows]


@app.post("/api/v1/security/api-keys", tags=["Security"])
def create_api_key(payload: ApiKeyCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin"})
    key = ApiKey(organization_id=org.id, user_id=user.id, label=payload.label, prefix="ops_live_", scopes=payload.scopes, expires_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=payload.expires_in_days))
    db.add(key)
    db.flush()
    _audit(db, org.id, user, "api_key.create", "api_key", str(key.id), {"scopes": payload.scopes}, request.headers.get("X-Request-ID", ""))
    db.commit()
    # The opaque key is returned only at creation time; it is not stored in raw form.
    return {"id": key.id, "prefix": key.prefix, "scopes": key.scopes, "api_key": issue_api_key_value(key), "expires_at": key.expires_at, "one_time_display": True}


@app.post("/api/v1/security/api-keys/{key_id}/revoke", tags=["Security"])
def revoke_api_key(key_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin"})
    key = _get_scoped(db, ApiKey, key_id, org.id, "API key")
    key.revoked = True
    db.commit()
    return {"id": key.id, "revoked": True}


@app.get("/api/v1/programmatic/dashboard/overview", tags=["Programmatic API"])
def programmatic_overview(principal: Any = Depends(require_api_key_scope("metrics:read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Example API-key-authenticated integration route scoped to the key organization."""
    return {"organization_id": principal.organization_id, "data": overview(db, principal.organization_id)}


@app.get("/api/v1/security/center", tags=["Security"])
def security_center(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"api_keys": api_keys(org, db), "controls": ["PBKDF2 password hashing", "Signed expiring access tokens", "Tenant boundary checks", "Rate limiting", "Request IDs", "Sensitive export audit records", "Read-only AI SQL design"], "data_retention": "Reference policy placeholder: configure retention for production deployment.", "security_alerts": [a for a in alerts(db, org.id) if a["entity_type"] == "data_source"]}


@app.get("/api/v1/search", tags=["Governance"])
def search(q: str, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return global_search(db, org.id, q, include_users=current_role(user, db).name == "Organization Admin")


@app.get("/api/v1/operations/console", tags=["Operations Console"])
def operations_console(org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    return operation_console(db, org.id)



# Phase 3 launch-hardening endpoints: live workflow mutations, lineage details, retention and evidence exports.
@app.get("/api/v1/system/migration-status", tags=["Operations Console"])
def migration_status() -> dict[str, Any]:
    return {"status": "available", "current_revision": "0003_phase3_launch", "migration_mode": "explicit_alembic_reference", "metadata_bootstrap": "local_demo_only"}


@app.get("/api/v1/system/database-health", tags=["Operations Console"])
def database_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    db.execute(select(Organization.id).limit(1)).first()
    return {"database": "reachable", "readiness": "ok", "production_boundary": "PostgreSQL required outside deterministic demo mode", "warnings": settings.startup_warnings()}


@app.post("/api/v1/alerts/rules", tags=["Alerts"])
def create_alert_rule(payload: AlertRuleCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Operations Manager", "Supply Chain Manager", "Finance Analyst"})
    rule = AlertRule(organization_id=org.id, name=payload.name, category=payload.category, severity=payload.severity, metric_slug=payload.metric_slug, operator=payload.operator, threshold=payload.threshold, scope_type=payload.scope_type, notification_targets=payload.notification_targets)
    db.add(rule)
    db.flush()
    _audit(db, org.id, user, "alert_rule.create", "alert_rule", str(rule.id), payload.model_dump(), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": rule.id, "name": rule.name, "status": rule.status, "audit_event": "alert_rule.create"}


@app.post("/api/v1/watchlists", tags=["Alerts"])
def create_watchlist(payload: WatchlistCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Operations Manager", "Supply Chain Manager", "Finance Analyst"})
    watchlist = Watchlist(organization_id=org.id, owner_id=user.id, name=payload.name, description=payload.description, criteria=payload.criteria, is_shared=payload.is_shared)
    db.add(watchlist)
    db.flush()
    _audit(db, org.id, user, "watchlist.create", "watchlist", str(watchlist.id), {"shared": watchlist.is_shared}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": watchlist.id, "name": watchlist.name, "status": "created", "audit_event": "watchlist.create"}


@app.post("/api/v1/watchlists/{watchlist_id}/items", tags=["Alerts"])
def add_watchlist_item(watchlist_id: int, payload: WatchlistItemCreate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    watchlist = _get_scoped(db, Watchlist, watchlist_id, org.id, "Watchlist")
    _require_workspace_role(user, db, {"Organization Admin", "Operations Manager", "Supply Chain Manager", "Finance Analyst"})
    item = WatchlistItem(organization_id=org.id, watchlist_id=watchlist.id, entity_type=payload.entity_type, entity_id=payload.entity_id, label=payload.label, metadata_json=payload.metadata)
    db.add(item)
    db.flush()
    _audit(db, org.id, user, "watchlist.item_added", "watchlist", str(watchlist.id), payload.model_dump(), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": item.id, "watchlist_id": watchlist.id, "status": "active", "audit_event": "watchlist.item_added"}


@app.delete("/api/v1/watchlists/{watchlist_id}/items/{item_id}", tags=["Alerts"])
def remove_watchlist_item(watchlist_id: int, item_id: int, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    watchlist = _get_scoped(db, Watchlist, watchlist_id, org.id, "Watchlist")
    item = db.get(WatchlistItem, item_id)
    if not item or item.watchlist_id != watchlist.id or item.organization_id != org.id:
        raise HTTPException(404, "Watchlist item not found")
    item.status = "removed"
    _audit(db, org.id, user, "watchlist.item_removed", "watchlist_item", str(item.id), {}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": item.id, "status": item.status}


@app.patch("/api/v1/scenarios/{scenario_id}", tags=["Decision Workbench"])
def update_scenario(scenario_id: int, payload: ScenarioUpdate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Finance Analyst", "Operations Manager", "Supply Chain Manager"})
    scenario = _get_scoped(db, Scenario, scenario_id, org.id, "Scenario")
    if payload.name:
        scenario.name = payload.name
    if payload.status:
        scenario.status = payload.status
    if payload.assumptions is not None:
        scenario.assumptions = {**(scenario.assumptions or {}), **payload.assumptions}
    if payload.adjustments is not None:
        scenario.assumptions = {**(scenario.assumptions or {}), "adjustments": payload.adjustments}
        scenario.impact = scenario_impact(db, org.id, payload.adjustments)
    _audit(db, org.id, user, "scenario.update", "scenario", str(scenario.id), payload.model_dump(exclude_none=True), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": scenario.id, "name": scenario.name, "status": scenario.status, "impact": scenario.impact, "audit_event": "scenario.update"}


@app.get("/api/v1/scenarios/compare", tags=["Decision Workbench"])
def compare_scenarios(ids: str, org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    scenario_ids = [int(value) for value in ids.split(",") if value.strip().isdigit()]
    rows = db.scalars(select(Scenario).where(Scenario.organization_id == org.id, Scenario.id.in_(scenario_ids))).all()
    return {"baseline_warning": "Scenario data is simulated and never mutates operational source records.", "scenarios": [{"id": s.id, "name": s.name, "status": s.status, "impact": s.impact, "assumptions": s.assumptions} for s in rows]}


@app.post("/api/v1/ingestion/json", tags=["Ingestion"])
def ingestion_json(payload: JsonImportRequest, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    checksum = hashlib.sha256(json.dumps(payload.rows, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(ImportJob).where(ImportJob.organization_id == org.id, ImportJob.file_name == f"{payload.file_name}:{checksum}"))
    if existing:
        raise HTTPException(409, "Duplicate import payload detected by checksum")
    request_payload = ImportPreviewRequest(import_type=payload.import_type, file_name=f"{payload.file_name}:{checksum}", rows=payload.rows)
    return ingestion_preview(request_payload, user, org, db)


@app.post("/api/v1/ingestion/{job_id}/rollback", tags=["Ingestion"])
def ingestion_rollback(job_id: int, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = _get_scoped(db, ImportJob, job_id, org.id, "Import job")
    if not job.rollback_available:
        raise HTTPException(409, "Rollback is not available for this import")
    job.status = "rolled_back_simulated"
    job.rollback_available = False
    db.add(LineageEvent(organization_id=org.id, source_kind="Import job", source_ref=str(job.id), target_kind="Rollback simulation", target_ref=job.status, metadata_json={"synthetic": True}))
    _audit(db, org.id, user, "ingestion.rollback", "import_job", str(job.id), {"simulated": True}, request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"id": job.id, "status": job.status, "simulated": True, "audit_event": "ingestion.rollback"}


@app.get("/api/v1/evidence-packages/{execution_id}.json", tags=["AI Operations"])
def evidence_package_json(execution_id: int, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    execution = _get_scoped(db, AIQueryExecution, execution_id, org.id, "AI execution")
    plan = db.scalar(select(QueryPlan).where(QueryPlan.execution_id == execution.id))
    validation = db.scalar(select(SQLValidationResult).where(SQLValidationResult.execution_id == execution.id))
    package = {
        "synthetic_demo": True,
        "organization_id": org.id,
        "generated_for": user.email,
        "execution": {"id": execution.id, "question": execution.question, "answer": execution.answer, "confidence": execution.confidence},
        "query_plan": jsonable_encoder(plan) if plan else None,
        "sql_validation": {"valid": validation.is_valid, "reasons": validation.reasons, "tables": validation.tables, "complexity_score": validation.complexity_score} if validation else None,
        "evidence": execution.evidence,
        "data_quality": data_quality_overview(db, org.id),
        "audit": audit_events(org, db)[:20],
    }
    db.add(AuditEvent(organization_id=org.id, actor_email=user.email, action="evidence_package.export_json", resource_type="ai_execution", resource_id=str(execution.id), metadata_json={"synthetic": True}))
    db.commit()
    return package


@app.get("/api/v1/notifications", tags=["Operations Console"])
def notifications(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Notification).where(Notification.organization_id == org.id, Notification.user_id == user.id).order_by(desc(Notification.created_at)).limit(50)).all()
    return [{"id": n.id, "title": n.title, "body": n.body, "type": n.type, "read_at": n.read_at, "created_at": n.created_at} for n in rows]


@app.patch("/api/v1/security/retention", tags=["Security"])
def update_retention(payload: RetentionConfigUpdate, request: Request, user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin"})
    _audit(db, org.id, user, "retention.update", "organization", str(org.id), payload.model_dump(), request.headers.get("X-Request-ID", ""))
    db.commit()
    return {"status": "updated", "configuration": payload.model_dump(), "audit_event": "retention.update", "note": "Reference retention model; configure legal hold and deletion workflows before production."}


@app.get("/api/v1/governance/audit-events/export.json", tags=["Governance"])
def audit_export(user: User = Depends(current_user), org: Organization = Depends(active_organization), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_workspace_role(user, db, {"Organization Admin", "Finance Analyst"})
    rows = audit_events(org, db)
    _audit(db, org.id, user, "audit.export_json", "organization", str(org.id), {"count": len(rows)})
    db.commit()
    return {"synthetic_demo": True, "count": len(rows), "events": rows}

# Local static preview retained for browser screenshot capture.
STATIC = Path(__file__).parent / "static" / "demo.html"


@app.get("/demo-preview", include_in_schema=False)
def preview(screen: str = "overview") -> FileResponse:
    return FileResponse(STATIC, media_type="text/html", headers={"X-OpsLens-Screen": screen})
