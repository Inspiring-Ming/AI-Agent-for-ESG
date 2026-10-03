"""L1 -- Client & Experience (Interact).

The interaction boundary through which the analyst engages with the agentic
system. Mirrors the three-step workflow of the existing ESG web interface
(company and year -> metric selection -> computation), but submits it as a
single intent that the agent then plans, rather than as three user-driven
steps.

Boundary (Section IV-B): L1 separates client-facing concerns from the internal
coordination of agentic execution, which belongs to L3. Requests cross the
controlled boundary at L2 before reaching L3.
"""

from typing import Any, Dict


class AnalystInterface:
    RESPONSIBILITY = "L1"

    def __init__(self, access, agent_runtime, trace):
        self._access = access
        self._agent = agent_runtime
        self._trace = trace

    def submit_metric_request(self, token: str, company: str, metric: str,
                              year: str, industry: str,
                              category: str = "Greenhouse Gas Emissions",
                              entitlements=None) -> Dict[str, Any]:
        request = {"company": company, "metric": metric, "year": year,
                   "industry": industry, "category": category}

        self._trace.record("L1", "L2", "request admission", ttype="T1",
                           company=company, metric=metric, year=year)
        try:
            principal = self._access.admit(token, request, entitlements)
        except (PermissionError, ValueError) as e:
            self._trace.record("L2", "L1", "request rejected", ttype="T1",
                               reason=str(e))
            return {"status": "error", "message": str(e)}

        self._trace.record("L2", "L3", "authorized request + identity context",
                           ttype="T2",
                           subject=principal["subject"],
                           trace_id=principal["trace_id"])
        result = self._agent.handle_metric_request(request, principal)

        self._trace.record("L3", "L1", "result and explanation", ttype="T1",
                           value=result.get("value"), unit=result.get("unit"))
        return self.present(self._access.egress(result))

    @staticmethod
    def present(result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("status") != "success":
            return {"status": "error", "message": result.get("error")}
        return {
            "status": "success",
            "headline": f"{result['metric']} — {result['company']} "
                        f"({result['year']}): {result['value']} {result['unit']}",
            "framework": result.get("framework"),
            "explanation": result["explanation"],
            "provenance": result["provenance"],
            "plan": result.get("plan", []),
        }
