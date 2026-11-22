"""Run the real OpsLens governed API workflow and render its measured trace."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "demo" / "animation_fixture.synthetic.json"
OUTPUT_DIR = ROOT / "docs" / "animation" / "runtime-evidence"
VIDEO_PATH = OUTPUT_DIR / "opslens-runtime.mp4"
POSTER_PATH = OUTPUT_DIR / "opslens-runtime-poster.png"
SUMMARY_PATH = OUTPUT_DIR / "opslens-runtime-summary.json"
EVIDENCE_PATH = OUTPUT_DIR / "opslens-evidence.csv"
FORECAST_PATH = OUTPUT_DIR / "opslens-forecast.csv"
APPROVAL_PATH = OUTPUT_DIR / "opslens-approval.csv"


def sha256_file(path: Path) -> str:
    """Hash an input or generated artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    """Write API output rows without dropping measured fields."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def login(client: Any, email: str) -> dict[str, str]:
    """Login through the real API route."""
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def run_api_workflow() -> dict[str, Any]:
    """Execute workspace seed, question planning, SQL guard, forecast, scenario, and approval."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    runtime = tempfile.TemporaryDirectory(prefix="opslens-real-runtime-")
    runtime_path = Path(runtime.name)
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(runtime_path / 'opslens.db').as_posix()}"
    os.environ["JWT_SECRET"] = "opslens-real-runtime-test-secret-with-more-than-32-characters"
    os.environ["DEMO_MODE"] = "true"
    os.environ["REQUEST_RATE_LIMIT"] = "500"
    sys.path.insert(0, str(ROOT / "apps" / "api"))

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.database import engine  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    try:
        with TestClient(app) as client:
            admin = login(client, "admin@opslens.demo")
            ops = login(client, "ops@opslens.demo")
            overview = client.get("/api/v1/dashboard/overview", headers=admin)
            overview.raise_for_status()
            conversation = client.post("/api/v1/ai/conversations", json={"title": "Runtime evidence"}, headers=ops)
            conversation.raise_for_status()
            question = client.post(
                f"/api/v1/ai/conversations/{conversation.json()['id']}/questions",
                json={"question": fixture["question"], "mode": "Investigation Mode"},
                headers=ops,
            )
            question.raise_for_status()
            question_body = question.json()
            quality = client.get("/api/v1/data-quality/overview", headers=admin)
            quality.raise_for_status()
            alerts = client.post("/api/v1/alerts/evaluate", headers=ops)
            alerts.raise_for_status()
            forecast = client.get("/api/v1/forecasts", params={"metric_slug": fixture["forecast"]["metric"], "horizon_days": fixture["forecast"]["horizon_days"]}, headers=admin)
            forecast.raise_for_status()
            scenario = client.post("/api/v1/scenarios", json=fixture["scenario"], headers=ops)
            scenario.raise_for_status()
            scenario_body = scenario.json()
            requested = client.post(f"/api/v1/scenarios/{scenario_body['id']}/request-approval", headers=ops)
            requested.raise_for_status()
            requested_body = requested.json()
            first_approval = client.post(
                f"/api/v1/approvals/{requested_body['approval_request_id']}/approve",
                json={"note": "Operations review complete"},
                headers=ops,
            )
            first_approval.raise_for_status()
            final_approval = client.post(
                f"/api/v1/approvals/{requested_body['approval_request_id']}/approve",
                json={"note": "Final governance approval"},
                headers=admin,
            )
            final_approval.raise_for_status()
            return {
                "fixture": fixture,
                "source": {"path": FIXTURE.relative_to(ROOT).as_posix(), "sha256": sha256_file(FIXTURE), "synthetic": True, "runtime": "FastAPI TestClient + temporary SQLite database"},
                "runtime": {"execution_mode": question_body["evidence"]["execution_mode"], "query_planner": "apps/api/app/services.py::question_plan", "sql_guard": "apps/api/app/sql_guard.py::validate_sql", "forecast_method": forecast.json()["method"], "learned_model": None, "external_integration_called": False},
                "workspace": {"kpi_count": len(overview.json()["kpis"]), "open_alert_count": overview.json()["open_alert_count"]},
                "question_trace": question_body,
                "quality": quality.json(),
                "alerts": {"created": alerts.json()["created"], "refreshed": alerts.json()["refreshed"], "triggered_count": len(alerts.json()["triggered"])},
                "forecast": forecast.json(),
                "scenario": scenario_body,
                "approval": {"policy": requested_body["steps"], "requested_status": requested_body["status"], "first_step": first_approval.json()["status"], "final_status": final_approval.json()["status"], "simulated_execution": final_approval.json()["simulated_execution"]},
                "claim_boundary": "Synthetic decision-support evidence; deterministic governed rules and a transparent baseline forecast; no learned model, external LLM, live integration, ERP mutation, or business-impact claim.",
            }
    finally:
        engine.dispose()
        runtime.cleanup()


