#!/usr/bin/env python3
"""Goal-variation experiment (Section V).

Runs the same deployed request path against goals that differ in what they
require, each several times, and records for every execution the action
sequence the agent chose, the interaction occurrences produced, the
interaction types realized, and whether the answer passed the number check.

If L0-L9 are responsibility boundaries rather than a fixed pipeline, goals that
require different things should produce different action sequences and type
sets with the same components. Because the planner is a language model, each
goal is repeated to measure whether its path is consistent.

Run (inside the Compose stack):  python run_goals.py [--repeats 3]
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from agentic import system                                         # noqa: E402
from agentic.adapters.esg_system import EnterpriseSystemUnavailable  # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl      # noqa: E402
from agentic.trace.recorder import Trace, T_TYPES                  # noqa: E402

BASE = {"company": "STMicroelectronics NV", "year": "2023",
        "industry": "semiconductors", "category": "Greenhouse Gas Emissions"}

GOALS = [
    ("G1", "named calculated metric, explanation requested",
     {"metric": "GHGEmissionIntensity", "explain": True}),
    ("G2", "same metric, result only",
     {"metric": "GHGEmissionIntensity", "explain": False}),
    ("G3", "named measured metric, explanation requested",
     {"metric": "GrossGlobalScope1Emissions", "explain": True}),
    ("G4", "no metric named; one requiring a calculation model",
     {"prefer_method": "calculation_model", "explain": True}),
    ("G5", "two named metrics, one calculated and one measured",
     {"metrics": ["GHGEmissionIntensity", "GrossGlobalScope1Emissions"],
      "explain": True}),
    ("G6", "metric the category does not contain",
     {"metric": "NonexistentMetric", "explain": True}),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()

    access = AccessControl(rate_limit=1000)
    rows = []
    for gid, desc, extra in GOALS:
        for rep in range(1, args.repeats + 1):
            trace = Trace(gid)
            result = system.handle(
                {**BASE, **extra}, access.issue_token("analyst@enterprise.example"),
                access, trace)
            types = trace.occurrences_by_type()
            row = {"id": gid, "repeat": rep, "description": desc,
                   "status": result["status"],
                   "actions": [p["action"] for p in result.get("plan", [])],
                   "occurrences": len(trace.interactions),
                   "types_realized": sorted(types),
                   "occurrences_by_type": types,
                   "responsibilities": trace.responsibilities_touched(),
                   "values": result.get("values"),
                   "model_calls": result.get("model_calls"),
                   "l6_invocations": result.get("l6_invocations"),
                   "grounded": result["grounding"]["grounded"],
                   "answer": result.get("answer")}
            rows.append(row)
            print(f"{gid}#{rep} {row['status']:<13} occ={row['occurrences']:<3}"
                  f" {row['types_realized']} {' > '.join(row['actions'])}"
                  f"  values={row['values']} grounded={row['grounded']}")

    per_goal = {}
    for r in rows:
        g = per_goal.setdefault(r["id"], {"sequences": set(), "occ": set(),
                                          "status": set(), "grounded": set(),
                                          "types": set()})
        g["sequences"].add(tuple(r["actions"]))
        g["occ"].add(r["occurrences"])
        g["status"].add(r["status"])
        g["grounded"].add(r["grounded"])
        g["types"].add(tuple(r["types_realized"]))
    consistency = {gid: {"distinct_sequences": len(v["sequences"]),
                         "occurrence_counts": sorted(v["occ"]),
                         "types": [list(t) for t in sorted(v["types"])],
                         "statuses": sorted(v["status"]),
                         "all_grounded": all(v["grounded"])}
                   for gid, v in per_goal.items()}
    summary = {"executions": len(rows),
               "distinct_action_sequences":
                   len({tuple(r["actions"]) for r in rows}),
               "distinct_occurrence_counts":
                   sorted({r["occurrences"] for r in rows}),
               "distinct_type_sets":
                   len({tuple(r["types_realized"]) for r in rows}),
               "all_grounded": all(r["grounded"] for r in rows),
               "per_goal": consistency}

    print("\n" + "=" * 76)
    print(json.dumps(summary, indent=2))
    print(f"interaction types defined: {len(T_TYPES)}")

    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "goal_variation.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"mechanism": system.MECHANISM, "repeats": args.repeats,
                   "summary": summary, "executions": rows}, fh, indent=2)
    print(f"written to {out}/goal_variation.json")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnterpriseSystemUnavailable as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(2)
