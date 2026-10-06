#!/usr/bin/env python3
"""Interactive view of the ESG agent.

Type a request, run the real agent against the real ESG system, and see each
decision the agent made, which responsibility it engaged, what was exchanged,
and the final answer.

Run:  python3 ui/app.py            then open http://localhost:8090
      python3 ui/app.py --mechanism local --esg-root PATH
"""

import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from flask import Flask, jsonify, request                         # noqa: E402

from agentic.adapters.esg_system import (                         # noqa: E402
    EnterpriseSystemUnavailable, HttpAdapter, LocalAdapter)
from agentic.responsibilities.l2_protect import AccessControl     # noqa: E402
from agentic.responsibilities.l3_coordinate import AgentRuntime   # noqa: E402
from agentic.responsibilities.l4_infer import ModelAccess         # noqa: E402
from agentic.responsibilities.l5_ground import EnterpriseKnowledgeGraph  # noqa: E402
from agentic.responsibilities.l6_act import ActionRuntime         # noqa: E402
from agentic.trace.recorder import Trace                          # noqa: E402

RESP = {
    "L1": ("Client & Experience", "analyst interface", "new"),
    "L2": ("Access, Identity & Safety Control", "access gate", "new"),
    "L3": ("Agent & Workflow Orchestration", "the agent", "new"),
    "L4": ("Model Access & Inference", "explanation provider", "new"),
    "L5": ("Enterprise Context & Knowledge", "ESG knowledge graph", "existing"),
    "L6": ("Tool & Action Runtime", "ESG computation service", "existing"),
}

# how many recorded exchanges each agent action produces
ACTION_EXCHANGES = {"discover": 2, "ground": 2, "compute": 2, "explain": 2}

ACTION_LABEL = {
    "discover": "Find out what metrics exist",
    "select": "Choose a metric",
    "ground": "Look up how to calculate it",
    "compute": "Calculate the value",
    "explain": "Explain the result",
    "abort": "Stop: cannot be done",
    "finish": "Done",
}

app = Flask(__name__)
ADAPTER = None


def describe(it):
    p, purpose = it["payload"], it["purpose"]
    return {
        "request admission": f"Request for {p.get('company')} ({p.get('year')})",
        "authorized request + identity context":
            "Request admitted; identity and trace id attached",
        "capability discovery":
            f"Which metrics are in “{p.get('category')}”? (CQ3)",
        "discovered metrics": f"{p.get('count')} candidate metrics",
        "context retrieval": f"How is {p.get('metric')} defined and calculated?",
        "grounded context":
            f"Calculation method: {p.get('method')}"
            + (f"; model {p.get('model')}" if p.get('model') else "")
            + f" (answered with CQ1–CQ{p.get('competency_questions')})",
        "action intent": f"Compute {p.get('metric')}",
        "observation": f"Computed value: {p.get('value')}",
        "inference request": "Write an explanation of the result",
        "inference result": "Explanation produced (output checked)",
        "result and explanation": "Answer returned to the analyst",
    }.get(purpose, purpose)


def run_goal(goal):
    trace = Trace("ui request")
    access = AccessControl()
    ground = EnterpriseKnowledgeGraph(ADAPTER)
    agent = AgentRuntime(ground, ModelAccess(), ActionRuntime(ADAPTER), trace)

    # L1 -> L2 -> L3, as in the instantiation
    trace.record("L1", "L2", "request admission", ttype="T1",
                 company=goal["company"], year=goal["year"])
    principal = access.admit(
        access.issue_token("analyst@enterprise.example"),
        {"company": goal["company"], "metric": goal.get("metric") or "any",
         "year": goal["year"], "industry": goal["industry"]},
        ["esg.metric.compute"])
    trace.record("L2", "L3", "authorized request + identity context",
                 ttype="T2", trace_id=principal["trace_id"])

    result = agent.pursue(goal, principal)
    trace.record("L3", "L1", "result and explanation", ttype="T1",
                 value=result.get("value"))

    occ = [{"seq": i.seq, "type": i.ttype, "source": i.source,
            "target": i.target, "text": describe(
                {"payload": i.payload, "purpose": i.purpose})}
           for i in trace.interactions]

    # attach the agent's decisions to the exchanges they produced
    steps, cursor = [], 2          # first two occurrences are L1/L2 admission
    for p in result.get("plan", []):
        n = ACTION_EXCHANGES.get(p["action"], 0)
        steps.append({"action": p["action"],
                      "label": ACTION_LABEL.get(p["action"], p["action"]),
                      "why": p["why"],
                      "exchanges": occ[cursor:cursor + n]})
        cursor += n

    return {
        "status": result["status"],
        "metric": result.get("metric"),
        "value": result.get("value"),
        "unit": result.get("unit"),
        "method": result.get("measurement_method"),
        "framework": result.get("framework"),
        "explanation": result.get("explanation"),
        "error": result.get("error"),
        "rationale": result.get("selection_rationale"),
        "inputs": ((result.get("provenance") or {}).get("computation")
                   or {}).get("inputs"),
        "equation": ((result.get("provenance") or {}).get("computation")
                     or {}).get("equation"),
        "entry": occ[:2],
        "steps": steps,
        "exit": occ[cursor:],
        "summary": {
            "occurrences": len(trace.interactions),
            "types": sorted({o["type"] for o in occ}),
            "responsibilities": trace.responsibilities_touched(),
        },
        "responsibilities": RESP,
    }


@app.get("/api/metrics")
def metrics():
    cat = request.args.get("category", "Greenhouse Gas Emissions")
    ind = request.args.get("industry", "semiconductors")
    try:
        found = EnterpriseKnowledgeGraph(ADAPTER).metrics_in_category(ind, cat)
    except EnterpriseSystemUnavailable as e:
        return jsonify({"error": str(e)}), 503
    return jsonify({"metrics": found})


@app.post("/api/run")
def run():
    body = request.get_json(force=True)
    goal = {"company": body.get("company", "STMicroelectronics NV"),
            "year": body.get("year", "2023"),
            "industry": body.get("industry", "semiconductors"),
            "category": body.get("category", "Greenhouse Gas Emissions"),
            "explain": bool(body.get("explain", True))}
    if body.get("metric"):
        goal["metric"] = body["metric"]
    elif body.get("prefer_method"):
        goal["prefer_method"] = body["prefer_method"]
    try:
        return jsonify(run_goal(goal))
    except EnterpriseSystemUnavailable as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.get("/")
def index():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mechanism", choices=["http", "local"], default="http")
    ap.add_argument("--esg-root", default=os.environ.get(
        "ESG_ROOT", os.path.join(os.path.dirname(ROOT),
                                 "esg-knowledge-graph-demo")))
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()
    ADAPTER = HttpAdapter() if a.mechanism == "http" else LocalAdapter(a.esg_root)
    print(f"ESG agent UI on http://localhost:{a.port}  (mechanism: {a.mechanism})")
    app.run(host="127.0.0.1", port=a.port, debug=False)
