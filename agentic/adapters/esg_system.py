"""Adapters onto the existing ESG Metric System.

Two interchangeable adapters expose the same interface, so the instantiation
can run against either the deployed service API or the local Python services
without any change to L3, L5 or L6:

  HttpAdapter   -- the deployed OntoMetric service API
                   (https://esgalaxy.com.ngrok.dev, source:
                    https://github.com/Inspiring-Ming/ESG-Metric-System)
  LocalAdapter  -- the same services imported in-process

This is the realization-mechanism distinction the architecture draws: the
responsibility boundary is fixed, the mechanism that realises it is not.
"""

from typing import Any, Dict, List
import json
import urllib.parse
import urllib.request

DEPLOYED_BASE = "https://esgalaxy.com.ngrok.dev"


class HttpAdapter:
    """Calls the deployed ESG service API over HTTP."""

    mechanism = "deployed service API (HTTP/REST)"

    def __init__(self, base: str = DEPLOYED_BASE, timeout: int = 60):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    # -- L5 knowledge-graph retrieval (CQ1-CQ7) ---------------------------
    def frameworks(self, industry: str) -> Dict[str, Any]:
        d = self._get(f"/api/KGservice/industries/{urllib.parse.quote(industry)}/frameworks")
        rows = d.get("data") or []
        return {"framework": (rows[0].get("name") or
                              rows[0].get("framework_name") or
                              rows[0].get("framework")) if rows else None,
                "raw": rows}

    def categories(self, industry: str, framework: str) -> Dict[str, Any]:
        d = self._get(f"/api/KGservice/frameworks/{urllib.parse.quote(framework)}/categories",
                      industry=industry)
        return {"categories": d.get("data") or []}

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


class LocalAdapter:
    """Imports the ESG services in-process (same interface as HttpAdapter)."""

    mechanism = "in-process Python services"

    def __init__(self, esg_root: str):
        import os
        import sys
        sys.path.insert(0, esg_root)
        os.chdir(esg_root)
        from src.services.data_retrieval_service import DataRetrievalService
        from src.services.knowledge_graph_service import KnowledgeGraphService
        from src.services.calculation_service import CalculationService
        self._data = DataRetrievalService()
        self._kg = KnowledgeGraphService(self._data)
        self._calc = CalculationService(self._data, self._kg)

    def frameworks(self, industry: str) -> Dict[str, Any]:
        d = self._kg.cq1_reporting_framework_by_industry(industry)
        return {"framework": (d.get("framework_name") or d.get("framework")
                              or d.get("name")), "raw": d}

    def categories(self, industry: str, framework: str) -> Dict[str, Any]:
        d = self._kg.cq2_categories_by_framework(industry)
        return {"categories": d.get("categories") or []}

    def metrics(self, industry: str, category: str) -> Dict[str, Any]:
        try:
            d = self._kg.cq3_metrics_by_category(industry, category)
        except Exception:
            return {"metrics": []}
        return {"metrics": d.get("metrics") or []}

    def models(self, industry: str, metric: str) -> Dict[str, Any]:
        d = self._kg.cq4_metric_calculation_method(industry, metric)
        model = {"model_name": d.get("model_name") or d.get("calculation_model"),
                 "model_equation": (d.get("model_equation")
                                    or d.get("model_description")),
                 "input_metrics": d.get("input_metrics", [])}
        return {"measurement_method": d.get("measurement_method"),
                "models": [model] if model["model_name"] or
                          d.get("measurement_method") else []}

    def calculate(self, industry: str, company: str, year: str,
                  metrics: List[str]) -> Dict[str, Any]:
        return self._calc.calculate(metrics[0], company, year, industry)

    def companies(self, industry: str) -> List[str]:
        return self._data.get_companies_by_industry(industry)

    def health(self) -> bool:
        return True
