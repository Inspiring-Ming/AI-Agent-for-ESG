#!/usr/bin/env python3
"""Architecture instantiation case study (Section V).

Instantiates the reference architecture over the ESG Metric System
(https://github.com/Inspiring-Ming/ESG-Metric-System, deployed at
https://esgalaxy.com.ngrok.dev) and executes the representative scenario:

    an analyst requests the calculation and explanation of a company's
    greenhouse-gas emissions intensity for a reporting period and framework.

Enterprise grounding is ontology-driven traversal of the ESG Metric Knowledge
Graph through its CQ1-CQ7 competency questions; the metric computation is an
existing deterministic service operation.

Outputs, written to output/:
  runtime_trace.json      interactions recorded while the scenario ran
  component_mapping.json  concrete component -> responsibility mapping
  variability.json        conditional capabilities and the condition for each

Run:  python3 run_case.py [--mechanism http|local] [--esg-root PATH]
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
from agentic.trace.recorder import Trace                              # noqa: E402
from agentic.adapters.esg_system import HttpAdapter, LocalAdapter     # noqa: E402
from agentic.responsibilities.l1_interact import AnalystInterface     # noqa: E402
from agentic.responsibilities.l2_protect import AccessControl         # noqa: E402
from agentic.responsibilities.l3_coordinate import AgentRuntime       # noqa: E402
from agentic.responsibilities.l4_infer import ModelAccess             # noqa: E402
from agentic.responsibilities.l5_ground import EnterpriseKnowledgeGraph  # noqa: E402
from agentic.responsibilities.l6_act import ActionRuntime             # noqa: E402

SCENARIO = {
    "company": "STMicroelectronics NV",
    "metric": "GHGEmissionIntensity",
    "year": "2023",
    "industry": "semiconductors",
    "category": "Greenhouse Gas Emissions",
}

ENTITLEMENTS = ["esg.metric.compute"]

VARIABILITY = [
    {"capability": "Asynchronous / event-driven execution",
     "responsibility": "L7", "instantiated": False,
     "condition": "workload requires decoupling or long-running execution",
     "reason": "the metric request completes through direct synchronous "
               "service interaction; report generation would introduce it"},
    {"capability": "Multi-agent collaboration",
     "responsibility": "L3", "instantiated": False,
     "condition": "execution involves multiple collaborating agents",
     "reason": "a single coordinating agent is sufficient for the scenario"},
    {"capability": "Human approval gate",
     "responsibility": "L6", "instantiated": False,
     "condition": "action is consequential and governance requires approval",
     "reason": "metric computation is a bounded analytical read"},
    {"capability": "Execution isolation / sandboxing",
     "responsibility": "L6", "instantiated": False,
     "condition": "risk or execution environment requires isolation",
     "reason": "the invoked capability is a trusted first-party service"},
    {"capability": "Persistent memory across executions",
     "responsibility": "L5", "instantiated": False,
     "condition": "task requires recall across separate executions",
     "reason": "the scenario is a single stateless request"},
    {"capability": "Evaluation and observability",
     "responsibility": "L9", "instantiated": False,
     "condition": "deployed operation requires telemetry and evaluation",
     "reason": "not exercised by a single traced execution"},
]


def build(mechanism: str, esg_root: str, trace: Trace):
    adapter = (HttpAdapter() if mechanism == "http"
               else LocalAdapter(esg_root))
    access = AccessControl()                              # L2
    ground = EnterpriseKnowledgeGraph(adapter)            # L5
    infer = ModelAccess()                                 # L4
    act = ActionRuntime(adapter)                          # L6
    agent = AgentRuntime(ground, infer, act, trace)       # L3
    client = AnalystInterface(access, agent, trace)       # L1
    return client, access, infer, act, adapter


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mechanism", choices=["http", "local"], default="http",
                    help="realization mechanism for the ESG system")
    ap.add_argument("--esg-root", default=DEFAULT_ESG_ROOT,
                    help="path to a local clone of the ESG Metric System")
    args = ap.parse_args()

    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)

    trace = Trace("ESG greenhouse-gas emissions intensity request")
    client, access, infer, act, adapter = build(
        args.mechanism, args.esg_root, trace)

    print("=" * 70)
    print("ARCHITECTURE INSTANTIATION — ESG metric computation scenario")
    print("=" * 70)
    print(f"Request     : {SCENARIO['metric']} for {SCENARIO['company']} "
          f"({SCENARIO['year']})")
    print(f"L5 grounding: ESG Metric Knowledge Graph via CQ1–CQ7")
    print(f"L6 mechanism: {act.mechanism}")
    print(f"L4 provider : {infer.provider_name}")

    token = access.issue_token("analyst@enterprise.example")
    response = client.submit_metric_request(
        token=token, entitlements=ENTITLEMENTS, **SCENARIO)

    print("\nResponse")
    print("-" * 70)
    if response["status"] != "success":
        print("  FAILED:", response.get("message"))
        trace.print_trace()
        return 1
    print("  " + response["headline"])
    print("  framework:", response.get("framework"))
    print("  " + response["explanation"])
    print("\n  Agent plan (L3):")
    for i, step in enumerate(response.get("plan", []), 1):
        print(f"    {i}. {step}")
    cqs = response["provenance"]["knowledge_graph"]["competency_questions"]
    print(f"\n  Knowledge-graph competency questions exercised ({len(cqs)}):")
    for q in cqs:
        print("    -", q)

    trace.print_trace()
    trace.to_json(os.path.join(out, "runtime_trace.json"))

    mapping = [
        {"component": "Analyst interface", "responsibility": "L1",
         "verb": "Interact", "origin": "case study (mirrors ESG web interface)"},
        {"component": "Access gate: signed session, validation, rate limit",
         "responsibility": "L2", "verb": "Protect",
         "origin": "case study (models the authors' ESG demo access gate)"},
        {"component": "Agent runtime / orchestrator", "responsibility": "L3",
         "verb": "Coordinate",
         "origin": "case study (occupies the model-selection and session seam "
                   "of the existing system)"},
        {"component": "Model access and explanation provider",
         "responsibility": "L4", "verb": "Infer", "origin": "case study"},
        {"component": "ESG Metric Knowledge Graph (RDF) via CQ1–CQ7",
         "responsibility": "L5", "verb": "Ground",
         "origin": "existing ESG Metric System"},
        {"component": "Metric-computation service (/api/CSservice/calculate)",
         "responsibility": "L6", "verb": "Act",
         "origin": "existing ESG Metric System"},
        {"component": "Deployed service platform (container, gunicorn, "
                      "health check)", "responsibility": "L8", "verb": "Operate",
         "origin": "existing ESG Metric System deployment"},
    ]
    with open(os.path.join(out, "component_mapping.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"scenario": SCENARIO,
                   "mechanism": act.mechanism,
                   "source_system": {
                       "repository":
                           "https://github.com/Inspiring-Ming/ESG-Metric-System",
                       "deployment": "https://esgalaxy.com.ngrok.dev"},
                   "mapping": mapping}, fh, indent=2)

    with open(os.path.join(out, "variability.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"conditional_capabilities": VARIABILITY}, fh, indent=2)

    inst = sorted({m["responsibility"] for m in mapping})
    print(f"\n  Responsibilities instantiated: {len(inst)}/10 "
          f"({', '.join(inst)})")
    print(f"  Conditional capabilities not instantiated: {len(VARIABILITY)}")
    print(f"  Evidence written to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
