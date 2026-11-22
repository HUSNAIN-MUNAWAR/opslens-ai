# OpsLens governed decision animation enhancement

## Purpose

Make the platform's decision boundary visible: synthetic workspace data becomes a governed query, SQL-validated evidence, transparent forecast/scenario output, and a human approval-controlled recommendation.

## Real service boundary

The generator runs the FastAPI app through `TestClient` with a temporary SQLite database. It exercises the real seed lifecycle, dashboard overview, governed question route, `question_plan`, SQL AST/tenant validation, evidence packaging, data-quality notices, alert evaluator, baseline forecast, scenario impact service, and two-step approval policy.

The artifact is synthetic and simulation-only. It does not call an external LLM, ERP, supplier, pricing, webhook, or live write boundary.

## Reproduce

```bash
python scripts/generate_opslens_animation.py
```

Outputs:

- `docs/animation/opslens_decision_sequence.json` — source checksum, governed query trace, validation, evidence, quality, forecast, scenario, approval, and scene events.
- `apps/web/public/animation/opslens-decision-reel.html` — dependency-free animated reference reel with pause, replay, and stage selection.
