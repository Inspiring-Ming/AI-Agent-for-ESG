"""HTTP adapter onto the existing ESG Metric System's service API
(source: https://github.com/Inspiring-Ming/ESG-Metric-System).

Used by the MCP servers, which expose the system's knowledge graph (L5) and
computation service (L6) to the agent.
"""

from typing import Any, Dict, List
import json
import urllib.parse
import urllib.request

DEFAULT_BASE = "http://localhost:8080"


class EnterpriseSystemUnavailable(RuntimeError):
    """The enterprise system could not be reached through this mechanism."""

    def __init__(self, base: str, detail: str):
        super().__init__(
            f"the enterprise system at {base} is unreachable ({detail}).\n"
            f"  Start the stack with `docker compose up -d`, or inspect the "
            f"recorded results in output/")


class HttpAdapter:
    """Calls the deployed ESG service API over HTTP."""

    mechanism = "deployed service API (HTTP/REST)"

    def __init__(self, base: str = DEFAULT_BASE, timeout: int = 60):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            raise EnterpriseSystemUnavailable(self.base, f"{type(e).__name__}: {e}")

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            raise EnterpriseSystemUnavailable(self.base, f"{type(e).__name__}: {e}")

    # -- L5 knowledge-graph retrieval (CQ1-CQ7) ---------------------------
    def frameworks(self, industry: str) -> Dict[str, Any]:
        d = self._get(f"/api/KGservice/industries/{urllib.parse.quote(industry)}/frameworks")
        rows = d.get("data") or []
        top = rows[0] if rows else {}
        return {"framework": top.get("name"), "framework_id": top.get("id")}

    def categories(self, industry: str, framework_id: str) -> Dict[str, Any]:
        d = self._get(f"/api/KGservice/frameworks/{urllib.parse.quote(framework_id)}/categories",
                      industry=industry)
        return {"categories": [c.get("category_name") for c in d.get("data") or []]}

    def metrics(self, industry: str, category: str) -> Dict[str, Any]:
        d = self._get(f"/api/KGservice/categories/{urllib.parse.quote(category)}/metrics",
                      industry=industry)
        return {"metrics": d.get("data") or []}

    def models(self, industry: str, metric: str) -> Dict[str, Any]:
        return self._get(f"/api/KGservice/metrics/{urllib.parse.quote(metric)}/models",
                         industry=industry)

    # -- L6 executable capability -----------------------------------------
    def calculate(self, industry: str, company: str, year: str,
                  metrics: List[str]) -> Dict[str, Any]:
        d = self._post("/api/CSservice/calculate",
                       {"industry": industry, "company_name": company,
                        "year": year, "metrics": metrics})
        rows = d.get("calculation_results") or []
        return rows[0] if rows else {"status": "error",
                                     "error": d.get("message", "no result")}

    def companies(self, industry: str) -> List[str]:
        d = self._get("/api/DRservice/companies/all")
        return (d.get("companies_by_industry") or {}).get(industry, [])

    def health(self) -> bool:
        try:
            self._get("/api/DRservice/companies/all")
            return True
        except Exception:
            return False
