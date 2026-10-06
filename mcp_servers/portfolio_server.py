"""MCP server for portfolio analytics and pre-trade compliance -- an L6
capability added by this package.

Deterministic calculations over per-holding carbon intensities that the
existing ESG computation service has produced. The agent never performs this
arithmetic itself: it requests it as an action and receives the result.

Weighted average carbon intensity (WACI), the portfolio carbon metric
recommended by the TCFD, is the weight-averaged intensity of the holdings:

    WACI = sum_i (w_i / W) * intensity_i      over holdings with an intensity,

where W is the total weight of those holdings. Holdings without an intensity
are excluded and reported, and the covered weight is returned.

Each fund has an ESG mandate held here, not supplied by the caller. A trade is
checked by applying it to the current weights and testing the resulting
portfolio against the mandate.

Tools
  portfolio_intensity(holdings, year, previous)   WACI, contributions, coverage
  check_trade(fund, holdings, trades, year)        post-trade WACI and breaches

Run:  python -m mcp_servers.portfolio_server   (env: MCP_PORT)
"""

import os
from typing import Dict, List, Optional

from mcp.server.mcpserver import MCPServer

PORT = int(os.environ.get("MCP_PORT", "8103"))

# Illustrative fund mandate (limits in percent of portfolio weight, and in
# t CO2e per USD million revenue).
MANDATES = {
    "ESG Semiconductor Fund": {
        "max_waci": 150.0,
        "high_intensity_threshold": 300.0,
        "max_high_intensity_weight_pct": 25.0,
        "max_single_weight_pct": 35.0,
    },
}

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
                                     / (w_cov * waci), 1) if waci else 0.0}
         for h in covered), key=lambda c: -c["contribution"])
    return {"waci": round(waci, 2), "covered_weight_pct": round(w_cov, 1),
            "contributions": contributions, "not_covered": missing}


def _breaches(holdings: List[Dict], waci: Optional[float], m: Dict) -> List[Dict]:
    out = []
    if waci is not None and waci > m["max_waci"]:
        out.append({"limit": "max_waci", "limit_value": m["max_waci"],
                    "actual": waci, "excess": round(waci - m["max_waci"], 2)})
    high = [h for h in holdings if h.get("intensity") is not None
            and h["intensity"] > m["high_intensity_threshold"]
            and h["weight_pct"] > 0]
    high_w = round(sum(h["weight_pct"] for h in high), 2)
    if high_w > m["max_high_intensity_weight_pct"]:
        out.append({"limit": "max_high_intensity_weight_pct",
                    "limit_value": m["max_high_intensity_weight_pct"],
                    "actual": high_w,
                    "excess": round(high_w - m["max_high_intensity_weight_pct"], 2),
                    "holdings": [h["company"] for h in high]})
    for h in holdings:
        if h["weight_pct"] > m["max_single_weight_pct"]:
            out.append({"limit": "max_single_weight_pct",
                        "limit_value": m["max_single_weight_pct"],
                        "actual": h["weight_pct"], "company": h["company"],
                        "excess": round(h["weight_pct"]
                                        - m["max_single_weight_pct"], 2)})
    return out


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
def check_trade(fund: str, holdings: List[Dict], trades: List[Dict],
                year: str) -> Dict:
    """Pre-trade compliance check of a trade against the fund's ESG mandate.

    trades: [{company, change_pct_points}] over current holdings; buys are
    positive, sells negative, and the changes must sum to zero (self-funded).
    """
    mandate = MANDATES.get(fund)
    if mandate is None:
        return {"valid": False, "error": f"no mandate for fund '{fund}'"}
    current = {h["company"]: h for h in holdings}
    changes: Dict[str, float] = {}
    for t in trades:
        changes[t["company"]] = changes.get(t["company"], 0.0) \
            + float(t["change_pct_points"])
    unknown = sorted(set(changes) - set(current))
    if unknown:
        return {"valid": False, "error": f"not current holdings: {unknown}"}
    if abs(sum(changes.values())) > 0.01:
        return {"valid": False, "error": "trade is not self-funded: changes "
                f"sum to {round(sum(changes.values()), 2)} percentage points"}
    after = [{**h, "weight_pct": round(h["weight_pct"]
                                       + changes.get(h["company"], 0.0), 4)}
             for h in holdings]
    if any(h["weight_pct"] < 0 for h in after):
        return {"valid": False, "error": "trade would leave a negative weight"}
    before_w, after_w = _waci(holdings), _waci(after)
    breaches = _breaches(after, after_w["waci"], mandate)
    out = {"valid": True, "fund": fund, "year": year, "mandate": mandate,
           "trades": [{"company": c, "change_pct_points": round(d, 2),
                       "from_pct": current[c]["weight_pct"],
                       "to_pct": round(current[c]["weight_pct"] + d, 2)}
                      for c, d in changes.items() if d],
           "waci_before": before_w["waci"], "waci_after": after_w["waci"],
           "compliant": not breaches, "breaches": breaches,
           "not_covered": after_w["not_covered"]}
    if before_w["waci"] and after_w["waci"] is not None:
        out["waci_change_pct"] = round(
            100 * (after_w["waci"] - before_w["waci"]) / before_w["waci"], 1)
    return out


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
