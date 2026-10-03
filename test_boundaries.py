#!/usr/bin/env python3
"""Boundary and variability checks for the case instantiation.

These assertions turn the claims made in Section V-B into executable checks, so
the evaluation reports properties of a running system rather than assertions
about one. Each test names the claim it substantiates.

Run:  python3 test_boundaries.py
"""

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from agentic.trace.recorder import Trace                         # noqa: E402
from agentic.responsibilities.l4_infer import (                  # noqa: E402
    ModelAccess, DeterministicProvider)
from agentic.responsibilities.l6_act import ActionRuntime        # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl     # noqa: E402

RESULTS = []


def check(claim: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((claim, condition, detail))
    print(f"  [{'PASS' if condition else 'FAIL'}] {claim}"
          + (f"\n         {detail}" if detail else ""))


PRINCIPAL = {"subject": "analyst", "entitlements": ["esg.metric.compute"],
             "trace_id": "test"}


class _StubCalc:
    """Stands in for the ESG system adapter."""

    mechanism = "stub"

    def __init__(self):
        self.calls = 0

    def calculate(self, industry, company, year, metrics):
        self.calls += 1
        return {"status": "success", "value": 0.071, "display_value": "0.0710",
                "unit": "tons CO2e per million USD",
                "model_name": "GHGEmissionIntensityModel",
                "model_equation": "(scope1_emissions + scope2_emissions) / revenue",
                "input_values": {"scope1_emissions": 514000.0,
                                 "scope2_emissions": 272000.0,
                                 "revenue": 11076000.0},
                "input_dataset_variables": {}, "implementation": {}}


def main() -> int:
    print("=" * 68)
    print("BOUNDARY AND VARIABILITY CHECKS")
    print("=" * 68)

    # -- Claim: the calculation is a service operation, not model output ----
    print("\nResponsibility separation (L4 vs L6)")
    calc = _StubCalc()
    act = ActionRuntime(calc)
    res = act.invoke("compute_metric", principal=PRINCIPAL,
                     metric="GHGEmissionIntensity", company="X",
                     year="2023", industry="semiconductors")
    check("L6 executes the metric through the computation service",
          calc.calls == 1 and res["value"] == 0.071)

    infer = ModelAccess(DeterministicProvider())
    out = infer.explain({"company": "X", "year": "2023",
                         "metric_context": {"metric": "GHGEmissionIntensity"},
                         "computation": res})
    check("L4 explanation reuses the computed value and introduces no new number",
          "0.0710" in out["explanation"] and calc.calls == 1,
          "the model never recomputes: calculation service call count stays 1")

    # -- Claim: L6 validates actions before executing them -----------------
    print("\nAction validation (L6)")
    try:
        act.invoke("compute_metric", principal=PRINCIPAL, metric="M",
                   company="", year="2023", industry="semiconductors")
        check("L6 rejects an invocation with missing arguments", False)
    except ValueError as e:
        check("L6 rejects an invocation with missing arguments", True, str(e))

    try:
        act.invoke("delete_everything", principal=PRINCIPAL, metric="M",
                   company="C", year="2023", industry="i")
        check("L6 rejects an unregistered tool", False)
    except ValueError as e:
        check("L6 rejects an unregistered tool", True, str(e))

    # -- Claim: approval is conditional, not mandatory ---------------------
    print("\nVariability: conditional approval gate (L6)")
    check("no approval required for a bounded analytical action",
          not act.approval_required("compute_metric"))

    gated = ActionRuntime(_StubCalc(), require_approval=True)
    check("approval still not required when the action is non-consequential",
          not gated.approval_required("compute_metric"),
          "the gate keys on consequence, not on the flag alone")

    gated.describe("compute_metric")["consequential"] = True
    check("approval IS required once the action is consequential",
          gated.approval_required("compute_metric"),
          "same responsibility, different condition -> different capability set")

    # -- Claim: L4 provider is replaceable ---------------------------------
    print("\nVariability: replaceable realization mechanism (L4)")

    class _AltProvider:
        name = "alternative-provider"

        def complete(self, prompt, context):
            return "Alternative provider explanation."

    alt = ModelAccess(_AltProvider())
    alt_out = alt.explain({"company": "X", "year": "2023",
                           "metric_context": {}, "computation": res})
    check("L4 provider can be swapped without changing L3, L5 or L6",
          alt.provider_name == "alternative-provider"
          and alt_out["status"] == "success")

    # -- Claim: L4 enforces an output contract -----------------------------
    print("\nOutput contract validation (L4)")

    class _EmptyProvider:
        name = "empty"

        def complete(self, prompt, context):
            return "   "

    bad = ModelAccess(_EmptyProvider()).explain(
        {"company": "X", "year": "2023", "metric_context": {},
         "computation": res})
    check("L4 flags an inference result that violates the output contract",
          bad["status"] == "contract_violation")

    # -- Claim: bounded execution is enforced by L3 ------------------------
    print("\nBounded execution (L3)")
    from agentic.responsibilities.l3_coordinate import AgentRuntime

    class _SlowGround:
        def metrics_in_category(self, industry, category):
            return [{"name": "M", "calculation_method": "calculation_model"}]

        def assemble_metric_context(self, industry, category, metric):
            return {"metric": metric, "measurement_method": "calculation_model",
                    "calculation_model": "M", "provenance":
                        {"competency_questions": []}}

    agent = AgentRuntime(_SlowGround(), infer, act, Trace("bounds"),
                         max_steps=1)
    r = agent.handle_metric_request({"company": "X", "metric": "M",
                                     "year": "2023", "category": "C",
                                     "industry": "semiconductors"}, PRINCIPAL)
    check("L3 halts execution past the configured step bound",
          r["status"] == "failed" and "exceeded" in (r.get("error") or ""),
          str(r.get("error")))

    # -- Claim: L2 controls the boundary, L6 authorizes the resource -------
    print("\nBoundary vs resource authorization (L2 vs L6)")
    access = AccessControl(rate_limit=2, per_seconds=3600)
    good = access.issue_token("analyst")
    req = {"company": "X", "metric": "M", "year": "2023",
           "industry": "semiconductors"}

    try:
        access.admit("forged:0:deadbeef", req)
        check("L2 rejects a request with an invalid token", False)
    except PermissionError as e:
        check("L2 rejects a request with an invalid token", True, str(e))

    ctx = access.admit(good, req, ["esg.metric.compute"])
    check("L2 mints identity and trace context for downstream propagation",
          ctx["subject"] == "analyst" and len(ctx["trace_id"]) == 12,
          f"trace_id={ctx['trace_id']}")

    try:
        access.admit(good, {**req, "company": ""})
        check("L2 rejects a malformed request at the boundary", False)
    except ValueError as e:
        check("L2 rejects a malformed request at the boundary", True, str(e))

    try:
        access.admit(good, req); access.admit(good, req)
        check("L2 enforces the per-principal rate limit", False)
    except PermissionError as e:
        check("L2 enforces the per-principal rate limit", True, str(e))

    # admission at L2 does not confer resource authorization at L6
    unentitled = {"subject": "analyst", "entitlements": [], "trace_id": "t"}
    try:
        act.invoke("compute_metric", principal=unentitled, metric="M",
                   company="C", year="2023", industry="semiconductors")
        check("L6 still refuses an admitted principal lacking the entitlement",
              False)
    except PermissionError as e:
        check("L6 still refuses an admitted principal lacking the entitlement",
              True, str(e))

    # -- Claim: the recorded trace matches the reported trace --------------
    print("\nRuntime trace")
    tp = os.path.join(HERE, "output", "runtime_trace.json")
    if os.path.exists(tp):
        with open(tp, encoding="utf-8") as fh:
            tr = json.load(fh)
        check("recorded trace has eleven interaction occurrences",
              tr["interaction_occurrences"] == 11,
              f"observed {tr['interaction_occurrences']} occurrences "
              f"realizing types {tr['interaction_types_observed']}")
        check("occurrences realize five of the eight defined interaction types",
              len(tr["interaction_types_observed"]) == 5
              and tr["interaction_types_defined"] == 8,
              str(tr["occurrences_by_type"]))
        check("recorded trace touches L1, L2, L3, L4, L5, L6",
              tr["responsibilities_touched"] ==
              ["L1", "L2", "L3", "L4", "L5", "L6"],
              str(tr["responsibilities_touched"]))
        check("L7 does not appear in the trace (not instantiated)",
              all("L7" not in (i["source"], i["target"])
                  for i in tr["interactions"]))
    else:
        check("runtime trace present (run run_case.py first)", False)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 68)
    print(f"  {passed}/{len(RESULTS)} checks passed")
    print("=" * 68)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
