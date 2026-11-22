# Real OpsLens runtime evidence

This is the accepted OpsLens animation evidence. It executes the real FastAPI routes against a temporary SQLite workspace and preserves the query plan, SQL guard result, database evidence rows, forecast output, simulated scenario, and two-step approval response. It does not pretend that OpsLens has a learned model where this repository currently uses governed deterministic services.

## Reproduce

```powershell
py -3.12 scripts/generate_real_runtime_video.py
```

The run uses the committed synthetic workspace in demo mode and does not call external integrations. The date-sensitive API-key boundary was also fixed so newly issued keys use current UTC rather than the deterministic seeded-data clock.

## Measured run

- Execution mode: `deterministic_governed_template`.
- Question plan: `stockout_risk`, confidence `0.91`, read-only approved tables, row limit `24`.
- SQL guard: valid, `sqlglot` parser, complexity `4`, tenant filter and bounded result set.
- Evidence: `18` actual seeded branch/SKU rows with risk, available units, supplier, reorder point, and quality notices preserved.
- Forecast: `exponential_smoothing_baseline`, 14-day horizon, first value `1,156,515.24`, last value `1,231,314.73`.
- Scenario: simulated transfer; stockout risk `18` projected to `16`; no operational records mutated.
- Approval: Operations Manager -> Organization Admin; final status `approved`; `simulated_execution=true`.

There is no learned model, external LLM, live ERP write, or business-impact claim in this run. The deterministic planner, SQL guard, rule engine, and transparent baseline are the real executable model boundary for this repository.

## Preserved outputs

| Artifact | Evidence |
| --- | --- |
| [`opslens-runtime.mp4`](runtime-evidence/opslens-runtime.mp4) | Eight-stage 256-frame animation from the real API workflow. |
| [`opslens-runtime-poster.png`](runtime-evidence/opslens-runtime-poster.png) | Poster showing actual evidence rows and the explicit no-learned-model boundary. |
| [`opslens-evidence.csv`](runtime-evidence/opslens-evidence.csv) | All 18 governed evidence rows returned by the question route. |
| [`opslens-forecast.csv`](runtime-evidence/opslens-forecast.csv) | All 14 forecast points and bounds from the real forecast service. |
| [`opslens-approval.csv`](runtime-evidence/opslens-approval.csv) | Both approval policy steps and their recorded statuses. |
| [`opslens-runtime-summary.json`](runtime-evidence/opslens-runtime-summary.json) | Full API responses, SQL validation, quality warnings, scenario assurance, approval state, and artifact hashes. |

The earlier HTML asset at [`apps/web/public/animation/opslens-decision-reel.html`](../../apps/web/public/animation/opslens-decision-reel.html) remains a dependency-free reference UI. Use the runtime-evidence files above for execution evidence.
