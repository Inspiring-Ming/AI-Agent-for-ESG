"""L1 -- Client & Experience, as a FastAPI service.

The HTTP API and the portfolio analyst page. Every request is admitted by L2
and coordinated by the agent; see agentic/system.py for the request paths.

Environment: MCP_KNOWLEDGE_URL, MCP_COMPUTE_URL, MCP_PORTFOLIO_URL,
ANTHROPIC_API_KEY, ANTHROPIC_MODEL, SESSION_SECRET.

Run:  uvicorn service.api:app --host 0.0.0.0 --port 8090
"""

import os
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agentic import system
from agentic.adapters.esg_system import EnterpriseSystemUnavailable
from agentic.responsibilities.l2_protect import SUBJECTS, AccessControl
from agentic.trace.recorder import Trace

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(os.path.dirname(HERE), "ui", "index.html")

# Companies of the existing system for which carbon intensity can be computed
# (emissions and revenue both available), and examples where it cannot.
COVERED = ["STMicroelectronics NV", "Infineon Technologies AG",
           "NXP Semiconductors NV", "Microchip Technology Inc",
           "ON Semiconductor Corp", "United Microelectronics Corp",
           "Micron Technology Inc"]
NOT_COVERED = ["Taiwan Semiconductor Manufacturing Co Ltd",
               "Advanced Micro Devices Inc", "Tokyo Electron Ltd"]

RESP = {
    "L1": ("Client & Experience", "portfolio analyst page"),
    "L2": ("Access, Identity & Safety Control", "access gate"),
    "L3": ("Agent & Workflow Orchestration", "the agent"),
    "L4": ("Model Access & Inference", "Claude model access"),
    "L5": ("Enterprise Context & Knowledge", "ESG knowledge graph"),
    "L6": ("Tool & Action Runtime", "computation & portfolio services"),
}
LABEL = {
    "decide": "Model decides the next step",
    "answer": "Model writes the answer",
    "answer_flagged": "Number check flags the draft; model is asked to revise",
    "discover_metrics": "Find which metrics the category has",
    "get_metric_definition": "Look up how the metric is calculated",
    "compute_metric": "Compute a holding's carbon intensity",
    "portfolio_intensity": "Compute the portfolio's carbon intensity",
    "propose_rebalance": "Propose a reweighting (needs approval)",
}

app = FastAPI(title="ESG portfolio agent", version="2.0")
ACCESS = AccessControl(rate_limit=60, per_seconds=3600)


class Holding(BaseModel):
    company: str
    weight_pct: float


class RunRequest(BaseModel):
    holdings: List[Holding] = Field(min_length=1, max_length=30)
    year: str = "2023"
    compare_year: Optional[str] = None
    question: str


def _describe(i) -> str:
    p = i.payload
    tool = p.get("tool")
    if i.purpose == "action intent":
        return {"compute_metric": f"Compute intensity: {p.get('company')}, "
                                  f"{p.get('year')}",
                "portfolio_intensity": f"Compute portfolio WACI for {p.get('year')}",
                "propose_rebalance": f"Propose reweighting ({p.get('year')})",
                }.get(tool, "Action")
    if i.purpose == "observation":
        if tool == "compute_metric":
            return (f"{p.get('company')}: {p.get('value')}" if p.get("value")
                    else f"{p.get('company')}: no value ({p.get('status')})")
        if p.get("waci") is not None:
            return f"Portfolio WACI {p.get('waci')}"
        return f"Status: {p.get('status')}" + (
            f", proposal {p.get('proposal_id')}" if p.get("proposal_id") else "")
    return {
        "request admission": f"Question about {p.get('holdings')} holdings "
                             f"({p.get('year')})",
        "approval decision": f"Decision on proposal {p.get('proposal_id')}"
                             + (f": {p.get('decision')}" if p.get("decision")
                                else ""),
        "authorized request + identity context":
            f"Admitted as {p.get('role')}; identity and trace id attached",
        "inference request": "Ask the model what to do next",
        "inference result": f"Model decision returned (contract: "
                            f"{p.get('contract')})",
        "capability discovery": f"Which metrics are in “{p.get('category')}”? "
                                f"(CQ3)",
        "discovered metrics": f"{p.get('count')} candidate metrics",
        "context retrieval": f"How is {p.get('metric')} calculated? (CQ1–CQ5)",
        "grounded context": f"Method: {p.get('method')}"
                            + (f"; model {p.get('model')}" if p.get("model")
                               else ""),
        "answer": "Answer returned to the portfolio manager",
        "decision outcome": f"Outcome: {p.get('status')}",
    }.get(i.purpose, i.purpose)


def _occ(trace):
    return {i.seq: {"seq": i.seq, "type": i.ttype, "source": i.source,
                    "target": i.target, "text": _describe(i)}
            for i in trace.interactions}


def _token(authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip()


@app.post("/api/session")
def session(role: str = "analyst"):
    """Demo sign-in: L2 issues a signed session token for a role."""
    subject = next((s for s, r in SUBJECTS.items() if r == role), None)
    if subject is None:
        raise HTTPException(422, "unknown role")
    return {"token": ACCESS.issue_token(subject), "subject": subject,
            "role": role}


@app.get("/api/companies")
def companies():
    return {"covered": COVERED, "not_covered": NOT_COVERED}


@app.post("/api/run")
def run(req: RunRequest, authorization: str = Header(default="")):
    request = req.model_dump(exclude_none=True)
    trace = Trace("api request")
    try:
        result = system.handle(request, _token(authorization), ACCESS, trace)
    except PermissionError as e:
        raise HTTPException(401, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except EnterpriseSystemUnavailable as e:
        raise HTTPException(503, str(e))

    occ = _occ(trace)
    steps = [{"action": p["action"],
              "label": LABEL.get(p["action"], p["action"]),
              "why": p["why"], "exchanges": [occ[s] for s in p["seqs"]]}
             for p in result.get("plan", [])]
    return {
        "status": result["status"], "answer": result.get("answer"),
        "error": result.get("error"), "metric": result.get("metric"),
        "framework": result.get("framework"),
        "portfolio": result.get("portfolio"),
        "portfolio_by_year": result.get("portfolio_by_year"),
        "computations": result.get("computations"),
        "proposal": result.get("proposal"),
        "grounding": result.get("grounding"),
        "entry": [occ[1], occ[2]], "steps": steps, "exit": [occ[max(occ)]],
        "summary": {"occurrences": len(trace.interactions),
                    "types": sorted({o["type"] for o in occ.values()}),
                    "responsibilities": trace.responsibilities_touched(),
                    "model_calls": result.get("model_calls"),
                    "model": result["provenance"]["inference_provider"],
                    "mechanism": system.MECHANISM},
        "responsibilities": RESP,
    }


@app.post("/api/proposals/{proposal_id}/{decision}")
def decide(proposal_id: str, decision: str,
           authorization: str = Header(default="")):
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "decision must be approve or reject")
    trace = Trace("approval decision")
    try:
        result = system.decide(proposal_id, decision == "approve",
                               _token(authorization), ACCESS, trace)
    except PermissionError as e:
        raise HTTPException(401, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"result": result, "exchanges": list(_occ(trace).values())}


@app.get("/", response_class=HTMLResponse)
def index():
    with open(UI, encoding="utf-8") as fh:
        return fh.read()
