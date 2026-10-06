"""L3 -- Agent & Workflow Orchestration (Coordinate).

An ESG portfolio analyst agent. Given a portfolio's holdings and an analyst's
question, a language model chooses each next step; L3 routes every step to the
responsibility that owns it and returns the observation to the model:

    discover_metrics, get_metric_definition         -> L5 (T4)
    compute_metric, portfolio_intensity,
    check_trade, submit_trade                       -> L6 (T5)
    every model decision                            -> L4 (T3)

L3 never executes a capability itself and never takes a value from model text.
Execution constraints owned by L3:
  * the model may act only on the request's fund, holdings and years;
  * holdings and their intensities passed to portfolio and trade tools are
    assembled by L3 from L6 results, never supplied by the model;
  * number check: every number in the final answer must occur in the request
    or in a result returned by L5 or L6; a draft that fails is returned to the
    model once for revision;
  * a bound on model calls.

Each exchange is recorded as an interaction occurrence, and each plan step
records the occurrences it produced.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

SYSTEM = """You are an ESG portfolio analyst assistant at an asset manager.
You answer a portfolio manager's questions about the carbon profile of their
fund, and check proposed trades against the fund's ESG mandate, using only the
tools provided.

Rules:
- Use discover_metrics and get_metric_definition to identify which metric in
  the category measures carbon intensity relative to revenue, and how it is
  calculated.
- Use compute_metric for each holding and each year the question needs.
- Use portfolio_intensity for the portfolio-level figure of each year needed.
- Never calculate, estimate or invent a number yourself; every number you state
  must come from the request or a tool result.
- Holdings whose metric cannot be computed must be reported with the reason
  the tool gave; do not substitute values.
- For a proposed trade, compute the intensities it needs first, then
  use check_trade. Express a trade as changes in percentage points of weight
  over current holdings that sum to zero (buys positive, sells negative).
- Call submit_trade only if the manager asks to submit, place or execute the
  trade. If the check shows a breach, submit only if the manager asks for an
  override, and give their reason as the justification; such a trade is held
  until a compliance officer approves it. Otherwise explain the breach and, if
  asked, suggest a compliant alternative verified with check_trade.
- If the question needs information the tools cannot provide (for example
  share prices, returns, forecasts or buy/sell recommendations), say what
  cannot be answered and do not
  call tools that do not help.
- Before each set of tool calls, write one short sentence giving your reason.
- Finish with a concise answer of at most six sentences."""

_METRIC = {"type": "string", "description": "Metric name exactly as discovered"}
_YEAR = {"type": "string", "description": "Four-digit reporting year"}
_TRADES = {"type": "array",
           "description": "Weight changes over current holdings, summing to 0",
           "items": {"type": "object",
                     "properties": {"company": {"type": "string"},
                                    "change_pct_points": {"type": "number"}},
                     "required": ["company", "change_pct_points"],
                     "additionalProperties": False}}
TOOLS = [
    {"name": "discover_metrics",
     "description": "List the ESG metrics in the request's reporting category, "
                    "with the calculation method each requires.",
     "input_schema": {"type": "object", "properties": {}, "required": [],
                      "additionalProperties": False},
     "strict": True},
    {"name": "get_metric_definition",
     "description": "Get a metric's definition, calculation method, "
                    "calculation model, required inputs and provenance.",
     "input_schema": {"type": "object", "properties": {"metric": _METRIC},
                      "required": ["metric"], "additionalProperties": False},
     "strict": True},
    {"name": "compute_metric",
     "description": "Compute a metric for one holding and one year with the "
                    "enterprise computation service.",
     "input_schema": {"type": "object",
                      "properties": {"metric": _METRIC,
                                     "company": {"type": "string",
                                                 "description": "Holding name "
                                                 "exactly as in the request"},
                                     "year": _YEAR},
                      "required": ["metric", "company", "year"],
                      "additionalProperties": False},
     "strict": True},
    {"name": "portfolio_intensity",
     "description": "Weighted average carbon intensity (WACI) of the portfolio "
                    "for one year, from the holdings' computed intensities, "
                    "with each holding's contribution, the covered weight, "
                    "holdings without data, and the change from another year "
                    "already computed.",
     "input_schema": {"type": "object",
                      "properties": {"metric": _METRIC, "year": _YEAR},
                      "required": ["metric", "year"],
                      "additionalProperties": False},
     "strict": True},
    {"name": "check_trade",
     "description": "Pre-trade compliance check: apply a trade to the current "
                    "weights and test the result against the fund's ESG "
                    "mandate. Returns the WACI before and after, the mandate "
                    "limits, and any breaches. Changes nothing.",
     "input_schema": {"type": "object",
                      "properties": {"metric": _METRIC, "year": _YEAR,
                                     "trades": _TRADES},
                      "required": ["metric", "year", "trades"],
                      "additionalProperties": False},
     "strict": True},
    {"name": "submit_trade",
     "description": "Submit a trade instruction. The compliance check is run "
                    "again; a compliant trade is cleared, a breaching trade is "
                    "held until a compliance officer approves an override.",
     "input_schema": {"type": "object",
                      "properties": {"metric": _METRIC, "year": _YEAR,
                                     "trades": _TRADES,
                                     "justification": {"type": "string"}},
                      "required": ["metric", "year", "trades",
                                   "justification"],
                      "additionalProperties": False},
     "strict": True},
]
L5_TOOLS = {"discover_metrics", "get_metric_definition"}

_NUM = re.compile(r"(?<![A-Za-z])\d[\d,]*\.?\d*")


def _numbers(text: str) -> List[float]:
    out = []
    for tok in _NUM.findall(text or ""):
        try:
            out.append(float(tok.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def _collect(obj: Any, into: set) -> None:
    """All numbers occurring anywhere in a tool result or request."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        into.add(abs(float(obj)))        # a change of -42.7 may be stated as 42.7
    elif isinstance(obj, str):
        into.update(_numbers(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, into)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, into)


