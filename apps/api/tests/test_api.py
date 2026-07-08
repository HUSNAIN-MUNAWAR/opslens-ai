import os
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

TEST_DB = Path(gettempdir()) / f"test_opslens_phase2_{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "phase2-test-secret"

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client, email="admin@opslens.demo"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_demo_login_workspace_and_overview(client):
    headers = login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["organization"]["name"] == "Northstar Retail Group"
    workspace_response = client.get("/api/v1/workspaces", headers=headers)
    assert workspace_response.status_code == 200
    assert len(workspace_response.json()) == 3
    overview = client.get("/api/v1/dashboard/overview", headers=headers)
    assert overview.status_code == 200
    assert len(overview.json()["kpis"]) == 5
    assert overview.json()["data_quality_notices"]


def test_workspace_switch_and_tenant_isolation(client):
    admin = login(client)
    workspaces = client.get("/api/v1/workspaces", headers=admin).json()
    crescent = next(w for w in workspaces if w["slug"] == "crescent")
    switched = client.post("/api/v1/workspaces/switch", json={"organization_id": crescent["id"]}, headers=admin)
    assert switched.status_code == 200
    crescent_headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}
    sources = client.get("/api/v1/governance/data-sources", headers=crescent_headers)
    assert sources.status_code == 200
    assert all("Inventory" not in item["name"] or item["freshness_hours"] < 2 for item in sources.json())
    finance = login(client, "finance@opslens.demo")
    denied = client.post("/api/v1/workspaces/switch", json={"organization_id": crescent["id"]}, headers=finance)
    assert denied.status_code == 403


