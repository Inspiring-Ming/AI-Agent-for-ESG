"""L1 -- Client & Experience, as a FastAPI service.

The HTTP API and the analyst page. Every request is admitted by L2 and then
coordinated by the agent; see agentic/system.py for the request path.

Environment: MCP_KNOWLEDGE_URL, MCP_COMPUTE_URL, ANTHROPIC_API_KEY,
ANTHROPIC_MODEL, SESSION_SECRET.

Run:  uvicorn service.api:app --host 0.0.0.0 --port 8090
"""

import os
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agentic import system
from agentic.adapters.esg_system import EnterpriseSystemUnavailable
from agentic.responsibilities.l2_protect import AccessControl
from agentic.trace.recorder import Trace

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(os.path.dirname(HERE), "ui", "index.html")

RESP = {
    "L1": ("Client & Experience", "analyst interface", "new"),
    "L2": ("Access, Identity & Safety Control", "access gate", "new"),
    "L3": ("Agent & Workflow Orchestration", "the agent", "new"),
    "L4": ("Model Access & Inference", "Claude model access", "new"),
    "L5": ("Enterprise Context & Knowledge", "ESG knowledge graph", "existing"),
    "L6": ("Tool & Action Runtime", "ESG computation service", "existing"),
}
LABEL = {
    "decide": "Model decides the next step",
    "answer": "Model writes the final answer",
    "discover_metrics": "Find out what metrics exist",
    "get_metric_definition": "Look up how the metric is calculated",
    "compute_metric": "Calculate the value",
}

app = FastAPI(title="ESG agent", version="1.0")
ACCESS = AccessControl(rate_limit=60, per_seconds=3600)


class RunRequest(BaseModel):
    company: str = "STMicroelectronics NV"
    year: str = "2023"
    industry: str = "semiconductors"
    category: str = "Greenhouse Gas Emissions"
    metric: Optional[str] = None
    metrics: Optional[List[str]] = None
    prefer_method: Optional[str] = None
    explain: bool = True


def _describe(i) -> str:
    p = i.payload
    return {
        "request admission": f"Request for {p.get('company')} ({p.get('year')})",
        "authorized request + identity context":
            "Request admitted; identity and trace id attached",
        "inference request": f"Ask the model what to do next ({p.get('provider')})",
        "inference result": f"Model decision returned (contract: {p.get('contract')})",
        "capability discovery": f"Which metrics are in “{p.get('category')}”? (CQ3)",
        "discovered metrics": f"{p.get('count')} candidate metrics",
        "context retrieval": f"How is {p.get('metric')} defined and calculated?",
        "grounded context": f"Method: {p.get('method')}"
                            + (f"; model {p.get('model')}" if p.get('model') else ""),
        "action intent": f"Compute {p.get('metric')}",
        "observation": f"Result: {p.get('status')}"
                       + (f", value {p.get('value')}" if p.get('value') else ""),
        "result and explanation": "Answer returned to the analyst",
    }.get(i.purpose, i.purpose)


@app.post("/api/session")
def session():
    """Demo sign-in: L2 issues a signed session token for the analyst."""
    return {"token": ACCESS.issue_token("analyst@enterprise.example")}


@app.get("/api/metrics")
def metrics(category: str = "Greenhouse Gas Emissions",
            industry: str = "semiconductors"):
    try:
        return {"metrics": system.knowledge().metrics_in_category(
            industry, category)}
    except EnterpriseSystemUnavailable as e:
        raise HTTPException(503, str(e))


@app.post("/api/run")
def run(req: RunRequest, authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    goal = {k: v for k, v in req.model_dump().items() if v not in (None, "")}
    trace = Trace("api request")
    try:
        result = system.handle(goal, token, ACCESS, trace)
    except PermissionError as e:
        raise HTTPException(401, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except EnterpriseSystemUnavailable as e:
        raise HTTPException(503, str(e))

    occ = {i.seq: {"seq": i.seq, "type": i.ttype, "source": i.source,
                   "target": i.target, "text": _describe(i)}
           for i in trace.interactions}
    steps = [{"action": p["action"],
              "label": LABEL.get(p["action"], p["action"]),
              "why": p["why"], "exchanges": [occ[s] for s in p["seqs"]]}
             for p in result.get("plan", [])]

    comp = (result.get("provenance") or {}).get("computation") or {}
    last = max(occ)
    return {
        "status": result["status"], "metric": result.get("metric"),
        "value": result.get("value"), "values": result.get("values"),
        "unit": result.get("unit"),
        "method": result.get("measurement_method"),
        "framework": result.get("framework"),
        "explanation": result.get("answer"),
        "error": result.get("error"),
        "rationale": result.get("selection_rationale"),
        "inputs": comp.get("inputs"), "equation": comp.get("equation"),
        "grounding": result.get("grounding"),
        "entry": [occ[1], occ[2]], "steps": steps, "exit": [occ[last]],
        "summary": {"occurrences": len(trace.interactions),
                    "types": sorted({o["type"] for o in occ.values()}),
                    "responsibilities": trace.responsibilities_touched(),
                    "model_calls": result.get("model_calls"),
                    "model": result.get("provenance", {}).get(
                        "inference_provider"),
                    "mechanism": system.MECHANISM},
        "responsibilities": RESP,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    with open(UI, encoding="utf-8") as fh:
        return fh.read()
