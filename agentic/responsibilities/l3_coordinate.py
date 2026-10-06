"""L3 -- Agent & Workflow Orchestration (Coordinate).

A goal-directed agent whose next action is chosen by a language model. Each
iteration L3 asks L4 for the next decision; the model either requests a tool
or ends its turn. L3 then routes each requested tool to the responsibility that
owns it and returns the observation to the model:

    discover_metrics, get_metric_definition  ->  L5 (T4)
    compute_metric                           ->  L6 (T5)
    every model call                          ->  L4 (T3)

L3 never executes a capability itself and never takes a metric value from
model text: the reported value is the one returned by L6. Guardrails owned by
L3: a bound on model calls, a fixed request context (company, year, industry,
category) that the model cannot change, and a grounding check that every
number in the final answer occurs in what L5/L6 returned.

Each exchange is recorded as an interaction occurrence, and each step of the
plan records which occurrences it produced, so the run can be inspected.
"""

import json
import re
from typing import Any, Dict, List, Optional

SYSTEM = """You are an ESG reporting agent working inside an enterprise system.
You answer an analyst's request about one company, one reporting year and one
ESG category, using only the tools provided.

Rules:
- Use discover_metrics to see which metrics the category contains, then decide
  which metric satisfies the request.
- Use get_metric_definition before computing, to learn how the metric is
  calculated.
- Use compute_metric to obtain any value. Never calculate, estimate or invent a
  number yourself; every number you state must come from a tool result.
- If no discovered metric satisfies the request, do not compute anything; say
  so and stop.
- Before each tool call, write one short sentence giving your reason.
- When finished: if an explanation was requested, explain the result in two or
  three sentences using only values from tool results; otherwise reply with
  just the metric name, value and unit."""

TOOLS = [
    {"name": "discover_metrics",
     "description": "List the ESG metrics contained in the request's reporting "
                    "category, with the calculation method each requires.",
     "input_schema": {"type": "object", "properties": {},
                      "required": [], "additionalProperties": False},
     "strict": True},
    {"name": "get_metric_definition",
     "description": "Get a metric's definition, calculation method, "
                    "calculation model, required inputs and provenance.",
     "input_schema": {"type": "object",
                      "properties": {"metric": {"type": "string",
                                                "description": "Metric name "
                                                "exactly as discovered"}},
                      "required": ["metric"], "additionalProperties": False},
     "strict": True},
    {"name": "compute_metric",
     "description": "Compute a metric for the request's company and year "
                    "with the enterprise computation service.",
     "input_schema": {"type": "object",
                      "properties": {"metric": {"type": "string",
                                                "description": "Metric name "
                                                "exactly as discovered"}},
                      "required": ["metric"], "additionalProperties": False},
     "strict": True},
]

_NUM = re.compile(r"(?<![A-Za-z])\d[\d,]*\.?\d*")


