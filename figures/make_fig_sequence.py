#!/usr/bin/env python3
"""Figure 3: recorded execution of the instantiated architecture.

A sequence diagram of the representative request, generated from
output/runtime_trace.json. Fig. 2 of the paper shows the architecture's
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
NEW_FILL, NEW_EDGE = "#FFFFFF", "#3B3B3B"      # introduced by instantiation
OLD_FILL, OLD_EDGE = "#E4EEF8", "#2F6DB5"      # existing ESG system
REQ, RET = "#1F4E9A", "#1E7A46"

# lifeline order chosen to keep the common exchanges short
LANES = [
    ("L1", "Client & Experience", "analyst interface", False),
    ("L2", "Access, Identity &\nSafety Control", "access gate", False),
    ("L3", "Agent & Workflow\nOrchestration", "goal-directed agent", False),
    ("L5", "Enterprise Context\n& Knowledge", "ESG knowledge graph", True),
    ("L6", "Tool & Action\nRuntime", "metric computation", True),
    ("L4", "Model Access\n& Inference", "explanation provider", False),
]

FW, FH = 10.5, 5.35
F_HEAD, F_SUB, F_MSG, F_NOTE = 9.4, 8.4, 8.4, 8.2


def _num(v):
    try:
        return f"{float(str(v).replace(',', '')):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def describe(it):
    """Human-readable message text from a recorded interaction."""
    p, purpose = it["payload"], it["purpose"]
    if purpose == "request admission":
        return f"metric request: {p.get('company')}, {p.get('year')}"
    if purpose.startswith("authorized request"):
        return "authorized request + identity and trace context"
    if purpose == "capability discovery":
        return f"which metrics in “{p.get('category')}”? (CQ3)"
    if purpose == "discovered metrics":
        return f"{p.get('count')} candidate metrics"
    if purpose == "context retrieval":
        return f"definition of {p.get('metric')}"
    if purpose == "grounded context":
        return (f"model {p.get('model')}, inputs, provenance "
                f"(CQ1–CQ{p.get('competency_questions')})")
    if purpose == "action intent":
        return "compute with the resolved model"
    if purpose == "observation":
        return f"value {_num(p.get('value'))} + inputs and provenance"
    if purpose == "inference request":
        return "explain the computed result"
    if purpose == "inference result":
        return "explanation (output contract satisfied)"
    if purpose == "result and explanation":
        return (f"result {_num(p.get('value'))} t CO\u2082e per USD million "
                "+ explanation")
    return purpose


def draw(out_dir):
    with open(TRACE, encoding="utf-8") as fh:
        tr = json.load(fh)
    msgs = tr["interactions"]

    fig = plt.figure(figsize=(FW, FH))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FW)
    ax.set_ylim(0, FH)
    ax.axis("off")

    x0, x1 = 0.85, FW - 0.85
    step = (x1 - x0) / (len(LANES) - 1)
    lane_x = {rid: x0 + i * step for i, (rid, *_rest) in enumerate(LANES)}

    head_top, head_h = FH - 0.08, 0.86
    top = head_top - head_h
    bottom = 0.78
    for rid, name, comp, existing in LANES:
        x = lane_x[rid]
        w = 1.52
        ax.add_patch(FancyBboxPatch(
            (x - w / 2, top), w, head_h,
            boxstyle="round,pad=0,rounding_size=0.06",
            facecolor=OLD_FILL if existing else NEW_FILL,
            edgecolor=OLD_EDGE if existing else NEW_EDGE, linewidth=1.3,
            zorder=3))
        ax.text(x, head_top - 0.14, rid, ha="center", va="center",
                fontsize=F_HEAD + 0.6, fontweight="bold", color=INK, zorder=4)
        ax.text(x, head_top - 0.29, name, ha="center", va="top",
                fontsize=F_SUB, fontweight="bold", color=INK, zorder=4,
                linespacing=1.15)
        ax.text(x, top + 0.10, comp, ha="center", va="bottom",
                fontsize=F_SUB - 0.4, color=MUTED, style="italic", zorder=4)
        ax.plot([x, x], [top, bottom], color="#9A9A9A", linewidth=1.0,
                linestyle=(0, (3, 2.5)), zorder=1)

    # messages
    y = top - 0.30
    gap = (top - 0.30 - (bottom + 0.15)) / (len(msgs) - 1)
    for it in msgs:
        xs, xt = lane_x[it["source"]], lane_x[it["target"]]
        ret = it["purpose"] in ("discovered metrics", "grounded context",
                                "observation", "inference result",
                                "result and explanation")
        col = RET if ret else REQ
        ax.add_patch(FancyArrowPatch(
            (xs, y), (xt, y), arrowstyle="-|>", mutation_scale=10,
            color=col, linewidth=1.25,
            linestyle=(0, (4, 2)) if ret else "-", shrinkA=0, shrinkB=0,
            zorder=5))
        left = min(xs, xt)
        ax.text(left + 0.08, y + 0.075,
                f"{it['seq']}  {it['ttype']}   {describe(it)}",
                ha="left", va="bottom", fontsize=F_MSG, color=INK, zorder=6,
                bbox=dict(boxstyle="square,pad=0.05", facecolor="white",
                          edgecolor="none", alpha=0.85))
        y -= gap

    # legend
    ly = 0.42
    ax.add_patch(FancyArrowPatch((0.20, ly), (0.62, ly), arrowstyle="-|>",
                                 mutation_scale=9, color=REQ, linewidth=1.25))
    ax.text(0.70, ly, "request / intent", ha="left", va="center",
            fontsize=F_NOTE, color=INK)
    ax.add_patch(FancyArrowPatch((2.05, ly), (2.47, ly), arrowstyle="-|>",
                                 mutation_scale=9, color=RET, linewidth=1.25,
                                 linestyle=(0, (4, 2))))
    ax.text(2.55, ly, "result / observation", ha="left", va="center",
            fontsize=F_NOTE, color=INK)
    ax.add_patch(FancyBboxPatch((4.20, ly - 0.09), 0.30, 0.18,
                                boxstyle="round,pad=0,rounding_size=0.03",
                                facecolor=NEW_FILL, edgecolor=NEW_EDGE,
                                linewidth=1.1))
    ax.text(4.58, ly, "introduced by the instantiation", ha="left",
            va="center", fontsize=F_NOTE, color=INK)
    ax.add_patch(FancyBboxPatch((6.70, ly - 0.09), 0.30, 0.18,
                                boxstyle="round,pad=0,rounding_size=0.03",
                                facecolor=OLD_FILL, edgecolor=OLD_EDGE,
                                linewidth=1.1))
    ax.text(7.08, ly, "provided by the existing ESG system", ha="left",
            va="center", fontsize=F_NOTE, color=INK)
    ax.text(0.20, 0.12,
            f"{tr['interaction_occurrences']} recorded interaction "
            f"occurrences realizing {len(tr['interaction_types_observed'])} "
            f"of {tr['interaction_types_defined']} interaction types. "
            "L2 applies its egress check to the result before L1 presents it.",
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
    draw(ap.parse_args().out)
