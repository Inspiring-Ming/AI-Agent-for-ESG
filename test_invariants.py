#!/usr/bin/env python3
"""Boundary-invariant experiments (Table III).

Each invariant defined in Section IV-A is tested against the running
instantiation. An invariant is reported Preserved only when a probe that would
violate it is observably refused or prevented, so Table III reports measured
outcomes rather than assertions.

  I1 Coordination--Execution        L3 decides; L6 validates and executes
  I2 Execution-State--Knowledge     execution-local state in L3; reusable
                                    definitions retrieved through L5
  I3 System-Access--ResourceAuthority L2 admits; L5/L6 retain enforcement
  I4 Evidence-Ownership--Correlation each responsibility emits local evidence;
                                    L9 correlates

Run (inside the Compose stack):  python test_invariants.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from agentic import system                                         # noqa: E402
from agentic.adapters.esg_system import EnterpriseSystemUnavailable  # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl      # noqa: E402
from agentic.responsibilities.l3_coordinate import AgentRuntime    # noqa: E402
from agentic.responsibilities.l4_infer import ModelAccess          # noqa: E402
from agentic.responsibilities.l6_act import ActionRuntime          # noqa: E402
from agentic.trace.recorder import Trace                           # noqa: E402

SCENARIO = {"company": "STMicroelectronics NV", "metric": "GHGEmissionIntensity",
            "year": "2023", "industry": "semiconductors",
            "category": "Greenhouse Gas Emissions", "explain": True}

FINDINGS = []


def record(inv, probe, expected, observed, preserved):
    FINDINGS.append({"invariant": inv, "probe": probe, "expected": expected,
                     "observed": observed, "preserved": preserved})
    print(f"  [{'PASS' if preserved else 'FAIL'}] {inv}: {probe}")
    print(f"         observed: {observed}")


class Counting:
    """Wraps an L5 or L6 backend and counts the calls that reach it."""

    def __init__(self, inner):
        self._inner = inner
        self.calculate_calls = 0
        self.kg_calls = 0
        self.mechanism = getattr(inner, "mechanism", "unknown")

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def calculate(self, *a, **k):            # L6 execution backend
        self.calculate_calls += 1
        return self._inner.calculate(*a, **k)

    def assemble_metric_context(self, *a, **k):   # L5 context retrieval
        self.kg_calls += 1
        return self._inner.assemble_metric_context(*a, **k)


def main() -> int:
    trace = Trace("invariant probes")
    access = AccessControl()
    kg = Counting(system.knowledge())
    adapter = Counting(system.compute_backend())
    infer = ModelAccess()
    act = ActionRuntime(adapter)
    agent = AgentRuntime(kg, infer, act, trace)

    print("=" * 70)
    print("BOUNDARY-INVARIANT PROBES")
    print("=" * 70)
    print(f"mechanism: {system.MECHANISM}   model: {infer.provider_name}\n")

    principal = access.admit(
        access.issue_token("analyst@enterprise.example"),
        SCENARIO, ["esg.metric.compute"])

    # ---------------- I1: Coordination -- Execution ----------------------
    print("I1  Coordination--Execution")
    result = agent.pursue(SCENARIO, principal)
    value_from_service = adapter.calculate_calls == 1
    reported = result.get("value")
    answer = result.get("answer") or ""
    grounding = result["grounding"]
    in_expl = reported in answer and grounding["grounded"]
    record("I1",
           "the reported value must originate from the computation service, "
           "not from model inference",
           "exactly one computation-service invocation; the explanation "
           "restates that value without recomputing it",
           f"computation-service invocations={adapter.calculate_calls}; "
           f"reported value={reported}; value restated in explanation={in_expl}"
           + f"; numbers in model answer {grounding['numbers']} all traced "
             f"to L5/L6 results={grounding['grounded']}",
           value_from_service and in_expl)

    # L3 cannot execute: it owns no execution mechanism
    l3_can_execute = any(hasattr(agent, m) for m in ("calculate", "execute"))
    record("I1",
           "L3 must not be able to execute an enterprise capability directly",
           "the coordinator exposes no execution mechanism of its own",
           f"coordinator exposes execution method={l3_can_execute}",
           not l3_can_execute)

    # ---------------- I2: Execution-State -- Knowledge -------------------
    print("\nI2  Execution-State--Knowledge")
    wc = agent.working_context
    state_keys = sorted(k for k in wc if k not in ("metric_context", "computation"))
    ctx = wc.get("metric_context", {})
    kg_sourced = ctx.get("provenance", {}).get("context_store")
    cqs = len(ctx.get("provenance", {}).get("competency_questions", []))
    record("I2",
           "execution-local state and reusable enterprise knowledge must be "
           "owned by different responsibilities",
           "L3 holds only execution-local state; definitions arrive from L5 "
           "with knowledge-store provenance",
           f"L3 execution-state keys={state_keys}; "
           f"L5 context store='{kg_sourced}' via {cqs} competency questions",
           bool(state_keys) and kg_sourced is not None and cqs > 0)

    # knowledge is retrieved per execution, not cached in the coordinator
    agent2 = AgentRuntime(kg, infer, act, Trace("second"))
    before = kg.kg_calls
    agent2.pursue(SCENARIO, principal)
    record("I2",
           "a second execution must re-retrieve knowledge rather than reuse "
           "coordinator state",
           "the knowledge graph is queried again for the new execution",
           f"knowledge-graph queries: before={before}, after={kg.kg_calls}",
           kg.kg_calls > before)

    # ---------------- I3: System-Access -- Resource-Authority ------------
    print("\nI3  System-Access--ResourceAuthority")
    admitted_no_ent = access.admit(
        access.issue_token("analyst@enterprise.example"), SCENARIO, [])
    try:
        act.invoke("compute_metric", principal=admitted_no_ent,
                   metric=SCENARIO["metric"], company=SCENARIO["company"],
                   year=SCENARIO["year"], industry=SCENARIO["industry"])
        obs, ok = "capability executed despite missing entitlement", False
    except PermissionError as e:
        obs, ok = f"refused at L6: {e}", True
    record("I3",
           "a principal admitted at L2 but lacking the resource entitlement "
           "must still be refused at L6",
           "admission at the system boundary does not confer resource-specific "
           "authorization",
           obs, ok)

    try:
        access.admit("forged:0:deadbeef", SCENARIO, ["esg.metric.compute"])
        obs2, ok2 = "unauthenticated request admitted", False
    except PermissionError as e:
        obs2, ok2 = f"refused at L2: {e}", True
    record("I3",
           "an unauthenticated request must not reach coordination",
           "L2 refuses the request before L3 is engaged", obs2, ok2)

    # ---------------- I4: Evidence-Ownership -- Correlation --------------
    print("\nI4  Evidence-Ownership--Correlation")
    emitters = sorted({i.source for i in trace.interactions})
    tid = principal["trace_id"]
    carried = sum(1 for i in trace.interactions
                  if i.payload.get("trace_id") == tid)
    record("I4",
           "each responsibility must emit evidence about its own operations, "
           "correlatable across the execution",
           "evidence originates from multiple responsibilities and shares a "
           "correlation identifier established at the boundary",
           f"emitting responsibilities={emitters}; "
           f"interactions carrying trace_id {tid}={carried}",
           len(emitters) >= 3 and carried >= 1)

    # ---------------- report ---------------------------------------------
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    by_inv = {}
    for f in FINDINGS:
        by_inv.setdefault(f["invariant"], []).append(f)
    summary = {inv: {"probes": len(v),
                     "preserved": all(x["preserved"] for x in v)}
               for inv, v in by_inv.items()}
    name = "invariants.json"
    with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
        json.dump({"mechanism": system.MECHANISM, "model": infer.provider_name,
                   "summary": summary,
                   "findings": FINDINGS}, fh, indent=2)

    print("\n" + "=" * 70)
    for inv in sorted(summary):
        s = summary[inv]
        print(f"  {inv}: {'Preserved' if s['preserved'] else 'VIOLATED'} "
              f"({s['probes']} probes)")
    passed = sum(1 for f in FINDINGS if f["preserved"])
    print(f"  {passed}/{len(FINDINGS)} probes passed")
    print("=" * 70)
    print(f"  written to {out}/{name}")
    return 0 if passed == len(FINDINGS) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnterpriseSystemUnavailable as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(2)