def _numbers(text: str) -> List[float]:
    out = []
    for tok in _NUM.findall(text or ""):
        try:
            out.append(float(tok.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


class AgentRuntime:
    RESPONSIBILITY = "L3"

    def __init__(self, ground, infer, act, trace, max_model_calls: int = 8):
        self._ground = ground
        self._infer = infer
        self._act = act
        self._trace = trace
        self._max_calls = max_model_calls
        self.working_context: Dict[str, Any] = {}

    # ------------------------------------------------------------------ util
    def _rec(self, *args, **kwargs) -> int:
        return self._trace.record(*args, **kwargs).seq

    def _goal_text(self, goal: Dict[str, Any]) -> str:
        want = (" and ".join(f"the metric {m}" for m in goal["metrics"])
                if goal.get("metrics") else
                f"the metric {goal['metric']}" if goal.get("metric") else
                "a metric that requires a calculation model"
                if goal.get("prefer_method") == "calculation_model" else
                "the most relevant metric")
        expl = ("Explain the result." if goal.get("explain")
                else "Do not explain; report only the result.")
        return (f"Company: {goal['company']}. Reporting year: {goal['year']}. "
                f"Industry: {goal['industry']}. Category: {goal['category']}.\n"
                f"Request: report {want} in this category. {expl}")

    # ------------------------------------------------------------- execution
    def _run_tool(self, name: str, args: Dict[str, Any],
                  principal: Optional[Dict[str, Any]]) -> (Dict, List[int]):
        wc, goal = self.working_context, self.working_context["goal"]
        tid = (principal or {}).get("trace_id")
        seqs: List[int] = []

        if name == "discover_metrics":
            seqs.append(self._rec("L3", "L5", "capability discovery", ttype="T4",
                                  category=goal["category"], trace_id=tid))
            found = self._ground.metrics_in_category(goal["industry"],
                                                     goal["category"])
            seqs.append(self._rec("L5", "L3", "discovered metrics", ttype="T4",
                                  count=len(found)))
            wc["candidates"] = found
            return {"metrics": [{"name": m["name"],
                                 "calculation_method": m.get("calculation_method"),
                                 "unit": m.get("unit")} for m in found]}, seqs

        if name == "get_metric_definition":
            seqs.append(self._rec("L3", "L5", "context retrieval", ttype="T4",
                                  metric=args["metric"], trace_id=tid))
            ctx = self._ground.assemble_metric_context(
                goal["industry"], goal["category"], args["metric"])
            cqs = len(ctx.get("provenance", {}).get("competency_questions", []))
            seqs.append(self._rec("L5", "L3", "grounded context", ttype="T4",
                                  method=ctx.get("measurement_method"),
                                  model=ctx.get("calculation_model"),
                                  competency_questions=cqs))
            wc["metric_context"] = ctx
            return {k: ctx.get(k) for k in (
                "metric", "framework", "measurement_method",
                "calculation_model", "model_equation", "required_inputs",
                "unit")}, seqs

        if name == "compute_metric":
            seqs.append(self._rec("L3", "L6", "action intent", ttype="T5",
                                  metric=args["metric"]))
            res = self._act.invoke(
                "compute_metric", principal=principal, metric=args["metric"],
                company=goal["company"], year=goal["year"],
                industry=goal["industry"])
            seqs.append(self._rec("L6", "L3", "observation", ttype="T5",
                                  status=res.get("status"),
                                  value=res.get("display_value")))
            wc["l6_invocations"] = wc.get("l6_invocations", 0) + 1
            if res.get("status") == "success":
                wc["computation"] = res
                wc["selected"] = args["metric"]
                wc.setdefault("computations", []).append(
                    {"metric": args["metric"], **res})
            return res, seqs

        raise ValueError(f"unregistered tool: {name}")

    # ------------------------------------------------------------------ loop
    def pursue(self, goal: Dict[str, Any],
               principal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.working_context = {"goal": dict(goal), "principal": principal,
                                "model_calls": 0, "plan": [],
                                "status": "running"}
        wc = self.working_context
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": self._goal_text(goal)}]
        final_text = ""

        while wc["status"] == "running":
            if wc["model_calls"] >= self._max_calls:
                wc["status"], wc["error"] = "failed", (
                    f"execution exceeded {self._max_calls} model calls")
                break
            wc["model_calls"] += 1

            s1 = self._rec("L3", "L4", "inference request", ttype="T3",
                           provider=self._infer.provider_name)
            out = self._infer.step(SYSTEM, messages, TOOLS)
            resp = out["response"]
            s2 = self._rec("L4", "L3", "inference result", ttype="T3",
                           contract=out["contract"])
            # keep the assistant turn verbatim (thinking blocks included)
            messages.append({"role": "assistant", "content": resp.content})

            text = " ".join(b.text for b in resp.content
                            if b.type == "text").strip()
            calls = [b for b in resp.content if b.type == "tool_use"]
            wc["plan"].append({"action": "decide", "why": text or
                               ("chose " + ", ".join(c.name for c in calls)
                                if calls else "finished"),
                               "seqs": [s1, s2]})

            if out["contract"] != "success":
                wc["status"], wc["error"] = "failed", (
                    f"inference contract violation: {out['contract']}")
                break

            if not calls:                      # model ended its turn
                final_text = text
                wc["plan"][-1]["action"] = "answer"
                wc["status"] = "success" if wc.get("computation") \
                    else "unsatisfiable"
                break

            results = []
            for c in calls:
                try:
                    result, seqs = self._run_tool(c.name, dict(c.input),
                                                  principal)
                    results.append({"type": "tool_result", "tool_use_id": c.id,
                                    "content": json.dumps(result, default=str)})
                except PermissionError as e:
                    seqs = []
                    results.append({"type": "tool_result", "tool_use_id": c.id,
                                    "content": f"Refused: {e}",
                                    "is_error": True})
                wc["plan"].append({"action": c.name,
                                   "why": json.dumps(dict(c.input)),
                                   "seqs": seqs})
            messages.append({"role": "user", "content": results})

        wc["final_text"] = final_text
        return self._result(final_text)

    # ---------------------------------------------------------------- result
    def _grounding(self, text: str) -> Dict[str, Any]:
        """Every number in the answer must occur in what L5/L6 returned."""
        wc = self.working_context
        allowed = {float(wc["goal"]["year"]), float(len(wc.get("candidates", [])))}
        for comp in wc.get("computations", []):
            for src in (comp.get("value"), comp.get("display_value")):
                try:
                    allowed.add(float(str(src).replace(",", "")))
                except (TypeError, ValueError):
                    pass
            for v in ((comp.get("provenance") or {}).get("inputs") or {}).values():
                try:
                    allowed.add(float(v))
                except (TypeError, ValueError):
                    pass
        found = [n for n in _numbers(text) if n >= 10 or n != int(n)]

        def ok(n):
            return any(abs(n - a) <= max(0.006, 0.0051 * abs(a))
                       or round(a, 1) == n or round(a, 2) == n
                       or round(a) == n for a in allowed)
        bad = [n for n in found if not ok(n)]
        return {"numbers": found, "unsupported": bad, "grounded": not bad}

    def _result(self, final_text: str) -> Dict[str, Any]:
        wc = self.working_context
        comp = wc.get("computation") or {}
        ctx = wc.get("metric_context") or {}
        plan = [{"action": p["action"], "why": p["why"], "seqs": p["seqs"]}
                for p in wc["plan"]]
        base = {"status": wc["status"], "plan": plan,
                "model_calls": wc["model_calls"],
                "l6_invocations": wc.get("l6_invocations", 0),
                "answer": final_text, "grounding": self._grounding(final_text),
                "selection_rationale": (
                    f"{len(wc.get('candidates', []))} candidates; selected "
                    f"'{wc['selected']}'" if wc.get("selected") else
                    "no candidate selected")}
        if wc["status"] != "success":
            base["error"] = wc.get("error") or final_text
            return base
        base.update({
            "metric": wc["selected"], "company": wc["goal"]["company"],
            "year": wc["goal"]["year"], "framework": ctx.get("framework"),
            "measurement_method": ctx.get("measurement_method"),
            "value": comp.get("display_value"),
            "values": {c["metric"]: c.get("display_value")
                       for c in wc.get("computations", [])},
            "unit": comp.get("unit") or ctx.get("unit"),
            "explanation": final_text if wc["goal"].get("explain") else None,
            "provenance": {"knowledge_graph": ctx.get("provenance"),
                           "computation": comp.get("provenance"),
                           "inference_provider": self._infer.provider_name,
                           "trace_id": (wc.get("principal") or {}).get(
                               "trace_id")},
        })
        return base
