from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs" / "animation" / "opslens_decision_sequence.json"
REEL = ROOT / "apps" / "web" / "public" / "animation" / "opslens-decision-reel.html"


def test_opslens_animation_exercises_governed_decision_loop() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_opslens_animation.py"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "apps" / "api")},
        check=True,
        capture_output=True,
        text=True,
    )
    assert "question:" in result.stdout
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reel = REEL.read_text(encoding="utf-8")
    assert manifest["source"]["synthetic"] is True
    assert manifest["question_trace"]["status"] == "completed"
    assert manifest["question_trace"]["validation"]["valid"] is True
    assert manifest["question_trace"]["evidence_row_count"] > 0
    assert manifest["scenario"]["simulated"] is True
    assert manifest["approval"]["first_step"] == "in_review"
    assert manifest["approval"]["final_status"] == "approved"
    assert manifest["approval"]["simulated_execution"] is True
    assert len(manifest["events"]) == 6
    assert "no live erp write" in reel.lower()
