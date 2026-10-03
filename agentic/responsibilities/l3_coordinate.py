"""L3 -- Agent & Workflow Orchestration (Coordinate).

Goal-directed coordination of agentic execution. L3 receives a goal rather than
a prescribed procedure, discovers what the goal requires by querying enterprise
knowledge through L5, and then decides on each iteration which supporting
responsibility to engage next, based on what it has observed so far.

The loop is plan -> act -> observe:

  plan     inspect the goal and the observations accumulated so far, and select
           the next action (discover, ground, compute, explain, or finish)
  act      engage the responsibility that owns the selected action
  observe  record the result into the working context, which conditions the
           next planning step

Nothing in this class prescribes the order in which L4, L5 and L6 are engaged.
Different goals produce different action sequences, different numbers of
interaction occurrences, and different sets of realized interaction types: a
metric requiring a calculation model engages L6 with a resolved model, whereas
a directly measured metric engages L6 without one, and a goal that cannot be
satisfied terminates without engaging L6 at all.

Boundary (Section IV-C): L3 decides *that* a capability is required; it never
executes one itself. Inference, grounding, and action mechanisms remain with
L4, L5, and L6.
"""

from typing import Any, Dict, List, Optional


class AgentRuntime:
    """Goal-directed coordinator with an explicit plan--act--observe loop."""

    RESPONSIBILITY = "L3"

    def __init__(self, ground, infer, act, trace, max_steps: int = 12):
        self._ground = ground
        self._infer = infer
        self._act = act
        self._trace = trace
        self._max_steps = max_steps
        self.working_context: Dict[str, Any] = {}

    # ------------------------------------------------------------------ plan
    def _plan(self) -> Dict[str, Any]:
        """Select the next action from the goal and accumulated observations.

        This is the agent's decision point. It reads only the working context,
        so the action sequence is a function of what has been observed rather
        than of a fixed procedure.
        """
        wc = self.working_context
        goal = wc["goal"]

        # 1. The goal names a category rather than a metric: discover what the
        #    category contains before anything can be computed.
        if goal.get("category") and not wc.get("candidates"):
            return {"action": "discover",
                    "why": "goal names a category; metrics must be discovered"}

        # 2. Candidates are known but none has been selected yet.
        if wc.get("candidates") and not wc.get("selected"):
            return {"action": "select",
                    "why": "choose the candidate that satisfies the goal"}

        # 3. A metric is selected but its definition has not been grounded.
        if wc.get("selected") and not wc.get("metric_context"):
            return {"action": "ground",
                    "why": "metric definition and calculation method required"}

        ctx = wc.get("metric_context") or {}

        # 4. Grounded, but a calculation model is required and not yet resolved.
        if ctx and ctx.get("measurement_method") == "calculation_model" \
                and not ctx.get("calculation_model"):
            return {"action": "abort",
                    "why": "calculation model required but not resolvable"}

        # 5. Grounded and resolvable: compute.
        if ctx and not wc.get("computation"):
            return {"action": "compute",
                    "why": "metric is computable from the grounded definition"}

        # 6. Computed: explain only if the goal asks for an explanation.
        if wc.get("computation") and goal.get("explain") \
                and not wc.get("explanation"):
            return {"action": "explain",
                    "why": "goal requests an explanation of the result"}

        return {"action": "finish", "why": "goal satisfied"}

    # ------------------------------------------------------------------- act
    def _act_on(self, decision: Dict[str, Any],
                principal: Optional[Dict[str, Any]]) -> None:
        """Engage the responsibility owning the selected action."""
        wc = self.working_context
        goal = wc["goal"]
        action = decision["action"]
        tid = (principal or {}).get("trace_id")

        if action == "discover":
            self._trace.record("L3", "L5", "capability discovery", ttype="T4",
                               category=goal["category"],
                               industry=goal["industry"], trace_id=tid)
            found = self._ground.metrics_in_category(
                goal["industry"], goal["category"])
            self._trace.record("L5", "L3", "discovered metrics", ttype="T4",
                               count=len(found))
            wc["candidates"] = found

        elif action == "select":
            chosen = self._select(wc["candidates"], goal)
            wc["selected"] = chosen
            wc["selection_rationale"] = (
                f"{len(wc['candidates'])} candidates; selected "
                f"'{chosen}'" if chosen else "no candidate satisfies the goal")
            if chosen is None:
                wc["status"] = "unsatisfiable"

        elif action == "ground":
            self._trace.record("L3", "L5", "context retrieval", ttype="T4",
                               metric=wc["selected"],
                               industry=goal["industry"], trace_id=tid)
            ctx = self._ground.assemble_metric_context(
                goal["industry"], goal.get("category"), wc["selected"])
            self._trace.record(
                "L5", "L3", "grounded context", ttype="T4",
                framework=ctx.get("framework"),
                method=ctx.get("measurement_method"),
                model=ctx.get("calculation_model"),
                competency_questions=len(
                    ctx["provenance"]["competency_questions"]))
            wc["metric_context"] = ctx

        elif action == "compute":
            ctx = wc["metric_context"]
            self._trace.record("L3", "L6", "action intent", ttype="T5",
                               tool="compute_metric", metric=wc["selected"],
                               model=ctx.get("calculation_model"),
                               method=ctx.get("measurement_method"))
            result = self._act.invoke(
                "compute_metric", principal=principal, metric=wc["selected"],
                company=goal["company"], year=goal["year"],
                industry=goal["industry"])
            self._trace.record("L6", "L3", "observation", ttype="T5",
                               status=result.get("status"),
                               value=result.get("display_value"))
            if result.get("status") != "success":
                wc["status"] = "failed"
                wc["error"] = result.get("error")
            else:
                wc["computation"] = result

        elif action == "explain":
            self._trace.record("L3", "L4", "inference request", ttype="T3",
                               provider=self._infer.provider_name)
            out = self._infer.explain({
                "company": goal["company"], "year": goal["year"],
                "metric_context": wc["metric_context"],
                "computation": wc["computation"]})
            self._trace.record("L4", "L3", "inference result", ttype="T3",
                               contract=out.get("status"))
            if out.get("status") != "success":
                wc["status"] = "failed"
                wc["error"] = "inference contract violation"
            else:
                wc["explanation"] = out["explanation"]

        elif action == "abort":
            wc["status"] = "unsatisfiable"
            wc["error"] = decision["why"]

    # ---------------------------------------------------------------- select
    @staticmethod
    def _select(candidates: List[Dict[str, Any]],
                goal: Dict[str, Any]) -> Optional[str]:
        """Choose among discovered metrics according to the goal.

        A goal may name a metric directly, or state a preference the agent
        resolves against the discovered candidates.
        """
        want = goal.get("metric")
        norm = lambda s: (s or "").replace(" ", "").lower()  # noqa: E731
        if want:
            for c in candidates:
                if norm(c.get("name")) == norm(want):
                    return c.get("name")
            return None
        prefer = goal.get("prefer_method")
        if prefer:
            for c in candidates:
                if c.get("calculation_method") == prefer:
                    return c.get("name")
            return None
        return candidates[0]["name"] if candidates else None

    # ------------------------------------------------------------------ loop
    def pursue(self, goal: Dict[str, Any],
               principal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the plan--act--observe loop until the goal is resolved."""
        self.working_context = {"goal": dict(goal), "principal": principal,
                                "steps": 0, "trace": [], "status": "running"}
        wc = self.working_context

        while wc["status"] == "running":
            wc["steps"] += 1
            if wc["steps"] > self._max_steps:
                wc["status"] = "failed"
                wc["error"] = f"execution exceeded {self._max_steps} steps"
                break

            decision = self._plan()
            wc["trace"].append({"step": wc["steps"],
                                "action": decision["action"],
                                "why": decision["why"]})
            if decision["action"] == "finish":
                wc["status"] = "complete"
                break
            self._act_on(decision, principal)

        return self._result()

    def _result(self) -> Dict[str, Any]:
        wc = self.working_context
        if wc["status"] != "complete":
            return {"status": wc["status"], "error": wc.get("error"),
                    "plan": wc["trace"], "steps_used": wc["steps"],
                    "selection_rationale": wc.get("selection_rationale")}
        ctx = wc.get("metric_context") or {}
        comp = wc.get("computation") or {}
        if not comp:
            return {"status": "failed",
                    "error": wc.get("error", "goal resolved without a result"),
                    "plan": wc["trace"], "steps_used": wc["steps"],
                    "selection_rationale": wc.get("selection_rationale")}
        return {
            "status": "success",
            "metric": wc["selected"], "company": wc["goal"]["company"],
            "year": wc["goal"]["year"], "framework": ctx.get("framework"),
            "measurement_method": ctx.get("measurement_method"),
            "value": comp.get("display_value"),
            "unit": comp.get("unit") or ctx.get("unit"),
            "explanation": wc.get("explanation"),
            "provenance": {
                "knowledge_graph": ctx.get("provenance"),
                "computation": comp.get("provenance"),
                "inference_provider": (self._infer.provider_name
                                       if wc.get("explanation") else None),
                "trace_id": (wc.get("principal") or {}).get("trace_id"),
            },
            "plan": wc["trace"],
            "selection_rationale": wc.get("selection_rationale"),
            "steps_used": wc["steps"],
        }

    # Backwards-compatible entry point used by the fixed-scenario runner.
    def handle_metric_request(self, request: Dict[str, Any],
                              principal: Optional[Dict[str, Any]] = None
                              ) -> Dict[str, Any]:
        goal = dict(request)
        goal.setdefault("explain", True)
        return self.pursue(goal, principal)