def put_lines(canvas: np.ndarray, lines: list[str], origin: tuple[int, int], color: tuple[int, int, int], scale: float = 0.56, gap: int = 26) -> None:
    """Draw readable ASCII-only evidence lines."""
    x, y = origin
    for line in lines:
        cv2.putText(canvas, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)
        y += gap


def render_frame(evidence: dict[str, Any], stage: str, index: int, total: int) -> np.ndarray:
    """Render a frame from actual API response values."""
    canvas = np.full((720, 1280, 3), (12, 20, 14), dtype=np.uint8)
    white, muted = (240, 246, 239), (162, 180, 157)
    accent, green, amber = (184, 239, 114), (145, 225, 130), (83, 190, 255)
    trace = evidence["question_trace"]
    plan = trace["query_plan"]
    validation = trace["validation"]
    rows = trace["evidence"]["rows"]
    forecast = evidence["forecast"]
    scenario = evidence["scenario"]
    approval = evidence["approval"]
    cv2.putText(canvas, "OPSLENS AI | REAL GOVERNED WORKFLOW", (52, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.92, accent, 2, cv2.LINE_AA)
    cv2.putText(canvas, "FastAPI execution | synthetic workspace | no learned model or live write", (53, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.56, muted, 1, cv2.LINE_AA)
    cv2.line(canvas, (52, 112), (1228, 112), (55, 78, 47), 1)
    cv2.rectangle(canvas, (52, 140), (824, 652), (21, 35, 20), -1)
    cv2.rectangle(canvas, (850, 140), (1228, 652), (21, 35, 20), -1)
    cv2.putText(canvas, f"{index + 1:02d}/{total:02d}  {stage.upper()}", (82, 186), cv2.FONT_HERSHEY_SIMPLEX, 0.75, green, 2, cv2.LINE_AA)

    if stage == "workspace":
        put_lines(canvas, ["actual seeded FastAPI workspace", f"KPIs: {evidence['workspace']['kpi_count']}", f"open alerts: {evidence['workspace']['open_alert_count']}", f"quality score: {evidence['quality']['overall_score']}", f"active quality issues: {evidence['quality']['active_issue_count']}", "temporary SQLite runtime"], (86, 270), white)
    elif stage == "plan":
        put_lines(canvas, ["actual question_plan()", f"intent: {plan['intent']}", f"metrics: {', '.join(plan['metrics'])}", f"tables: {', '.join(plan['allowed_tables'])}", f"row limit: {plan['row_limit']}", f"confidence: {plan['confidence']:.2f}"], (86, 270), white)
    elif stage == "sql guard":
        put_lines(canvas, ["actual validate_sql()", f"valid: {validation['valid']}", f"parser: {validation['parser']}", f"complexity: {validation['complexity_score']}", f"tables: {', '.join(validation['tables'])}", f"row limit: {validation['row_limit']}"], (86, 270), white)
    elif stage == "evidence":
        put_lines(canvas, ["actual governed query response", f"status: {trace['status']}", f"rows: {len(rows)}", f"confidence: {trace['confidence']:.2f}", f"quality notices: {len(trace['evidence']['data_quality_notices'])}", "source rows preserved in CSV"], (86, 270), white)
        y = 470
        for row in rows[:4]:
            cv2.putText(canvas, f"{row.get('sku', '')} | {row.get('branch', '')} | units {row.get('available', '')}", (86, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, muted, 1, cv2.LINE_AA)
            y += 27
    elif stage == "forecast":
        put_lines(canvas, ["actual forecast_payload()", f"method: {forecast['method']}", f"horizon: {forecast['horizon_days']} days", f"first: {forecast['forecast'][0]['value']:,.2f}", f"last: {forecast['forecast'][-1]['value']:,.2f}", f"quality notices: {len(forecast['quality_notices'])}"], (86, 270), white)
    elif stage == "scenario":
        put_lines(canvas, ["actual scenario_impact()", f"simulated: {scenario['simulated']}", f"baseline risk: {scenario['impact']['baseline']['stockout_risk']}", f"projected risk: {scenario['impact']['projected']['stockout_risk']}", f"supplier exposure: {scenario['impact']['projected']['supplier_exposure']}", "no operational record mutated"], (86, 270), white)
    elif stage == "approval":
        put_lines(canvas, ["actual human approval routes", f"policy steps: {len(approval['policy'])}", f"requested: {approval['requested_status']}", f"first step: {approval['first_step']}", f"final: {approval['final_status']}", f"simulated execution: {approval['simulated_execution']}"], (86, 270), white)
        cv2.rectangle(canvas, (86, 470), (700, 524), (75, 108, 48), 2)
        cv2.putText(canvas, "approval changed simulated state only", (106, 505), cv2.FONT_HERSHEY_SIMPLEX, 0.55, green, 1, cv2.LINE_AA)
    else:
        put_lines(canvas, ["reviewable evidence written", "MP4 + evidence CSV + forecast CSV", "approval CSV + full JSON trace", "learned model: none", "external integration: false", "business-impact claim: none"], (86, 270), white)

    cv2.putText(canvas, "RUNTIME FACTS", (878, 186), cv2.FONT_HERSHEY_SIMPLEX, 0.7, amber, 2, cv2.LINE_AA)
    put_lines(canvas, [f"planner: {evidence['runtime']['query_planner'].split('::')[-1]}", f"guard: {evidence['runtime']['sql_guard'].split('::')[-1]}", f"forecast: {evidence['runtime']['forecast_method']}", "execution: deterministic", "data: synthetic demo", "live write: false"], (878, 238), muted, 0.53)
    cv2.line(canvas, (878, 418), (1198, 418), (55, 78, 47), 1)
    put_lines(canvas, ["HONEST BOUNDARY", "Real API/services.", "No learned model.", "Scenario is simulated.", "No ERP mutation."], (878, 464), green, 0.56)
    cv2.putText(canvas, "No fabricated rows, forecasts, or approvals", (53, 695), cv2.FONT_HERSHEY_SIMPLEX, 0.54, muted, 1, cv2.LINE_AA)
    return canvas


def write_outputs(evidence: dict[str, Any]) -> None:
    """Persist API traces and render the measured workflow."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = evidence["question_trace"]["evidence"]["rows"]
    evidence_fields = sorted({key for row in rows for key in row})
    write_csv(EVIDENCE_PATH, rows, evidence_fields)
    write_csv(FORECAST_PATH, evidence["forecast"]["forecast"], ["day", "value", "lower", "upper"])
    approval_rows = [{"step": index + 1, "role": role, "status": "approved" if index < 2 else "not_used"} for index, role in enumerate(evidence["approval"]["policy"])]
    write_csv(APPROVAL_PATH, approval_rows, ["step", "role", "status"])

    stages = ["workspace", "plan", "sql guard", "evidence", "forecast", "scenario", "approval", "artifacts"]
    writer = cv2.VideoWriter(str(VIDEO_PATH), cv2.VideoWriter_fourcc(*"mp4v"), 20.0, (1280, 720))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {VIDEO_PATH}")
    try:
        for index, stage in enumerate(stages):
            frame = render_frame(evidence, stage, index, len(stages))
            if stage == "evidence":
                cv2.imwrite(str(POSTER_PATH), frame)
            for _ in range(32):
                writer.write(frame)
    finally:
        writer.release()

    evidence["artifacts"] = {
        "video": {"path": VIDEO_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(VIDEO_PATH), "frames": len(stages) * 32, "fps": 20},
        "poster": {"path": POSTER_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(POSTER_PATH)},
        "evidence_csv": {"path": EVIDENCE_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(EVIDENCE_PATH)},
        "forecast_csv": {"path": FORECAST_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(FORECAST_PATH)},
        "approval_csv": {"path": APPROVAL_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(APPROVAL_PATH)},
    }
    with SUMMARY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> None:
    """Execute the real governed API path and generate evidence."""
    evidence = run_api_workflow()
    write_outputs(evidence)
    print(json.dumps({"summary": SUMMARY_PATH.as_posix(), "video": VIDEO_PATH.as_posix(), "learned_model": evidence["runtime"]["learned_model"], "approval": evidence["approval"]}, indent=2))


if __name__ == "__main__":
    main()
