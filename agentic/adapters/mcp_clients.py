"""MCP clients for the L5 and L6 servers.

The agent reaches the existing system's knowledge graph (L5) and computation
service (L6), and the portfolio service (L6), only through these clients.
"""

import asyncio
import json
from typing import Any, Dict, List

from mcp import Client

from agentic.adapters.esg_system import EnterpriseSystemUnavailable


def _call(url: str, tool: str, args: Dict[str, Any]) -> Any:
    async def run():
        async with Client(url) as client:
            return await client.call_tool(tool, args)
    try:
        res = asyncio.run(run())
    except Exception as exc:                               # noqa: BLE001
        raise EnterpriseSystemUnavailable(url, f"{type(exc).__name__}: {exc}")
    if getattr(res, "is_error", None) or getattr(res, "isError", None):
        text = " ".join(getattr(c, "text", "") for c in res.content)
        raise EnterpriseSystemUnavailable(url, f"tool {tool} failed: {text}")
    sc = getattr(res, "structured_content", None) or getattr(
        res, "structuredContent", None)
    if sc:
        # MCPServer wraps non-object returns as {"result": ...}
        return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
    return json.loads(res.content[0].text)


class McpKnowledge:
    """L5 through MCP: same interface as EnterpriseKnowledgeGraph."""

    RESPONSIBILITY = "L5"
    mechanism = "MCP (streamable HTTP)"

    def __init__(self, url: str):
        self.url = url

    def metrics_in_category(self, industry: str, category: str) -> List[Dict]:
        return _call(self.url, "discover_metrics",
                     {"industry": industry, "category": category})["metrics"]

    def assemble_metric_context(self, industry: str, category: str,
                                metric: str) -> Dict[str, Any]:
        return _call(self.url, "get_metric_definition",
                     {"industry": industry, "category": category,
                      "metric": metric})


class McpCompute:
    """Execution backend for the L6 action runtime, reached through MCP."""

    mechanism = "MCP (streamable HTTP)"

    def __init__(self, url: str):
        self.url = url

    def calculate(self, industry: str, company: str, year: str,
                  metrics: List[str]) -> Dict[str, Any]:
        return _call(self.url, "compute_metric",
                     {"industry": industry, "company": company,
                      "year": str(year), "metric": metrics[0]})


class McpPortfolio:
    """Portfolio analytics backend for the L6 action runtime, via MCP."""

    mechanism = "MCP (streamable HTTP)"

    def __init__(self, url: str):
        self.url = url

    def portfolio_intensity(self, holdings, year, previous=None):
        args = {"holdings": holdings, "year": str(year)}
        if previous:
            args["previous"] = previous
        return _call(self.url, "portfolio_intensity", args)

    def evaluate_rebalance(self, holdings, target_weights, year):
        return _call(self.url, "evaluate_rebalance",
                     {"holdings": holdings, "target_weights": target_weights,
                      "year": str(year)})
