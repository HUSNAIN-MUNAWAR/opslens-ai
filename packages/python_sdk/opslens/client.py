from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request


@dataclass
class OpsLensClient:
    """Small standard-library client for the OpsLens AI deterministic demo API."""

    base_url: str = "http://localhost:8000"
    access_token: str | None = None
    api_key: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "X-Request-ID": "sdk-demo"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload or {}).encode() if method in {"POST", "PATCH"} else None
        req = request.Request(f"{self.base_url.rstrip('/')}{path}", data=data, method=method, headers=self._headers())
        with request.urlopen(req, timeout=15) as response:  # noqa: S310 - local demo client
            raw = response.read().decode()
            return json.loads(raw) if raw else None

    def authenticate(self, email: str = "admin@opslens.demo", password: str = "DemoPass123!") -> Any:
        payload = self._json("POST", "/api/v1/auth/login", {"email": email, "password": password})
        self.access_token = payload["access_token"]
        return payload

    def dashboard(self) -> Any:
        return self._json("GET", "/api/v1/dashboard/overview")

    def alerts(self) -> Any:
        return self._json("GET", "/api/v1/alerts")

    def create_investigation(self, title: str, category: str = "operations") -> Any:
        return self._json("POST", "/api/v1/investigations", {"title": title, "category": category, "priority": "high", "severity": "high"})

    def ask_copilot(self, question: str) -> Any:
        conversation = self._json("POST", "/api/v1/ai/conversations", {"title": "SDK governed question"})
        return self._json("POST", f"/api/v1/ai/conversations/{conversation['id']}/questions", {"question": question})

    def create_scenario(self, name: str, adjustments: list[dict[str, Any]]) -> Any:
        return self._json("POST", "/api/v1/scenarios", {"name": name, "adjustments": adjustments})

    def create_report(self, name: str, report_type: str = "Executive Operations Brief") -> Any:
        return self._json("POST", "/api/v1/reports", {"name": name, "report_type": report_type})

    def imports(self) -> Any:
        return self._json("GET", "/api/v1/ingestion/jobs")

    def data_quality(self) -> Any:
        return self._json("GET", "/api/v1/data-quality/overview")
