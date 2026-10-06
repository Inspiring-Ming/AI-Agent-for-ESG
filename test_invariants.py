#!/usr/bin/env python3
"""Boundary-invariant probes (Section VI).

Each boundary invariant of the reference architecture is tested against the
running instantiation. An invariant is reported Preserved only when a probe
that would violate it is observably refused or prevented, so the paper reports
measured outcomes rather than assertions.

  I1 Coordination--Execution         L3 decides; L6 validates and executes
  I2 Execution-State--Knowledge      execution-local state in L3; reusable
                                     definitions retrieved through L5
  I3 System-Access--Resource-Authority  L2 admits; L6 retains enforcement,
                                     including the approval gate
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
from agentic.scenarios import BASE, GOALS                          # noqa: E402
from agentic.trace.recorder import Trace                           # noqa: E402

REQUEST = {**system.DEFAULTS, **dict((g, r) for g, _, r in GOALS)["G1"]}
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
        self.calls = {}
        self.mechanism = getattr(inner, "mechanism", "unknown")

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def counted(*a, **k):
            self.calls[name] = self.calls.get(name, 0) + 1
            return attr(*a, **k)
        return counted


def main() -> int:
    trace = Trace("invariant probes")
    access = AccessControl()
    kg = Counting(system.knowledge())
    compute = Counting(system.compute_backend())
    portfolio = Counting(system.portfolio_backend())
    infer = ModelAccess()
    act = ActionRuntime(compute, portfolio)
    agent = AgentRuntime(kg, infer, act, trace)

    print("=" * 70)
    print("BOUNDARY-INVARIANT PROBES")
    print("=" * 70)
    print(f"mechanism: {system.MECHANISM}   model: {infer.provider_name}\n")

    analyst = access.issue_token("analyst@enterprise.example")
    manager = access.issue_token("portfolio.manager@enterprise.example")
    principal = access.admit(analyst, REQUEST)

    # ---------------- I1: Coordination -- Execution ----------------------
    print("I1  Coordination--Execution")
    result = agent.pursue(REQUEST, principal)
    pf = result.get("portfolio") or {}
    computed = {c["company"]: c["value"] for c in result["computations"]
                if c["status"] == "success"}
    from_l6 = bool(pf.get("contributions")) and all(
        abs(c["intensity"] - float(computed[c["company"]])) < 0.01
        for c in pf["contributions"])
    g = result["grounding"]
    record("I1",
           "every value reported must originate from an L6 service, "
           "not from model inference",
           "one L6 computation per holding; the portfolio figure from the L6 "
           "portfolio service; every number in the answer traced to L5/L6",
           f"computation-service calls={compute.calls.get('calculate', 0)} "
           f"for {len(BASE)} holdings; portfolio-service calls="
           f"{portfolio.calls.get('portfolio_intensity', 0)}; holding "
           f"intensities equal L6 results={from_l6}; numbers in answer "
           f"{g['numbers']} traced={g['grounded']}",
           compute.calls.get("calculate", 0) == len(BASE)
           and portfolio.calls.get("portfolio_intensity", 0) >= 1
           and pf.get("waci") is not None and from_l6 and g["grounded"])

    l3_can_execute = any(hasattr(agent, m) for m in
                         ("calculate", "execute", "portfolio_intensity",
                          "evaluate_rebalance"))
    record("I1",
           "L3 must not be able to execute an enterprise capability directly",
           "the coordinator exposes no execution mechanism of its own",
           f"coordinator exposes execution method={l3_can_execute}",
           not l3_can_execute)

    # ---------------- I2: Execution-State -- Knowledge -------------------
    print("\nI2  Execution-State--Knowledge")
    wc = agent.working_context
    state_keys = sorted(k for k in wc if k != "metric_context")
    ctx = wc.get("metric_context", {})
    store = ctx.get("provenance", {}).get("context_store")
    cqs = len(ctx.get("provenance", {}).get("competency_questions", []))
    record("I2",
           "execution-local state and reusable enterprise knowledge must be "
           "owned by different responsibilities",
           "L3 holds only execution-local state; definitions arrive from L5 "
           "with knowledge-store provenance",
           f"L3 execution-state keys={state_keys}; L5 context store='{store}' "
           f"via {cqs} competency questions",
           bool(state_keys) and store is not None and cqs > 0)

    before = kg.calls.get("assemble_metric_context", 0)
    AgentRuntime(kg, infer, act, Trace("second")).pursue(REQUEST, principal)
    after = kg.calls.get("assemble_metric_context", 0)
    record("I2",
           "a second execution must re-retrieve knowledge rather than reuse "
           "coordinator state",
           "the knowledge graph is queried again for the new execution",
           f"metric-definition retrievals: before={before}, after={after}",
           after > before)

    # ---------------- I3: System-Access -- Resource-Authority ------------
    print("\nI3  System-Access--Resource-Authority")
    no_ent = access.admit(analyst, REQUEST, entitlements=[])
    try:
        act.invoke("compute_metric", principal=no_ent,
                   metric="GHGEmissionIntensity", company=BASE[0]["company"],
                   year="2023", industry="semiconductors")
        obs, ok = "capability executed despite missing entitlement", False
    except PermissionError as e:
        obs, ok = f"refused at L6: {e}", True
    record("I3",
           "a principal admitted at L2 but lacking the resource entitlement "
           "must still be refused at L6",
           "admission at the system boundary does not confer resource-specific "
           "authorization", obs, ok)

    try:
        access.admit("forged:0:deadbeef", REQUEST)
        obs, ok = "unauthenticated request admitted", False
    except PermissionError as e:
        obs, ok = f"refused at L2: {e}", True
    record("I3", "an unauthenticated request must not reach coordination",
           "L2 refuses the request before L3 is engaged", obs, ok)

    # A consequential action stops at the L6 approval gate ...
    holdings = [{"company": h["company"], "weight_pct": h["weight_pct"],
                 "intensity": (float(computed[h["company"]])
                               if h["company"] in computed else None),
                 "reason": None} for h in BASE]
    target = [{"company": h["company"], "weight_pct": w}
              for h, w in zip(BASE, (30, 40, 10, 20))]
    prop = act.invoke("propose_rebalance", principal=principal,
                      holdings=holdings, target_weights=target, year="2023")
    pid = prop.get("proposal_id")
    # ... and cannot be approved by a principal without the approval
    # entitlement, nor by the principal who requested it.
    refusals = []
    for who, p in (("analyst", access.admit(analyst, {"proposal_id": pid})),
                   ("requester holding the approval entitlement",
                    access.admit(analyst, {"proposal_id": pid},
                                 entitlements=["esg.portfolio.approve"]))):
        try:
            act.decide(pid, True, p)
            refusals.append(f"{who}: approved")
        except PermissionError as e:
            refusals.append(f"{who}: refused ({e})")
    approved = act.decide(pid, True, access.admit(manager, {"proposal_id": pid}))
    record("I3",
           "a consequential action must not take effect without approval "
           "by an authorized principal other than the requester",
           "proposal held pending; refused for the analyst and for the "
           "requester; accepted from the portfolio manager",
           f"proposal status={prop['status']}; " + "; ".join(refusals)
           + f"; portfolio manager: {approved['status']}",
           prop["status"] == "pending_approval"
           and all("refused" in r for r in refusals)
           and approved["status"] == "approved")

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
           f"occurrences carrying trace_id {tid}={carried}",
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
    with open(os.path.join(out, "invariants.json"), "w", encoding="utf-8") as fh:
        json.dump({"mechanism": system.MECHANISM, "model": infer.provider_name,
                   "summary": summary, "findings": FINDINGS}, fh, indent=2)

    print("\n" + "=" * 70)
    for inv in sorted(summary):
        s = summary[inv]
        print(f"  {inv}: {'Preserved' if s['preserved'] else 'VIOLATED'} "
              f"({s['probes']} probes)")
    passed = sum(1 for f in FINDINGS if f["preserved"])
    print(f"  {passed}/{len(FINDINGS)} probes passed")
    print("=" * 70)
    print(f"  written to {out}/invariants.json")
    return 0 if passed == len(FINDINGS) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnterpriseSystemUnavailable as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(2)
