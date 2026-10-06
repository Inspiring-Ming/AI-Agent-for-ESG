"""MCP server for L5 -- Enterprise Context & Knowledge.

Exposes the ESG knowledge graph of the existing system as MCP tools, so the
agent reaches enterprise grounding through a standard interoperability protocol
(the mechanism the paper names for L5 interactions). The server owns retrieval
and context assembly; it never computes metric values (that is L6).

Tools
  discover_metrics(industry, category)            CQ3
  get_metric_definition(industry, category, metric)  CQ1-CQ5

Run:  python -m mcp_servers.knowledge_server   (env: ESG_URL, MCP_PORT)
"""

import os

from mcp.server.mcpserver import MCPServer

from agentic.adapters.esg_system import HttpAdapter
from agentic.responsibilities.l5_ground import EnterpriseKnowledgeGraph

ESG_URL = os.environ.get("ESG_URL", "http://localhost:8080")
PORT = int(os.environ.get("MCP_PORT", "8101"))

mcp = MCPServer("esg-knowledge")


def _kg() -> EnterpriseKnowledgeGraph:
    return EnterpriseKnowledgeGraph(HttpAdapter(base=ESG_URL))


@mcp.tool()
def discover_metrics(industry: str, category: str) -> dict:
    """List the ESG metrics a reporting category contains (competency question
    CQ3), with the calculation method each requires."""
    return {"metrics": _kg().metrics_in_category(industry, category)}


@mcp.tool()
def get_metric_definition(industry: str, category: str, metric: str) -> dict:
    """Return a metric's definition, calculation method, calculation model,
    required inputs, and provenance (competency questions CQ1-CQ5)."""
    return _kg().assemble_metric_context(industry, category, metric)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
