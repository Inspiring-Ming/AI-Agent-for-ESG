#!/usr/bin/env python3
"""Goal-variation experiment.

Runs the same coordinator against several goals and records, for each, the
action sequence it chose, the interaction occurrences it produced, and the
interaction types it realized.

The purpose is to test the architectural claim that L0--L9 define responsibility
boundaries rather than a fixed runtime pipeline. If the claim holds, goals that
differ in what they require should produce different action sequences and
different sets of realized interaction types, using the same responsibilities
and the same coordinator.

Run:  python3 run_goals.py [--mechanism http|local]
"""

import argparse
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ESG_ROOT = os.environ.get(
    "ESG_ROOT", os.path.join(os.path.dirname(HERE), "esg-knowledge-graph-demo"))
sys.path.insert(0, HERE)

from agentic.trace.recorder import Trace, T_TYPES                     # noqa: E402
from agentic.adapters.esg_system import HttpAdapter, LocalAdapter     # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl         # noqa: E402
from agentic.responsibilities.l3_coordinate import AgentRuntime       # noqa: E402
from agentic.responsibilities.l4_infer import ModelAccess             # noqa: E402
from agentic.responsibilities.l5_ground import EnterpriseKnowledgeGraph  # noqa: E402
from agentic.responsibilities.l6_act import ActionRuntime             # noqa: E402

COMPANY, YEAR, INDUSTRY = "STMicroelectronics NV", "2023", "semiconductors"
CATEGORY = "Greenhouse Gas Emissions"

GOALS = [
    {"id": "G1",
     "description": "named metric requiring a calculation model, with explanation",
     "goal": {"company": COMPANY, "year": YEAR, "industry": INDUSTRY,
              "category": CATEGORY, "metric": "GHGEmissionIntensity",
              "explain": True}},
    {"id": "G2",
     "description": "same metric, result only (no explanation requested)",
     "goal": {"company": COMPANY, "year": YEAR, "industry": INDUSTRY,
              "category": CATEGORY, "metric": "GHGEmissionIntensity",
              "explain": False}},
    {"id": "G3",
     "description": "directly measured metric, with explanation",
     "goal": {"company": COMPANY, "year": YEAR, "industry": INDUSTRY,
              "category": CATEGORY, "metric": "GrossGlobalScope1Emissions",
              "explain": True}},
    {"id": "G4",
     "description": "no metric named; agent selects by required method",
     "goal": {"company": COMPANY, "year": YEAR, "industry": INDUSTRY,
              "category": CATEGORY, "prefer_method": "calculation_model",
              "explain": True}},
    {"id": "G5",
     "description": "goal that no discovered metric satisfies",
     "goal": {"company": COMPANY, "year": YEAR, "industry": INDUSTRY,
              "category": CATEGORY, "metric": "NonexistentMetric",
              "explain": True}},
]


def build(mechanism, esg_root, trace):
    adapter = HttpAdapter() if mechanism == "http" else LocalAdapter(esg_root)
    return (AccessControl(),
            AgentRuntime(EnterpriseKnowledgeGraph(adapter), ModelAccess(),
                         ActionRuntime(adapter), trace))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mechanism", choices=["http", "local"], default="http")
    ap.add_argument("--esg-root", default=DEFAULT_ESG_ROOT,
                    help="path to a local clone of the ESG Metric System")
    args = ap.parse_args()

    print("=" * 76)
    print("GOAL-VARIATION EXPERIMENT")
    print("=" * 76)

    rows = []
    for case in GOALS:
        trace = Trace(case["id"])
        access, agent = build(args.mechanism, args.esg_root, trace)
        principal = access.admit(
            access.issue_token("analyst@enterprise.example"),
            {"company": COMPANY, "metric": case["goal"].get("metric", "any"),
             "year": YEAR, "industry": INDUSTRY},
            ["esg.metric.compute"])

        result = agent.pursue(case["goal"], principal)
        actions = [t["action"] for t in result.get("plan", [])]
        types = trace.occurrences_by_type()
        resp = trace.responsibilities_touched()

        rows.append({
            "id": case["id"], "description": case["description"],
            "status": result["status"],
            "actions": actions,
            "occurrences": len(trace.interactions),
            "types_realized": sorted(types),
            "occurrences_by_type": types,
            "responsibilities": resp,
            "value": result.get("value"),
            "measurement_method": result.get("measurement_method"),
            "explained": bool(result.get("explanation")),
            "rationale": result.get("selection_rationale"),
        })

        print(f"\n{case['id']}  {case['description']}")
        print(f"   status      : {result['status']}")
        print(f"   actions     : {' -> '.join(actions)}")
        print(f"   occurrences : {len(trace.interactions)}  "
              f"types: {sorted(types)}  {types}")
        print(f"   resp. used  : {resp}")
        if result.get("value"):
            print(f"   result      : {result['value']} "
                  f"({result.get('measurement_method')})"
                  f"{'  + explanation' if result.get('explanation') else ''}")
        if result.get("rationale"):
            print(f"   selection   : {result['rationale']}")
        if result.get("error"):
            print(f"   error       : {result['error']}")

    # ---- variation summary ------------------------------------------------
    seqs = {tuple(r["actions"]) for r in rows}
    occs = {r["occurrences"] for r in rows}
    tsets = {tuple(r["types_realized"]) for r in rows}
    succeeded = [r for r in rows if r["status"] == "success"]

    print("\n" + "=" * 76)
    print(f"  goals executed              : {len(rows)}")
    print(f"  distinct action sequences   : {len(seqs)}")
    print(f"  distinct occurrence counts  : {sorted(occs)}")
    print(f"  distinct realized type sets : {len(tsets)}")
    for t in sorted(tsets):
        print(f"      {list(t)}")
    print(f"  goals satisfied             : {len(succeeded)}/{len(rows)}")
    print(f"  interaction types defined   : {len(T_TYPES)}")
    print("=" * 76)

    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "goal_variation.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"mechanism": args.mechanism,
                   "summary": {"goals": len(rows),
                               "distinct_action_sequences": len(seqs),
                               "distinct_occurrence_counts": sorted(occs),
                               "distinct_type_sets": len(tsets),
                               "satisfied": len(succeeded)},
                   "goals": rows}, fh, indent=2)
    print(f"  written to {out}/goal_variation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
