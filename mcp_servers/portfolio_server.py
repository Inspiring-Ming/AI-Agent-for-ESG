"""MCP server for portfolio analytics -- an L6 capability added by this package.

Deterministic portfolio calculations over per-holding carbon intensities that
the existing ESG computation service has produced. The agent never performs
this arithmetic itself: it requests it as an action and receives the result.

Weighted average carbon intensity (WACI), the portfolio carbon metric
recommended by the TCFD, is the weight-averaged intensity of the holdings:

    WACI = sum_i (w_i / W) * intensity_i      over holdings with an intensity,

where W is the total weight of those holdings. Holdings without an intensity
are excluded and reported, and the covered weight is returned so that partial
coverage is visible.

Tools
  portfolio_intensity(holdings, year, previous)   WACI, contributions, coverage
  evaluate_rebalance(holdings, target_weights, year)   WACI under new weights

Run:  python -m mcp_servers.portfolio_server   (env: MCP_PORT)
"""

import os
from typing import Dict, List, Optional

from mcp.server.mcpserver import MCPServer

PORT = int(os.environ.get("MCP_PORT", "8103"))

mcp = MCPServer("esg-portfolio")


def _waci(holdings: List[Dict]) -> Dict:
    covered = [h for h in holdings if h.get("intensity") is not None]
    missing = [{"company": h["company"], "weight_pct": h["weight_pct"],
                "reason": h.get("reason") or "no intensity available"}
               for h in holdings if h.get("intensity") is None]
    w_cov = sum(h["weight_pct"] for h in covered)
    if not covered or w_cov <= 0:
        return {"waci": None, "covered_weight_pct": 0.0,
                "contributions": [], "not_covered": missing}
    waci = sum(h["weight_pct"] * h["intensity"] for h in covered) / w_cov
    contributions = sorted(
        ({"company": h["company"], "weight_pct": h["weight_pct"],
          "intensity": round(h["intensity"], 2),
          "contribution": round(h["weight_pct"] * h["intensity"] / w_cov, 2),
          "share_of_waci_pct": round(100 * h["weight_pct"] * h["intensity"]
                                     / (w_cov * waci), 1)}
         for h in covered), key=lambda c: -c["contribution"])
    return {"waci": round(waci, 2),
            "covered_weight_pct": round(w_cov, 1),
            "contributions": contributions,
            "not_covered": missing}


@mcp.tool()
def portfolio_intensity(holdings: List[Dict], year: str,
                        previous: Optional[Dict] = None) -> Dict:
    """Weighted average carbon intensity (WACI) of a portfolio for one year.

    holdings: [{company, weight_pct, intensity (or null), reason}]
    previous: optional earlier result {year, waci} to compare against.
    """
    out = {"year": year, "unit": "t CO2e per USD million revenue",
           **_waci(holdings)}
    if previous and previous.get("waci") and out["waci"] is not None:
        a, b = sorted([(previous["year"], previous["waci"]),
                       (year, out["waci"])])
        out["change"] = {"from_year": a[0], "to_year": b[0],
                         "from_waci": a[1], "to_waci": b[1],
                         "change": round(b[1] - a[1], 2),
                         "change_pct": round(100 * (b[1] - a[1]) / a[1], 1)}
    return out


@mcp.tool()
def evaluate_rebalance(holdings: List[Dict], target_weights: List[Dict],
                       year: str) -> Dict:
    """WACI of the portfolio under proposed target weights.

    target_weights: [{company, weight_pct}] covering only current holdings,
    each weight >= 0, summing to 100.
    """
    current = {h["company"]: h for h in holdings}
    targets = {t["company"]: float(t["weight_pct"]) for t in target_weights}
    unknown = sorted(set(targets) - set(current))
    if unknown:
        return {"valid": False, "error": f"not current holdings: {unknown}"}
    if any(w < 0 for w in targets.values()):
        return {"valid": False, "error": "weights must not be negative"}
    total = sum(targets.values())
    if abs(total - 100) > 0.5:
        return {"valid": False,
                "error": f"target weights sum to {round(total, 2)}, not 100"}
    before = _waci(holdings)
    after = _waci([{**h, "weight_pct": targets.get(h["company"], 0.0)}
                   for h in holdings])
    changes = [{"company": c, "from_pct": current[c]["weight_pct"],
                "to_pct": targets.get(c, 0.0),
                "shift_pct_points": round(targets.get(c, 0.0)
                                          - current[c]["weight_pct"], 2)}
               for c in current if targets.get(c, 0.0) != current[c]["weight_pct"]]
    out = {"valid": True, "year": year, "weight_changes": changes,
           "waci_before": before["waci"], "waci_after": after["waci"]}
    if before["waci"] and after["waci"] is not None:
        out["change_pct"] = round(100 * (after["waci"] - before["waci"])
                                  / before["waci"], 1)
    return out


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