class AgentRuntime:
    RESPONSIBILITY = "L3"

    def __init__(self, ground, infer, act, trace, max_model_calls: int = 12):
        self._ground = ground
        self._infer = infer
        self._act = act
        self._trace = trace
        self._max_calls = max_model_calls
        self.working_context: Dict[str, Any] = {}

    # ------------------------------------------------------------------ util
    def _rec(self, *args, **kwargs) -> int:
        return self._trace.record(*args, **kwargs).seq

    @staticmethod
    def _goal_text(goal: Dict[str, Any]) -> str:
        lines = [f"{h['company']}: {h['weight_pct']}%" for h in goal["holdings"]]
        years = goal["year"] + (f" (comparison year: {goal['compare_year']})"
                                if goal.get("compare_year") else "")
        return (f"Fund: {goal['fund']}. Industry: {goal['industry']}. "
                f"Category: {goal['category']}.\n"
                f"Reporting year: {years}.\n"
                f"Portfolio holdings (weight):\n  " + "\n  ".join(lines) +
                f"\nQuestion: {goal['question']}")

    def _years(self) -> set:
        g = self.working_context["goal"]
        return {str(g["year"])} | ({str(g["compare_year"])}
                                   if g.get("compare_year") else set())

    def _holdings_for(self, metric: str, year: str) -> List[Dict[str, Any]]:
        """Holdings with intensities assembled from this execution's L6 results."""
        comps = self.working_context["computations"]
        out = []
        for h in self.working_context["goal"]["holdings"]:
            c = comps.get((h["company"], year, metric))
            ok = c is not None and c["status"] == "success"
            out.append({"company": h["company"],
                        "weight_pct": float(h["weight_pct"]),
                        "intensity": float(c["value"]) if ok else None,
                        "reason": None if ok else (
                            c["error"] if c else
                            "not computed in this execution")})
        return out

    # ------------------------------------------------------------- execution
    def _run_tool(self, name: str, args: Dict[str, Any],
                  principal: Optional[Dict[str, Any]]) -> Tuple[Dict, List[int]]:
        wc, goal = self.working_context, self.working_context["goal"]
        tid = (principal or {}).get("trace_id")
        rec = self._rec

        if name == "discover_metrics":
            s = [rec("L3", "L5", "capability discovery", ttype="T4",
                     category=goal["category"], trace_id=tid)]
            found = self._ground.metrics_in_category(goal["industry"],
                                                     goal["category"])
            s.append(rec("L5", "L3", "discovered metrics", ttype="T4",
                         count=len(found)))
            wc["candidates"] = found
            return {"metrics": [{"name": m["name"],
                                 "calculation_method": m.get("calculation_method"),
                                 "unit": m.get("unit")} for m in found]}, s

        if name == "get_metric_definition":
            s = [rec("L3", "L5", "context retrieval", ttype="T4",
                     metric=args["metric"], trace_id=tid)]
            ctx = self._ground.assemble_metric_context(
                goal["industry"], goal["category"], args["metric"])
            cqs = len(ctx.get("provenance", {}).get("competency_questions", []))
            s.append(rec("L5", "L3", "grounded context", ttype="T4",
                         method=ctx.get("measurement_method"),
                         model=ctx.get("calculation_model"),
                         competency_questions=cqs))
            wc["metric_context"] = ctx
            return {k: ctx.get(k) for k in (
                "metric", "framework", "measurement_method",
                "calculation_model", "model_equation", "required_inputs",
                "unit")}, s

        # ---- L6 actions: L3 enforces the request scope first ------------
        year = str(args.get("year", ""))
        if year not in self._years():
            raise PermissionError(f"year {year} is outside the request")

        if name == "compute_metric":
            holdings = {h["company"] for h in goal["holdings"]}
            if args["company"] not in holdings:
                raise PermissionError(f"{args['company']} is not a holding")
            s = [rec("L3", "L6", "action intent", ttype="T5",
                     tool=name, company=args["company"], year=year,
                     metric=args["metric"])]
            res = self._act.invoke(name, principal=principal,
                                   metric=args["metric"],
                                   company=args["company"], year=year,
                                   industry=goal["industry"])
            s.append(rec("L6", "L3", "observation", ttype="T5", tool=name,
                         company=args["company"], status=res["status"],
                         value=res.get("display_value")))
            wc["computations"][(args["company"], year, args["metric"])] = res
            wc["l6_invocations"] += 1
            return res, s

        if name == "portfolio_intensity":
            holdings = self._holdings_for(args["metric"], year)
            prev = next(({"year": y, "waci": r["waci"]}
                         for y, r in wc["portfolio"].items() if y != year),
                        None)
            s = [rec("L3", "L6", "action intent", ttype="T5", tool=name,
                     year=year)]
            res = self._act.invoke(name, principal=principal,
                                   holdings=holdings, year=year,
                                   previous=prev)
            s.append(rec("L6", "L3", "observation", ttype="T5", tool=name,
                         status=res["status"], waci=res.get("waci")))
            wc["portfolio"][year] = res
            wc["l6_invocations"] += 1
            return res, s

        if name in ("check_trade", "submit_trade"):
            holdings = self._holdings_for(args["metric"], year)
            extra = ({"justification": args.get("justification")}
                     if name == "submit_trade" else {})
            s = [rec("L3", "L6", "action intent", ttype="T5", tool=name,
                     year=year, trades=len(args["trades"]))]
            res = self._act.invoke(name, principal=principal,
                                   fund=goal["fund"], holdings=holdings,
                                   trades=args["trades"], year=year, **extra)
            s.append(rec("L6", "L3", "observation", ttype="T5", tool=name,
                         status=res["status"], compliant=res.get("compliant"),
                         trade_id=res.get("trade_id")))
            if name == "check_trade" and res["status"] == "success":
                wc["trade_checks"].append(res)
            if name == "submit_trade" and res["status"] != "error":
                wc["trade"] = res
            wc["l6_invocations"] += 1
            return res, s

        raise ValueError(f"unregistered tool: {name}")

    # ------------------------------------------------------------------ loop
    def pursue(self, goal: Dict[str, Any],
               principal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.working_context = {"goal": dict(goal), "principal": principal,
                                "model_calls": 0, "plan": [],
                                "computations": {}, "portfolio": {},
                                "trade_checks": [],
                                "l6_invocations": 0, "evidence": set(),
                                "revisions": 0, "flagged": [],
                                "status": "running"}
        wc = self.working_context
        _collect({k: v for k, v in goal.items() if k != "industry"},
                 wc["evidence"])
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
            wc["plan"].append({"action": "decide", "why": text or (
                "chose " + ", ".join(c.name for c in calls) if calls
                else "finished"), "seqs": [s1, s2]})

            if out["contract"] != "success":
                wc["status"], wc["error"] = "failed", (
                    f"inference contract violation: {out['contract']}")
                break

            if not calls:                      # model ended its turn
                check = self._grounding(text)
                if not check["grounded"] and wc["revisions"] < 1:
                    # Number check failed: return the draft for one revision.
                    wc["revisions"] += 1
                    wc["flagged"] = check["unsupported"]
                    wc["plan"][-1]["action"] = "answer_flagged"
                    messages.append({"role": "user", "content": (
                        "Number check: your answer states numbers that no "
                        "tool returned: "
                        + ", ".join(f"{n:g}" for n in check["unsupported"])
                        + ". Reply with the restated answer only, using only "
                          "numbers from the request or tool results; do not "
                          "derive new numbers or comment on this check.")})
                    continue
                final_text = text
                wc["plan"][-1]["action"] = "answer"
                wc["status"] = (
                    (wc.get("trade") or {}).get("status")   # cleared / pending_override
                    or ("success" if wc["portfolio"] or wc["trade_checks"]
                        or any(
                        c["status"] == "success"
                        for c in wc["computations"].values())
                        else "unsatisfiable"))
                break

            results = []
            for c in calls:
                args = dict(c.input)
                try:
                    result, seqs = self._run_tool(c.name, args, principal)
                    _collect(result, wc["evidence"])
                    results.append({"type": "tool_result", "tool_use_id": c.id,
                                    "content": json.dumps(result, default=str)})
                except (PermissionError, ValueError) as e:
                    seqs = []
                    results.append({"type": "tool_result", "tool_use_id": c.id,
                                    "content": f"Refused: {e}",
                                    "is_error": True})
                wc["plan"].append({"action": c.name, "why": json.dumps(args),
                                   "seqs": seqs})
            messages.append({"role": "user", "content": results})

        wc["final_text"] = final_text
        return self._result(final_text)

    # ------------------------------------------------------- approval resume
    def decide_trade(self, trade_id: str, approve: bool,
                     principal: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Route a compliance officer's override decision to the L6 gate."""
        self._rec("L3", "L6", "override decision", ttype="T5",
                  trade_id=trade_id,
                  decision="approve" if approve else "reject",
                  trace_id=(principal or {}).get("trace_id"))
        try:
            res = self._act.decide(trade_id, approve, principal)
        except (PermissionError, ValueError) as e:
            res = {"trade_id": trade_id, "status": "refused", "error": str(e)}
        self._rec("L6", "L3", "observation", ttype="T5", status=res["status"])
        return res

    # ---------------------------------------------------------------- result
    def _grounding(self, text: str) -> Dict[str, Any]:
        """Every number in the answer must occur in the request or an L5/L6 result."""
        allowed = self.working_context["evidence"]
        found = [n for n in _numbers(text) if n >= 10 or n != int(n)]

        def ok(n):
            # equal up to 0.5% or to rounding at one or two decimals; rounding
            # to a whole number only for values of 100 or more
            return any(abs(n - a) <= max(0.006, 0.005 * abs(a))
                       or round(a, 1) == n or round(a, 2) == n
                       or (abs(a) >= 100 and round(a) == n) for a in allowed)
        bad = [n for n in found if not ok(n)]
        return {"numbers": found, "unsupported": bad, "grounded": not bad}

    def _result(self, final_text: str) -> Dict[str, Any]:
        wc = self.working_context
        goal = wc["goal"]
        ctx = wc.get("metric_context") or {}
        comps = [{"company": k[0], "year": k[1], "metric": k[2],
                  "status": v["status"], "value": v.get("display_value"),
                  "unit": v.get("unit"), "error": v.get("error"),
                  "inputs": (v.get("provenance") or {}).get("inputs")}
                 for k, v in wc["computations"].items()]
        out = {"status": wc["status"],
               "plan": [dict(p) for p in wc["plan"]],
               "model_calls": wc["model_calls"],
               "l6_invocations": wc["l6_invocations"],
               "answer": final_text,
               "grounding": {**self._grounding(final_text),
                             "revisions": wc["revisions"],
                             "flagged_in_draft": wc["flagged"]},
               "computations": comps,
               "portfolio": wc["portfolio"].get(str(goal["year"])),
               "portfolio_by_year": wc["portfolio"],
               "trade_checks": wc["trade_checks"],
               "trade": wc.get("trade"),
               "metric": ctx.get("metric"),
               "framework": ctx.get("framework"),
               "provenance": {"knowledge_graph": ctx.get("provenance"),
                              "inference_provider": self._infer.provider_name,
                              "trace_id": (wc.get("principal") or {}).get(
                                  "trace_id")}}
        if wc.get("error"):
            out["error"] = wc["error"]
        return out
