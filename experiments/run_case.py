#!/usr/bin/env python3
"""Worked example (Section V).

Runs one portfolio question through the deployed request path
(agentic/system.py): a portfolio manager asks for the 2023 carbon intensity of
a four-holding semiconductor portfolio, one holding of which lacks revenue
data, and which holdings drive it.

Outputs, written to output/:
  runtime_trace.json      interaction occurrences recorded during the request
  component_mapping.json  case component -> responsibility
  variability.json        conditional capabilities and the condition for each

Run (inside the Compose stack):  python experiments/run_case.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
sys.path.insert(0, HERE)

from agentic import system                                         # noqa: E402
from agentic.adapters.esg_system import EnterpriseSystemUnavailable  # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl      # noqa: E402
from agentic.scenarios import WORKED_EXAMPLE                       # noqa: E402
from agentic.trace.recorder import Trace                           # noqa: E402

MAPPING = [
    ("L1", "Web service and portfolio analyst page", "this package"),
    ("L2", "Access gate: signed session token, role-based entitlements "
           "(portfolio manager, compliance officer), request validation, rate "
           "limit, egress check", "this package"),
    ("L3", "Agent runtime: model-driven tool-use loop with execution "
           "constraints", "this package"),
    ("L4", "Model access: Claude, inference-contract validation, "
           "server-side fallback", "this package"),
    ("L5", "ESG knowledge graph (competency questions) behind an MCP server",
     "existing ESG system"),
    ("L6", "Metric-computation service behind an MCP server",
     "existing ESG system"),
    ("L6", "Portfolio and compliance service (WACI, pre-trade mandate "
           "check) behind an MCP server; entitlement checks; override "
           "approval gate", "this package"),
    ("L8", "Docker Compose deployment of all services", "this package"),
]

VARIABILITY = [
    {"capability": "Action-policy or approval gate", "responsibility": "L6",
     "condition": "action is consequential (a trade instruction)",
     "instantiated": True,
     "note": "every submitted trade is checked against the fund mandate "
             "(action policy); a breaching trade needs a compliance officer's "
             "override (approval gate); analytical reads bypass both"},
    {"capability": "Asynchronous / event-driven execution",
     "responsibility": "L7", "instantiated": False,
     "condition": "workload requires decoupling or long-running execution",
     "reason": "requests complete synchronously in under a minute"},
    {"capability": "Multi-agent collaboration", "responsibility": "L3",
     "instantiated": False,
     "condition": "execution involves multiple collaborating agents",
     "reason": "a single coordinating agent is sufficient"},
    {"capability": "Execution isolation", "responsibility": "L6",
     "instantiated": False, "condition": "untrusted or high-risk execution",
     "reason": "invoked capabilities are trusted first-party services"},
    {"capability": "Persistent cross-execution memory", "responsibility": "L5",
     "instantiated": False,
     "condition": "task requires recall across separate executions",
     "reason": "each question is answered independently"},
    {"capability": "Evaluation and observability", "responsibility": "L9",
     "instantiated": False,
     "condition": "deployed operation requires telemetry and evaluation",
     "reason": "evidence is recorded per request but not correlated by a "
               "separate L9 service"},
]


def main() -> int:
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)

    access = AccessControl()
    trace = Trace("ESG portfolio carbon-intensity question")
    token = access.issue_token("portfolio.manager@enterprise.example")
    result = system.handle(WORKED_EXAMPLE, token, access, trace)

    print("=" * 70)
    print("WORKED EXAMPLE")
    print("=" * 70)
    print(f"status : {result['status']}  "
          f"({result['model_calls']} model calls, "
          f"{result['l6_invocations']} L6 invocations)")
    print(f"answer :\n{result['answer']}\n")
    print(f"number check: {result['grounding']}")
    print(f"portfolio: {json.dumps(result['portfolio'], indent=1)}")
    print("\nplan (L3):")
    for i, p in enumerate(result["plan"], 1):
        print(f"  {i:>2}. {p['action']:<22} occ {p['seqs']}  {p['why'][:80]}")
    trace.print_trace()

    trace.to_json(os.path.join(out, "runtime_trace.json"))
    with open(os.path.join(out, "worked_example.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"request": WORKED_EXAMPLE,
                   "result": {k: result[k] for k in (
                       "status", "answer", "grounding", "portfolio",
                       "computations", "model_calls", "l6_invocations")}},
                  fh, indent=2, default=str)
    with open(os.path.join(out, "component_mapping.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"mechanism": system.MECHANISM,
                   "mapping": [{"responsibility": r, "component": c,
                                "origin": o} for r, c, o in MAPPING]},
                  fh, indent=2)
    with open(os.path.join(out, "variability.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"conditional_capabilities": VARIABILITY}, fh, indent=2)

    inst = sorted({r for r, _, _ in MAPPING})
    print(f"\nresponsibilities instantiated: {len(inst)}/10 ({', '.join(inst)})")
    print(f"written to {out}/")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnterpriseSystemUnavailable as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(2)
