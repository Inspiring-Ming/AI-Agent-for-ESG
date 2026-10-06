"""MCP server for L6 -- Tool & Action Runtime (execution side).

Exposes the existing ESG metric-computation service as an MCP tool. The
computation itself remains a deterministic service operation of the existing
system; this server only makes it reachable through MCP.

Resource-specific authorization is enforced by the L6 action runtime in the
agent host before this tool is invoked (invariant I3), so the
model never supplies or sees credentials.

Tools
  compute_metric(industry, company, year, metric)

Run:  python -m mcp_servers.compute_server   (env: ESG_URL, MCP_PORT)
"""

import os

from mcp.server.mcpserver import MCPServer

from agentic.adapters.esg_system import HttpAdapter

ESG_URL = os.environ.get("ESG_URL", "http://localhost:8080")
PORT = int(os.environ.get("MCP_PORT", "8102"))

mcp = MCPServer("esg-compute")


@mcp.tool()
def compute_metric(industry: str, company: str, year: str, metric: str) -> dict:
    """Compute an ESG metric for a company and reporting year with the
    existing computation service; returns the value, unit, calculation model,
    equation, input values, and implementation as provenance."""
    return HttpAdapter(base=ESG_URL).calculate(industry, company, year, [metric])


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