def test_governed_ai_question_and_unsafe_sql(client):
    headers = login(client, "ops@opslens.demo")
    convo = client.post("/api/v1/ai/conversations", json={"title": "Stockout test"}, headers=headers)
    assert convo.status_code == 200
    execution = client.post(
        f"/api/v1/ai/conversations/{convo.json()['id']}/questions",
        json={"question": "Which products are likely to stock out within 14 days?", "mode": "Investigation Mode"},
        headers=headers,
    )
    assert execution.status_code == 200, execution.text
    body = execution.json()
    assert body["status"] == "completed"
    assert ":organization_id" in body["sql"]
    assert body["validation"]["valid"]
    unsupported = client.post(
        f"/api/v1/ai/conversations/{convo.json()['id']}/questions",
        json={"question": "What do customers feel about us?"},
        headers=headers,
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["status"] == "blocked"


def test_quality_scenario_report_and_import_contracts(client):
    headers = login(client, "admin@opslens.demo")
    quality = client.get("/api/v1/data-quality/overview", headers=headers)
    assert quality.status_code == 200
    assert quality.json()["active_issue_count"] >= 1
    scenario = client.post("/api/v1/scenarios", json={"name": "Transfer test", "adjustments": [{"type": "transfer_inventory", "value": 40}]}, headers=headers)
    assert scenario.status_code == 200
    approval = client.post(f"/api/v1/scenarios/{scenario.json()['id']}/request-approval", headers=headers)
    assert approval.status_code == 200
    report = client.post("/api/v1/reports", json={"name": "Verification brief", "report_type": "Executive Operations Brief"}, headers=headers)
    assert report.status_code == 200
    exported = client.get(f"/api/v1/reports/{report.json()['id']}/export.csv", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    preview = client.post("/api/v1/ingestion/preview", json={"import_type": "products", "file_name": "bad.csv", "rows": [{"sku": "A-1", "name": "Missing price"}]}, headers=headers)
    assert preview.status_code == 200
    assert preview.json()["status"] == "validation_failed"


def test_api_key_scope_programmatic_access_and_revocation(client):
    headers = login(client, "admin@opslens.demo")
    created = client.post(
        "/api/v1/security/api-keys",
        json={"label": "Test integration", "scopes": ["metrics:read"], "expires_in_days": 7},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["one_time_display"] is True
    programmatic = client.get(
        "/api/v1/programmatic/dashboard/overview",
        headers={"X-API-Key": body["api_key"]},
    )
    assert programmatic.status_code == 200, programmatic.text
    assert programmatic.json()["data"]["kpis"]
    revoked = client.post(f"/api/v1/security/api-keys/{body['id']}/revoke", headers=headers)
    assert revoked.status_code == 200
    denied = client.get("/api/v1/programmatic/dashboard/overview", headers={"X-API-Key": body["api_key"]})
    assert denied.status_code == 401


def test_role_permissions_alert_and_quality_lifecycle(client):
    viewer_headers = login(client, "viewer@opslens.demo")
    denied = client.post("/api/v1/scenarios", json={"name": "Viewer cannot simulate"}, headers=viewer_headers)
    assert denied.status_code == 403

    admin_headers = login(client, "admin@opslens.demo")
    alert_list = client.get("/api/v1/alerts", headers=admin_headers)
    assert alert_list.status_code == 200 and alert_list.json()["alerts"]
    alert_id = alert_list.json()["alerts"][0]["id"]
    acknowledged = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "acknowledged"}, headers=admin_headers)
    assert acknowledged.status_code == 200
    linked = client.post(f"/api/v1/alerts/{alert_id}/investigations", headers=admin_headers)
    assert linked.status_code == 200 and linked.json()["status"] == "triaged"

    quality = client.get("/api/v1/data-quality/overview", headers=admin_headers).json()
    issue_id = quality["issues"][0]["id"]
    updated = client.patch(f"/api/v1/data-quality/issues/{issue_id}", json={"status": "acknowledged"}, headers=admin_headers)
    assert updated.status_code == 200
    quality_inv = client.post(f"/api/v1/data-quality/issues/{issue_id}/investigations", headers=admin_headers)
    assert quality_inv.status_code == 200


def test_schedule_csv_upload_and_branch_role_scope(client):
    admin_headers = login(client, "admin@opslens.demo")
    scheduled = client.post(
        "/api/v1/reports/schedules",
        json={"name": "Daily stockout brief", "report_type": "Inventory Risk Report", "cadence": "daily", "delivery_channel": "in_app"},
        headers=admin_headers,
    )
    assert scheduled.status_code == 200, scheduled.text
    run_now = client.post(f"/api/v1/reports/schedules/{scheduled.json()['id']}/run-now", headers=admin_headers)
    assert run_now.status_code == 200

    uploaded = client.post(
        "/api/v1/ingestion/csv?import_type=products",
        files={"file": ("products.csv", "sku,name,unit_cost,list_price\nSKU-1,Good product,100,150\n", "text/csv")},
        headers=admin_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "ready"
    committed = client.post(f"/api/v1/ingestion/{uploaded.json()['import_job_id']}/commit", headers=admin_headers)
    assert committed.status_code == 200

    branch_headers = login(client, "branch.manager@opslens.demo")
    branch_rows = client.get("/api/v1/dashboard/branch-comparison", headers=branch_headers)
    assert branch_rows.status_code == 200
    assert len(branch_rows.json()) <= 1


def test_alert_rule_evaluation_is_a_real_idempotent_service(client):
    headers = login(client, "ops@opslens.demo")
    first = client.post("/api/v1/alerts/evaluate", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["evaluated_rule_count"] >= 1
    second = client.post("/api/v1/alerts/evaluate", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["created"] == 0
    assert second.json()["refreshed"] >= 1


def test_multistep_scenario_approval_policy(client):
    ops_headers = login(client, "ops@opslens.demo")
    scenario = client.post(
        "/api/v1/scenarios",
        json={"name": "Multi-step transfer", "adjustments": [{"type": "transfer_inventory", "value": 40}]},
        headers=ops_headers,
    )
    assert scenario.status_code == 200, scenario.text
    requested = client.post(f"/api/v1/scenarios/{scenario.json()['id']}/request-approval", headers=ops_headers)
    assert requested.status_code == 200, requested.text
    assert requested.json()["steps"] == ["Operations Manager", "Organization Admin"]
    first_step = client.post(
        f"/api/v1/approvals/{requested.json()['approval_request_id']}/approve",
        json={"note": "Operations review complete"},
        headers=ops_headers,
    )
    assert first_step.status_code == 200, first_step.text
    assert first_step.json()["status"] == "in_review"
    assert first_step.json()["required_role"] == "Organization Admin"
    admin_headers = login(client, "admin@opslens.demo")
    final_step = client.post(
        f"/api/v1/approvals/{requested.json()['approval_request_id']}/approve",
        json={"note": "Final governance approval"},
        headers=admin_headers,
    )
    assert final_step.status_code == 200, final_step.text
    assert final_step.json()["status"] == "approved"
