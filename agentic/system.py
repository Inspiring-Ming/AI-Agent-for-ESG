"""Assembly of the instantiated responsibilities and the request path.

One function, `handle`, is the path every request takes, whether it arrives at
the FastAPI service or from an experiment script:

    L1 -> L2  (T1)  request admission
    L2 -> L3  (T2)  authorized request + identity and trace context
    L3 <-> L4 (T3)  every model decision
    L3 <-> L5 (T4)  knowledge-graph retrieval, through MCP
    L3 <-> L6 (T5)  metric computation, through MCP
    L3 -> L1  (T1)  result, after the L2 egress check
"""

import os
from typing import Any, Dict, Optional

from agentic.adapters.mcp_clients import McpCompute, McpKnowledge
from agentic.responsibilities.l2_protect import AccessControl
from agentic.responsibilities.l3_coordinate import AgentRuntime
from agentic.responsibilities.l4_infer import ModelAccess
from agentic.responsibilities.l6_act import ActionRuntime
from agentic.trace.recorder import Trace

MECHANISM = "MCP (streamable HTTP)"
ENTITLEMENTS = ["esg.metric.compute"]


def knowledge() -> McpKnowledge:
    """L5: the existing knowledge graph, reached through its MCP server."""
    return McpKnowledge(os.environ.get("MCP_KNOWLEDGE_URL",
                                       "http://localhost:8101/mcp"))


def compute_backend() -> McpCompute:
    """Execution backend of L6: the existing computation service, via MCP."""
    return McpCompute(os.environ.get("MCP_COMPUTE_URL",
                                     "http://localhost:8102/mcp"))


def build_agent(trace: Trace, ground=None, backend=None,
                infer: Optional[ModelAccess] = None) -> AgentRuntime:
    """L3 wired to L4, L5 and L6; backends can be wrapped for probing."""
    return AgentRuntime(ground or knowledge(),
                        infer or ModelAccess(),
                        ActionRuntime(backend or compute_backend()),
                        trace)


def handle(goal: Dict[str, Any], token: str, access: AccessControl,
           trace: Trace, entitlements=ENTITLEMENTS) -> Dict[str, Any]:
    """Run one request through L1 -> L2 -> L3 -> L1, recording each exchange.

    Raises PermissionError / ValueError when L2 refuses the request.
    """
    trace.record("L1", "L2", "request admission", ttype="T1",
                 company=goal.get("company"), year=goal.get("year"))
    principal = access.admit(
        token, {"company": goal.get("company"), "year": goal.get("year"),
                "industry": goal.get("industry"),
                "metric": goal.get("metric") or "any"},
        entitlements)
    trace.record("L2", "L3", "authorized request + identity context",
                 ttype="T2", subject=principal["subject"],
                 trace_id=principal["trace_id"])

    result = build_agent(trace).pursue(goal, principal)

    trace.record("L3", "L1", "result and explanation", ttype="T1",
                 value=result.get("value"), unit=result.get("unit"))
    return access.egress(result)
