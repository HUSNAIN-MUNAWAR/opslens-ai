"""Generate a deterministic OpsLens governed-decision reference reel."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "demo" / "animation_fixture.synthetic.json"
MANIFEST = ROOT / "docs" / "animation" / "opslens_decision_sequence.json"
REEL = ROOT / "apps" / "web" / "public" / "animation" / "opslens-decision-reel.html"


def _login(client, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def build_manifest() -> dict[str, object]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    runtime = tempfile.TemporaryDirectory(prefix="opslens-animation-")
    runtime_path = Path(runtime.name)
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(runtime_path / 'opslens.db').as_posix()}"
    os.environ["JWT_SECRET"] = "opslens-animation-test-secret-with-more-than-32-characters"
    os.environ["DEMO_MODE"] = "true"
    os.environ["REQUEST_RATE_LIMIT"] = "500"
    sys.path.insert(0, str(ROOT / "apps" / "api"))

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    from app.database import engine  # noqa: PLC0415

    try:
        with TestClient(app) as client:
            admin = _login(client, "admin@opslens.demo")
            ops = _login(client, "ops@opslens.demo")
            overview = client.get("/api/v1/dashboard/overview", headers=admin)
            conversation = client.post("/api/v1/ai/conversations", json={"title": "Animation trace"}, headers=ops)
            conversation.raise_for_status()
            question = client.post(
                f"/api/v1/ai/conversations/{conversation.json()['id']}/questions",
                json={"question": fixture["question"], "mode": "Investigation Mode"},
                headers=ops,
            )
            question.raise_for_status()
            question_body = question.json()
            quality = client.get("/api/v1/data-quality/overview", headers=admin)
            alerts = client.post("/api/v1/alerts/evaluate", headers=ops)
            forecast = client.get(
                "/api/v1/forecasts",
                params={"metric_slug": fixture["forecast"]["metric"], "horizon_days": fixture["forecast"]["horizon_days"]},
                headers=admin,
            )
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

            source_bytes = FIXTURE.read_bytes()
            forecast_body = forecast.json()
            quality_body = quality.json()
            alerts_body = alerts.json()
            events = [
                {"id": "workspace", "short": "Seed", "title": "Synthetic workspace is loaded", "detail": "The real FastAPI lifespan seeds synthetic organizations, products, sales, inventory, suppliers, quality issues, and governance policies.", "metric": f"{len(overview.json()['kpis'])} KPIs · {overview.json()['open_alert_count']} open alerts", "status": "ready"},
                {"id": "plan", "short": "Plan", "title": "The question becomes a certified plan", "detail": "The governed route selects stockout metrics, approved tables, tenant scope, dimensions, and a bounded row limit.", "metric": f"{question_body['query_plan']['intent']} · {question_body['query_plan']['row_limit']} row limit", "status": question_body["status"]},
                {"id": "guard", "short": "Guard", "title": "SQL passes AST and tenant checks", "detail": "Read-only SQL is validated before execution, with organization scope, allowlists, complexity, and row limits recorded.", "metric": f"valid {question_body['validation']['valid']} · parser {question_body['validation']['parser']}", "status": "validated"},
                {"id": "evidence", "short": "Evidence", "title": "Evidence and quality warnings are packaged", "detail": "The response carries synthetic rows, source tables, confidence, and active data-quality notices into the answer boundary.", "metric": f"{len(question_body['evidence']['rows'])} rows · confidence {question_body['confidence']:.2f}", "status": "grounded"},
                {"id": "simulate", "short": "Simulate", "title": "Forecast and scenario effects stay simulated", "detail": "A transparent baseline and inventory-transfer scenario estimate impact without mutating ERP, inventory, supplier, or pricing records.", "metric": f"{forecast_body['method']} · {scenario_body['impact']['projected']['stockout_risk']} projected risk", "status": "simulated"},
                {"id": "approve", "short": "Approve", "title": "Human approval completes the workflow", "detail": "The operations manager completes step one and the organization admin completes step two; only the simulated recommendation changes state.", "metric": f"{first_approval.json()['status']} → {final_approval.json()['status']} · {len(requested_body['steps'])} steps", "status": final_approval.json()["status"]},
            ]
            return {
                "schema_version": "1.0",
                "fixture": fixture["fixture_id"],
                "source": {"path": FIXTURE.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(source_bytes).hexdigest(), "synthetic": True, "runtime": "FastAPI TestClient + temporary SQLite database"},
                "model": {"execution_mode": question_body["evidence"]["execution_mode"], "query_planner": "apps/api/app/services.py::question_plan", "sql_guard": "apps/api/app/sql_guard.py::validate_sql", "forecast": forecast_body["method"], "claim_boundary": "Synthetic decision-support evidence; no external LLM, live integration, ERP mutation, or business-impact claim."},
                "question_trace": {"status": question_body["status"], "confidence": question_body["confidence"], "answer": question_body["answer"], "validation": question_body["validation"], "query_plan": question_body["query_plan"], "evidence_row_count": len(question_body["evidence"]["rows"]), "quality_warning_count": len(question_body["evidence"]["data_quality_notices"]), "synthetic": question_body["evidence"]["synthetic"]},
                "quality": {"overall_score": quality_body["overall_score"], "active_issue_count": quality_body["active_issue_count"], "critical_source_count": quality_body["critical_source_count"]},
                "alerts": {"created": alerts_body["created"], "refreshed": alerts_body["refreshed"], "triggered_count": len(alerts_body["triggered"])},
                "forecast": {"method": forecast_body["method"], "horizon_days": forecast_body["horizon_days"], "first_value": forecast_body["forecast"][0]["value"], "last_value": forecast_body["forecast"][-1]["value"], "quality_notice_count": len(forecast_body["quality_notices"])},
                "scenario": {"simulated": scenario_body["simulated"], "baseline": scenario_body["impact"]["baseline"], "projected": scenario_body["impact"]["projected"], "assurance": scenario_body["impact"]["assurance"]},
                "approval": {"policy": requested_body["steps"], "requested_status": requested_body["status"], "first_step": first_approval.json()["status"], "final_status": final_approval.json()["status"], "simulated_execution": final_approval.json()["simulated_execution"]},
                "events": events,
            }
    finally:
        engine.dispose()
        runtime.cleanup()


def render_reel(manifest: dict[str, object]) -> str:
    payload = json.dumps(manifest, indent=2, sort_keys=True).replace("</", "<\\/")
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OpsLens — Governed decision reference reel</title><style>
:root{color-scheme:dark;--ink:#f0f5f3;--muted:#9db3ae;--line:#294b48;--accent:#b8ef72}*{box-sizing:border-box}body{margin:0;min-width:320px;background:radial-gradient(circle at 84% 0,#304820 0,#101b13 48%,#070b09 100%);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:42px 28px 34px}.eyebrow{color:var(--accent);font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}h1{max-width:850px;margin:8px 0 10px;font-size:clamp(28px,5vw,54px);line-height:1.02;letter-spacing:-.045em}.lede{max-width:800px;margin:0;color:var(--muted);font-size:17px}.stage{margin-top:34px;overflow:hidden;border:1px solid var(--line);border-radius:22px;background:linear-gradient(145deg,rgba(36,66,36,.94),rgba(8,15,10,.98));box-shadow:0 22px 60px rgba(0,0,0,.3)}svg{display:block;width:100%;height:auto;min-height:300px}.route{fill:none;stroke:#526b4b;stroke-width:4;stroke-linecap:round;stroke-dasharray:7 12}.station circle{fill:#0a1610;stroke:#69805a;stroke-width:3;transition:fill .25s,stroke .25s,transform .25s;transform-origin:center}.station text{fill:#adc0a8;font-size:14px;text-anchor:middle}.station .index{fill:#e4f4d9;font-size:13px;font-weight:800}.station.active circle{fill:#42621e;stroke:var(--accent);transform:scale(1.1)}.station.active text{fill:var(--ink)}.station.done circle{fill:#2d4827;stroke:#9abf70}.token{fill:var(--accent);stroke:#f1ffd9;stroke-width:3;filter:drop-shadow(0 0 12px rgba(184,239,114,.65))}.token-label{fill:#1b2b0b;font-size:10px;font-weight:900;text-anchor:middle}.panel{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:end;padding:22px 24px 24px;border-top:1px solid var(--line)}.panel h2{margin:0 0 3px;font-size:24px;letter-spacing:-.02em}.panel p{margin:0;color:var(--muted)}.metric{color:var(--accent);font-size:13px;font-weight:800;text-align:right}.controls{display:flex;gap:8px;margin-top:16px}button{border:1px solid #718f5f;border-radius:999px;padding:9px 15px;background:#29451f;color:var(--ink);font:inherit;cursor:pointer}button:hover,button:focus-visible{border-color:var(--accent);outline:2px solid rgba(184,239,114,.35);outline-offset:2px}.timeline{display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:7px;margin-top:18px}.timeline button{min-height:60px;border-radius:12px;padding:8px;color:var(--muted);text-align:left;font-size:12px}.timeline button[aria-current=step]{border-color:var(--accent);background:#3a5b24;color:var(--ink)}.timeline strong{display:block;color:inherit;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.disclaimer{margin-top:20px;color:var(--muted);font-size:12px}@media(max-width:760px){main{padding:28px 16px}.panel{grid-template-columns:1fr}.metric{text-align:left}.timeline{grid-template-columns:repeat(2,minmax(0,1fr))}svg{min-height:420px}}@media(prefers-reduced-motion:reduce){*,*::before,*:after{transition-duration:.01ms!important;animation-duration:.01ms!important;animation-iteration-count:1!important}}
</style></head><body><main><div class="eyebrow">OpsLens AI · production reference reel</div><h1>Evidence enters a governed decision loop.</h1><p class="lede">Synthetic operations data becomes a bounded query, validated evidence, transparent simulation, and a two-step human approval — without mutating a live system.</p><section class="stage" aria-label="Animated governed decision sequence"><svg viewBox="0 0 1210 390" role="img" aria-labelledby="diagram-title diagram-description"><title id="diagram-title">OpsLens governed decision stages</title><desc id="diagram-description">A token travels through seeded workspace, query planning, SQL guard, evidence, simulation, and approval.</desc><path class="route" d="M80 190 C220 82 360 82 510 190 S800 298 1130 100"></path><g id="stations"></g><g aria-hidden="true"><circle id="token" class="token" cx="80" cy="190" r="22"></circle><text id="token-label" class="token-label" x="80" y="194">RUN</text></g></svg><div class="panel" aria-live="polite"><div><h2 id="event-title"></h2><p id="event-detail"></p></div><div id="event-metric" class="metric"></div></div></section><div class="controls"><button id="toggle" type="button">Pause</button><button id="replay" type="button">Replay</button></div><div id="timeline" class="timeline" role="list" aria-label="Animation stages"></div><p class="disclaimer">Synthetic workspace · deterministic governance services · simulation only · no live ERP write.</p><script>
const sequence=__SEQUENCE__;const events=sequence.events;const points=[[80,190],[270,96],[460,96],[650,190],[840,284],[1040,284]];const stations=document.getElementById('stations'),timeline=document.getElementById('timeline'),token=document.getElementById('token'),tokenLabel=document.getElementById('token-label'),title=document.getElementById('event-title'),detail=document.getElementById('event-detail'),metric=document.getElementById('event-metric'),toggle=document.getElementById('toggle');let current=0,started=performance.now(),playing=!window.matchMedia('(prefers-reduced-motion: reduce)').matches;const duration=1900;points.forEach((point,index)=>{const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.classList.add('station');group.innerHTML=`<circle cx="${point[0]}" cy="${point[1]}" r="30"></circle><text class="index" x="${point[0]}" y="${point[1]+5}">${index+1}</text><text x="${point[0]}" y="${point[1]+57}">${events[index].short}</text>`;stations.appendChild(group)});events.forEach((event,index)=>{const item=document.createElement('button');item.type='button';item.setAttribute('role','listitem');item.innerHTML=`<strong>${String(index+1).padStart(2,'0')} · ${event.status}</strong>${event.title}`;item.addEventListener('click',()=>{current=index;started=performance.now();playing=false;toggle.textContent='Play';render(0)});timeline.appendChild(item)});function render(progress){const next=(current+1)%points.length,from=points[current],to=points[next],x=from[0]+(to[0]-from[0])*progress,y=from[1]+(to[1]-from[1])*progress;token.setAttribute('cx',x);token.setAttribute('cy',y);tokenLabel.setAttribute('x',x);tokenLabel.setAttribute('y',y+4);title.textContent=events[current].title;detail.textContent=events[current].detail;metric.textContent=events[current].metric;document.querySelectorAll('.station').forEach((node,index)=>{node.classList.toggle('active',index===current);node.classList.toggle('done',index<current)});timeline.querySelectorAll('button').forEach((node,index)=>node.setAttribute('aria-current',index===current?'step':'false'))}function animate(now){if(playing){const progress=Math.min(1,(now-started)/duration);render(progress);if(progress>=1){current=(current+1)%events.length;started=now}}else{render(0)}requestAnimationFrame(animate)}toggle.addEventListener('click',()=>{playing=!playing;started=performance.now();toggle.textContent=playing?'Pause':'Play'});document.getElementById('replay').addEventListener('click',()=>{current=0;started=performance.now();playing=true;toggle.textContent='Pause'});render(0);requestAnimationFrame(animate);
</script></main></body></html>
""".replace("__SEQUENCE__", payload)


def main() -> None:
    manifest = build_manifest()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    REEL.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REEL.write_text(render_reel(manifest), encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")
    print(f"wrote {REEL.relative_to(ROOT)}")
    print(f"question: {manifest['question_trace']['status']} · SQL valid {manifest['question_trace']['validation']['valid']}")
    print(f"approval: {manifest['approval']['first_step']} -> {manifest['approval']['final_status']}")


if __name__ == "__main__":
    main()
