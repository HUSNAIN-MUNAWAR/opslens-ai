import os
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

TEST_DB = Path(gettempdir()) / f"test_opslens_phase3_{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "phase3-test-secret-with-more-than-32-characters"

from fastapi.testclient import TestClient
from app.main import app


def _headers(client: TestClient, email: str = "admin@opslens.demo") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_phase3_watchlist_rule_and_retention_workflow():
    with TestClient(app) as client:
        headers = _headers(client)
        rule = client.post("/api/v1/alerts/rules", json={"name": "Phase 3 freshness rule", "metric_slug": "freshness", "threshold": 6, "severity": "high"}, headers=headers)
        assert rule.status_code == 200, rule.text
        watchlist = client.post("/api/v1/watchlists", json={"name": "Launch watch", "description": "Phase 3 persisted membership"}, headers=headers)
        assert watchlist.status_code == 200, watchlist.text
        item = client.post(f"/api/v1/watchlists/{watchlist.json()['id']}/items", json={"entity_type": "alert", "entity_id": str(rule.json()["id"]), "label": "Freshness rule"}, headers=headers)
        assert item.status_code == 200, item.text
        alerts = client.get("/api/v1/alerts", headers=headers).json()
        created = next(w for w in alerts["watchlists"] if w["id"] == watchlist.json()["id"])
        assert created["items"][0]["label"] == "Freshness rule"
        retention = client.patch("/api/v1/security/retention", json={"audit_retention_days": 400, "report_retention_days": 800, "import_retention_days": 365, "legal_hold_enabled": False}, headers=headers)
        assert retention.status_code == 200, retention.text


def test_phase3_import_rollback_evidence_and_system_health():
    with TestClient(app) as client:
        headers = _headers(client, "ops@opslens.demo")
        health = client.get("/api/v1/system/database-health", headers=headers)
        assert health.status_code == 200 and health.json()["database"] == "reachable"
        job = client.post("/api/v1/ingestion/json", json={"import_type": "products", "file_name": "phase3-products.json", "rows": [{"sku": "P3-1", "name": "Phase 3", "unit_cost": 100, "list_price": 120}]}, headers=headers)
        assert job.status_code == 200, job.text
        committed = client.post(f"/api/v1/ingestion/{job.json()['import_job_id']}/commit", headers=headers)
        assert committed.status_code == 200, committed.text
        rollback = client.post(f"/api/v1/ingestion/{job.json()['import_job_id']}/rollback", headers=headers)
        assert rollback.status_code == 200, rollback.text
        conversation = client.post("/api/v1/ai/conversations", json={"title": "Evidence package"}, headers=headers).json()
        answer = client.post(f"/api/v1/ai/conversations/{conversation['id']}/questions", json={"question": "Which products are likely to stock out within 14 days?"}, headers=headers)
        assert answer.status_code == 200, answer.text
        package = client.get(f"/api/v1/evidence-packages/{answer.json()['execution_id']}.json", headers=headers)
        assert package.status_code == 200, package.text
        assert package.json()["synthetic_demo"] is True
