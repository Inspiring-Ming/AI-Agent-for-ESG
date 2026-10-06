"""Assembly of the instantiated responsibilities and the request paths.

`handle` is the path every portfolio question takes, whether it arrives at the
FastAPI service or from an experiment script:

    L1 -> L2  (T1)  request admission
    L2 -> L3  (T2)  authorized request + identity and trace context
    L3 <-> L4 (T3)  every model decision
    L3 <-> L5 (T4)  knowledge-graph retrieval, through MCP
    L3 <-> L6 (T5)  metric computation, portfolio analytics and pre-trade
                    compliance, through MCP
    L3 -> L1  (T1)  answer, after the L2 egress check

`decide` is the path of a compliance officer's decision on a trade held for an
override: L1 -> L2 -> L3 -> L6 approval gate -> L3 -> L1.
"""

import os
from typing import Any, Dict, Optional

from agentic.adapters.mcp_clients import McpCompute, McpKnowledge, McpPortfolio
from agentic.responsibilities.l2_protect import AccessControl
from agentic.responsibilities.l3_coordinate import AgentRuntime
from agentic.responsibilities.l4_infer import ModelAccess
from agentic.responsibilities.l6_act import ActionRuntime
from agentic.trace.recorder import Trace

MECHANISM = "MCP (streamable HTTP)"
DEFAULTS = {"fund": "ESG Semiconductor Fund", "industry": "semiconductors",
            "category": "Greenhouse Gas Emissions"}


def knowledge() -> McpKnowledge:
    """L5: the existing knowledge graph, reached through its MCP server."""
    return McpKnowledge(os.environ.get("MCP_KNOWLEDGE_URL",
                                       "http://localhost:8101/mcp"))


def compute_backend() -> McpCompute:
    """L6 backend: the existing computation service, via MCP."""
    return McpCompute(os.environ.get("MCP_COMPUTE_URL",
                                     "http://localhost:8102/mcp"))


def portfolio_backend() -> McpPortfolio:
    """L6 backend: the portfolio and compliance service, via MCP."""
    return McpPortfolio(os.environ.get("MCP_PORTFOLIO_URL",
                                       "http://localhost:8103/mcp"))


def action_runtime(compute=None, portfolio=None) -> ActionRuntime:
    return ActionRuntime(compute or compute_backend(),
                         portfolio or portfolio_backend())


def build_agent(trace: Trace, ground=None, act: Optional[ActionRuntime] = None,
                infer: Optional[ModelAccess] = None) -> AgentRuntime:
    """L3 wired to L4, L5 and L6; components can be wrapped for probing."""
    return AgentRuntime(ground or knowledge(), infer or ModelAccess(),
                        act or action_runtime(), trace)


def handle(request: Dict[str, Any], token: str, access: AccessControl,
           trace: Trace) -> Dict[str, Any]:
    """Run one question through L1 -> L2 -> L3 -> L1.

    Raises PermissionError / ValueError when L2 refuses the request.
    """
    goal = {**DEFAULTS, **request}
    trace.record("L1", "L2", "request admission", ttype="T1",
                 holdings=len(goal.get("holdings") or []),
                 year=goal.get("year"))
    principal = access.admit(token, goal)
    trace.record("L2", "L3", "authorized request + identity context",
                 ttype="T2", subject=principal["subject"],
                 role=principal["role"], trace_id=principal["trace_id"])

    result = build_agent(trace).pursue(goal, principal)

    trace.record("L3", "L1", "answer", ttype="T1", status=result["status"],
                 waci=(result.get("portfolio") or {}).get("waci"))
    return access.egress(result)


def decide(trade_id: str, approve: bool, token: str,
           access: AccessControl, trace: Trace) -> Dict[str, Any]:
    """Route an override decision through L1 -> L2 -> L3 -> L6 -> L3 -> L1."""
    trace.record("L1", "L2", "override decision", ttype="T1",
                 trade_id=trade_id)
    principal = access.admit(token, {"trade_id": trade_id})
    trace.record("L2", "L3", "authorized request + identity context",
                 ttype="T2", subject=principal["subject"],
                 role=principal["role"], trace_id=principal["trace_id"])
    agent = AgentRuntime(None, None, action_runtime(), trace)
    result = agent.decide_trade(trade_id, approve, principal)
    trace.record("L3", "L1", "decision outcome", ttype="T1",
                 status=result["status"])
    return access.egress(result)
