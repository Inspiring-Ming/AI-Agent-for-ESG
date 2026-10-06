#!/usr/bin/env python3
"""Representative request (Section V).

Runs one analyst request through the deployed request path (agentic/system.py):

    an analyst requests the greenhouse-gas emissions intensity of
    STMicroelectronics for 2023, with an explanation.

Outputs, written to output/:
  runtime_trace.json      interaction occurrences recorded during the request
  component_mapping.json  case component -> responsibility
  variability.json        conditional capabilities and the condition for each

Run (inside the Compose stack):  python run_case.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from agentic import system                                         # noqa: E402
from agentic.adapters.esg_system import EnterpriseSystemUnavailable  # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl      # noqa: E402
from agentic.trace.recorder import Trace                           # noqa: E402

SCENARIO = {"company": "STMicroelectronics NV", "year": "2023",
            "industry": "semiconductors", "category": "Greenhouse Gas Emissions",
            "metric": "GHGEmissionIntensity", "explain": True}

MAPPING = [
    ("L1", "FastAPI service and analyst page", "this package"),
    ("L2", "Access gate: signed session token, request validation, "
           "rate limit, egress check", "this package"),
    ("L3", "Agent runtime: model-driven tool-use loop with guardrails",
     "this package"),
    ("L4", "Model access: Claude, output-contract validation, "
           "server-side fallback", "this package"),
    ("L5", "ESG knowledge graph (RDF, competency questions) behind an "
           "MCP server", "existing ESG system"),
    ("L6", "Action runtime (entitlement check) + metric-computation service "
           "behind an MCP server", "existing ESG system"),
    ("L8", "Docker Compose deployment of all services", "this package"),
]

VARIABILITY = [
    {"capability": "Asynchronous / event-driven execution",
     "responsibility": "L7",
     "condition": "workload requires decoupling or long-running execution",
     "reason": "the request completes through direct synchronous calls"},
    {"capability": "Multi-agent collaboration", "responsibility": "L3",
     "condition": "execution involves multiple collaborating agents",
     "reason": "a single coordinating agent is sufficient"},
    {"capability": "Action-policy or approval gate", "responsibility": "L6",
     "condition": "action is consequential and governance requires approval",
     "reason": "metric computation is a bounded analytical read"},
    {"capability": "Execution isolation", "responsibility": "L6",
     "condition": "untrusted or high-risk execution",
     "reason": "the invoked capability is a trusted first-party service"},
    {"capability": "Persistent cross-execution memory", "responsibility": "L5",
     "condition": "task requires recall across separate executions",
     "reason": "each request is independent"},
    {"capability": "Evaluation and observability", "responsibility": "L9",
     "condition": "deployed operation requires telemetry and evaluation",
     "reason": "evidence is recorded per request but not correlated by a "
               "separate L9 service"},
]


def main() -> int:
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)

    access = AccessControl()
    trace = Trace("ESG greenhouse-gas emissions intensity request")
    token = access.issue_token("analyst@enterprise.example")
    result = system.handle(SCENARIO, token, access, trace)

    print("=" * 70)
    print("REPRESENTATIVE REQUEST")
    print("=" * 70)
    print(f"status : {result['status']}")
    print(f"value  : {result.get('value')} {result.get('unit') or ''}")
    print(f"model  : {result.get('provenance', {}).get('inference_provider')}"
          f" ({result.get('model_calls')} calls)")
    print(f"answer : {result.get('answer')}")
    print(f"number check: {result.get('grounding')}")
    print("\nplan (L3):")
    for i, p in enumerate(result.get("plan", []), 1):
        print(f"  {i}. {p['action']:<22} occ {p['seqs']}  {p['why'][:90]}")
    cqs = (((result.get("provenance") or {}).get("knowledge_graph") or {})
           .get("competency_questions", []))
    print(f"\ncompetency questions run by L5 ({len(cqs)}):")
    for q in cqs:
        print("  -", q)
    trace.print_trace()

    trace.to_json(os.path.join(out, "runtime_trace.json"))
    with open(os.path.join(out, "component_mapping.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"scenario": SCENARIO, "mechanism": system.MECHANISM,
                   "mapping": [{"responsibility": r, "component": c,
                                "origin": o} for r, c, o in MAPPING]},
                  fh, indent=2)
    with open(os.path.join(out, "variability.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"conditional_capabilities": VARIABILITY}, fh, indent=2)

    print(f"\nresponsibilities instantiated: {len(MAPPING)}/10 "
          f"({', '.join(r for r, _, _ in MAPPING)})")
    print(f"written to {out}/")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnterpriseSystemUnavailable as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(2)
