#!/usr/bin/env python3
"""Recorded-execution figure (fig:case-runtime) of the instantiated architecture.

A sequence diagram of the worked example, generated from
output/runtime_trace.json. Consecutive per-holding computations are drawn as
one request row and one result row. The reference-architecture figure shows the architecture's
structure; this figure shows behaviour: which responsibility exchanged what
with which, in the order it happened, against the real enterprise system.

Each lifeline is headed by its responsibility and the case component that
realizes it, and is marked as introduced by the instantiation or provided by
the existing ESG system. Each message carries its interaction type and the
content actually exchanged, including the computed value.

Writes case-runtime.{pdf,svg,png} to --out (default: figures/).
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACE = os.path.join(HERE, "output", "runtime_trace.json")

INK, MUTED = "#141414", "#4A4A4A"
REQ, RET = "#213A8F", "#1E7A46"
TAG = "#213A8F"
# (edge, fill) per responsibility, matching the reference-architecture figure
RCOL = {"L1": ("#2E9B57", "#ECF8F0"), "L2": ("#E0A12A", "#FFF6E3"),
        "L3": ("#D64545", "#FDECEC"), "L4": ("#9A4FC4", "#F6EDFB"),
        "L5": ("#2F7FD6", "#EAF3FD"), "L6": ("#2E9B57", "#ECF8F0")}

# lifeline order chosen to keep the common exchanges short
LANES = [
    ("L1", "Client & Experience", "portfolio analyst page", False),
    ("L2", "Access, Identity &\nSafety Control", "access gate", False),
    ("L3", "Agent & Workflow\nOrchestration", "agent runtime", False),
    ("L5", "Enterprise Context\n& Knowledge", "ESG knowledge graph*", True),
    ("L6", "Tool & Action\nRuntime", "computation* · portfolio", "mixed"),
    ("L4", "Model Access\n& Inference", "hosted language model", False),
]

FW, FH = 10.5, 7.6
F_HEAD, F_SUB, F_MSG, F_NOTE = 11.0, 10.0, 10.2, 9.6


def _num(v):
    try:
        return f"{float(str(v).replace(',', '')):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def describe(it):
    """Human-readable message text from a recorded interaction."""
    p, purpose = it["payload"], it["purpose"]
    tool = p.get("tool")
    if purpose == "request admission":
        return f"portfolio question ({p.get('holdings')} holdings, {p.get('year')})"
    if purpose.startswith("authorized request"):
        role = (p.get("role") or "").replace("_", " ")
        return f"admitted request with identity ({role}) and trace context"
    if purpose == "capability discovery":
        return f"metrics of category “{p.get('category')}”"
    if purpose == "discovered metrics":
        return f"{p.get('count')} metrics"
    if purpose == "context retrieval":
        return f"calculation model of {p.get('metric')}"
    if purpose == "grounded context":
        return f"{p.get('model')} and its required inputs"
    if purpose == "action intent" and tool == "portfolio_intensity":
        return f"portfolio carbon intensity (WACI), {p.get('year')}"
    if purpose == "action intent" and tool in ("check_trade", "submit_trade"):
        return ("pre-trade compliance check" if tool == "check_trade"
                else "submit trade instruction")
    if purpose == "observation" and tool == "portfolio_intensity":
        return f"WACI {_num(p.get('waci'))}, holding contributions, data coverage"
    if purpose == "observation" and tool == "check_trade":
        return "within mandate" if p.get("compliant") else "breaches mandate"
    if purpose == "observation" and tool == "submit_trade":
        return f"{p.get('status')}"
    if purpose == "inference request":
        return "next-step request (question and observations)"
    if purpose == "inference result":
        return f"model decision; output contract {'satisfied' if p.get('contract') == 'success' else p.get('contract')}"
    if purpose == "answer":
        return (f"answer after L2 egress check: WACI {_num(p.get('waci'))},"
                " drivers, excluded holding")
    return purpose


def _short(company):
    return company.split(" Technologies")[0].split(" Semiconductor")[0] \
        .split(" Technology")[0].replace("STMicroelectronics NV", "STMicro") \
        .replace("Taiwan", "TSMC").split(" Inc")[0]


def rows(msgs):
    """Group consecutive per-holding computations into two rows."""
    out, i = [], 0
    while i < len(msgs):
        it = msgs[i]
        if it["payload"].get("tool") == "compute_metric" \
                and it["purpose"] == "action intent":
            j = i
            while j < len(msgs) and msgs[j]["payload"].get("tool") == "compute_metric":
                j += 1
            grp = msgs[i:j]
            intents = [m for m in grp if m["purpose"] == "action intent"]
            obs = [m for m in grp if m["purpose"] == "observation"]
            seqs = f"{grp[0]['seq']}–{grp[-1]['seq']}"
            out.append({**intents[0], "num": seqs, "text": "compute "
                        f"{intents[0]['payload'].get('metric')} for "
                        f"{len(intents)} holdings, {intents[0]['payload'].get('year')}",
                        "ret": False})
            vals = " · ".join(
                f"{_short(m['payload']['company'])} {_num(m['payload']['value'])}"
                if m["payload"].get("value") else
                f"{_short(m['payload']['company'])}: no revenue data"
                for m in obs)
            out.append({**obs[0], "num": seqs, "text": vals, "ret": True})
            i = j
            continue
        ret = it["purpose"] in ("discovered metrics", "grounded context",
                                "observation", "inference result", "answer")
        out.append({**it, "num": str(it["seq"]), "text": describe(it),
                    "ret": ret})
        i += 1
    return out


TCOL = {t: TAG for t in ("T1", "T2", "T3", "T4", "T5")}


def _right(fig, ax, artist):
    """Right edge of a drawn text artist, in data coordinates."""
    bb = artist.get_window_extent(renderer=fig.canvas.get_renderer())
    return ax.transData.inverted().transform((bb.x1, bb.y0))[0]


def draw(out_dir):
    with open(TRACE, encoding="utf-8") as fh:
        tr = json.load(fh)
    msgs = tr["interactions"]

    fig = plt.figure(figsize=(FW, FH))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FW)
    ax.set_ylim(0, FH)
    ax.axis("off")

    x0, x1 = 0.92, FW - 0.92
    step = (x1 - x0) / (len(LANES) - 1)
    lane_x = {rid: x0 + i * step for i, (rid, *_rest) in enumerate(LANES)}

    head_top, head_h = FH - 0.08, 0.86
    top = head_top - head_h
    bottom = 0.78
    for rid, name, comp, existing in LANES:
        x = lane_x[rid]
        w = 1.64
        ax.add_patch(FancyBboxPatch(
            (x - w / 2, top), w, head_h,
            boxstyle="round,pad=0,rounding_size=0.04",
            facecolor=RCOL[rid][1], edgecolor=RCOL[rid][0], linewidth=1.4,
            zorder=3))
        ax.text(x, head_top - 0.14, rid, ha="center", va="center",
                fontsize=F_HEAD + 0.6, fontweight="bold", color=RCOL[rid][0],
                zorder=4)
        ax.text(x, head_top - 0.29, name, ha="center", va="top",
                fontsize=F_SUB, fontweight="bold", color=INK, zorder=4,
                linespacing=1.15)
        ax.text(x, top + 0.10, comp, ha="center", va="bottom",
                fontsize=F_SUB - 0.4, color=MUTED, style="italic", zorder=4)
        ax.plot([x, x], [top, bottom], color="#9A9A9A", linewidth=1.0,
                linestyle=(0, (3, 2.5)), zorder=1)

    # messages
    msgs = rows(msgs)
    y = top - 0.30
    gap = (top - 0.30 - (bottom + 0.15)) / (len(msgs) - 1)
    for it in msgs:
        xs, xt = lane_x[it["source"]], lane_x[it["target"]]
        col = RET if it["ret"] else REQ
        ax.add_patch(FancyArrowPatch(
            (xs, y), (xt, y), arrowstyle="-|>", mutation_scale=10,
            color=col, linewidth=1.25,
            linestyle=(0, (4, 2)) if it["ret"] else "-", shrinkA=0, shrinkB=0,
            zorder=5))
        left = min(xs, xt)
        # label: occurrence number, interaction-type tag, content
        x = left + 0.08
        t = ax.text(x, y + 0.075, it["num"], ha="left", va="bottom",
                    fontsize=F_MSG - 0.6, color=MUTED, zorder=6)
        x = _right(fig, ax, t) + 0.10
        t = ax.text(x, y + 0.075, it["ttype"], ha="left", va="bottom",
                    fontsize=F_MSG - 0.8, fontweight="bold",
                    color="white", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.08",
                              facecolor=TCOL.get(it["ttype"], INK),
                              edgecolor="none"))
        x = _right(fig, ax, t) + 0.12
        ax.text(x, y + 0.075, it["text"],
                ha="left", va="bottom", fontsize=F_MSG, color=INK, zorder=6,
                bbox=dict(boxstyle="square,pad=0.05", facecolor="white",
                          edgecolor="none", alpha=0.85))
        y -= gap

    # legend: items placed one after another
    ly, x = 0.42, 0.20

    def item(x, draw_mark, text):
        draw_mark(x)
        t = ax.text(x + 0.52, ly, text, ha="left", va="center",
                    fontsize=F_NOTE, color=INK)
        return _right(fig, ax, t) + 0.45

    x = item(x, lambda x: ax.add_patch(FancyArrowPatch(
        (x, ly), (x + 0.42, ly), arrowstyle="-|>", mutation_scale=9,
        color=REQ, linewidth=1.25)), "request / intent")
    x = item(x, lambda x: ax.add_patch(FancyArrowPatch(
        (x, ly), (x + 0.42, ly), arrowstyle="-|>", mutation_scale=9,
        color=RET, linewidth=1.25, linestyle=(0, (4, 2)))),
        "result / observation")
    ax.text(x, ly, "* existing ESG system; all other components were "
            "added for the agent", ha="left", va="center",
            fontsize=F_NOTE, color=INK)

    ax.text(0.20, 0.12,
            "L5 and L6 are reached through MCP; L6 comprises the existing "
            "computation service and the added portfolio service.",
            ha="left", va="center", fontsize=F_NOTE, color=MUTED)

    os.makedirs(out_dir, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(os.path.join(out_dir, f"case-runtime.{ext}"), format=ext,
                    dpi=300 if ext == "png" else None, bbox_inches="tight",
                    pad_inches=0.03, facecolor="white")
    plt.close(fig)
    print(f"wrote case-runtime.{{pdf,svg,png}} -> {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "figures"))
    ap.add_argument("--trace", default=TRACE)
    a = ap.parse_args()
    TRACE = a.trace
    draw(a.out)
