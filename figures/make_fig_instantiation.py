#!/usr/bin/env python3
"""Figure: instantiation of the reference architecture in the ESG case.

Draws the instantiated responsibilities and the typed interactions recorded
for the representative scenario. Interaction labels use the architecture's
interaction types (T1-T8), not step numbers, because the occurrence order is a
property of the execution rather than of the architecture.

Reads the recorded trace so the figure cannot drift from the experiment.
Vector output (PDF + SVG) for publication.
"""

import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACE = os.path.join(HERE, "output", "runtime_trace.json")
GOALS = os.path.join(HERE, "output", "goal_variation.json")
OUT = os.path.join(HERE, "figures")

C = {
    "L0": ("#EDF0F7", "#2F5597"), "L1": ("#E4F1E8", "#2E7D4F"),
    "L2": ("#E7EEF7", "#37699B"), "L3": ("#F0E9F5", "#6A4C93"),
    "L4": ("#FBE9E9", "#B4444B"), "L5": ("#FDF3E2", "#B07D0A"),
    "L6": ("#E6F2F3", "#2B7A82"), "L7": ("#EEF0F6", "#5566A6"),
    "L8": ("#EDF1F4", "#4F6D7A"), "L9": ("#F6E9F0", "#94436B"),
}
INK, MUTED = "#1A1A1A", "#5A5A5A"
REQ, RET, COND = "#2B5CA8", "#1F7A4D", "#8A93A6"

FW, FH = 7.16, 6.18


def box(ax, x, y, w, h, rid, verb, title, lines, dashed=False,
        tfs=8.6, lfs=6.9):
    fill, edge = C[rid]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.055",
        facecolor=fill, edgecolor=edge, linewidth=1.15,
        linestyle="-" if not dashed else (0, (3.5, 2.2)), zorder=3))
    ax.text(x + 0.10, y + h - 0.15, f"{rid}  {verb}", ha="left", va="center",
            fontsize=tfs, fontweight="bold", color=edge, zorder=5)
    ax.text(x + 0.10, y + h - 0.32, title, ha="left", va="center",
            fontsize=lfs + 0.5, color=INK, zorder=5)
    for i, ln in enumerate(lines):
        ax.text(x + 0.10, y + h - 0.50 - i * 0.145, "· " + ln,
                ha="left", va="center", fontsize=lfs, color=MUTED, zorder=5)


def arrow(ax, p0, p1, color, label, lx, ly, ha="center", dashed=False,
          rad=0.0, fs=6.6):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle="-|>", mutation_scale=8.5, color=color,
        linewidth=1.15, shrinkA=0, shrinkB=0, zorder=6,
        linestyle="-" if not dashed else (0, (3.5, 2.2)),
        connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text(lx, ly, label, ha=ha, va="center", fontsize=fs,
                color=color, zorder=7, fontweight="bold")


def draw():
    with open(TRACE, encoding="utf-8") as fh:
        tr = json.load(fh)
    occ = tr["interaction_occurrences"]
    nty = len(tr["interaction_types_observed"])
    tot = tr["interaction_types_defined"]

    fig = plt.figure(figsize=(FW, FH))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FW); ax.set_ylim(0, FH); ax.axis("off")

    L, R = 0.16, FW - 0.16

    # ---- L0 design-time band -----------------------------------------
    y0, h0 = FH - 0.70, 0.58
    box(ax, L, y0, R - L, h0, "L0", "Decide", "Business & Solution Design",
        ["Governing requirements, constraints and policy for the case "
         "(design time, not a runtime path)"], tfs=8.2)

    # ---- L1 / L2 entry row -------------------------------------------
    yb, hb = y0 - 1.06, 0.88
    w1 = 2.38
    box(ax, L, yb, w1, hb, "L1", "Interact", "Analyst interface",
        ["Submit metric request", "Present result and explanation"])
    box(ax, L + w1 + 0.78, yb, w1 + 0.30, hb, "L2", "Protect",
        "Access gate",
        ["Signed session, request validation", "Per-principal rate limit",
         "Establishes identity and trace context"])

    arrow(ax, (L + w1 + 0.04, yb + hb * 0.62),
          (L + w1 + 0.74, yb + hb * 0.62), REQ, "T1",
          L + w1 + 0.39, yb + hb * 0.62 + 0.13)
    arrow(ax, (L + w1 + 0.74, yb + hb * 0.26),
          (L + w1 + 0.04, yb + hb * 0.26), RET, "T1",
          L + w1 + 0.39, yb + hb * 0.26 - 0.13)

    # ---- L3 coordinator ----------------------------------------------
    yh, hh = yb - 1.10, 0.92
    box(ax, L, yh, R - L, hh, "L3", "Coordinate",
        "Goal-directed agent runtime",
        ["Receives a goal, not a procedure; plans the next action from "
         "accumulated observations",
         "Discovers candidates, selects, grounds, invokes computation, "
         "requests explanation, terminates",
         "Holds execution-local working context and bounds the execution"])

    x2 = L + w1 + 0.78 + (w1 + 0.30) / 2
    arrow(ax, (x2, yb - 0.02), (x2, yh + hh + 0.02), REQ, "T2",
          x2 + 0.13, (yb + yh + hh) / 2 + 0.02, ha="left")
    xb = L + w1 * 0.34
    arrow(ax, (xb, yh + hh + 0.02), (xb, yb - 0.02), RET, "T1",
          xb - 0.13, (yb + yh + hh) / 2 + 0.02, ha="right")

    # ---- L4 / L5 / L6 supporting row ---------------------------------
    yl, hl = yh - 1.32, 1.08
    gap = 0.20
    wl = (R - L - 2 * gap) / 3
    specs = [
        ("L4", "Infer", "Model access",
         ["Explanation provider", "Output contract validation"], "T3"),
        ("L5", "Ground", "ESG knowledge graph",
         ["Metric discovery (CQ3)", "Definition, model, provenance",
          "Queried through CQ1–CQ7"], "T4"),
        ("L6", "Act", "Metric-computation services",
         ["Resource-specific authorization", "Deterministic computation",
          "Result with provenance"], "T5"),
    ]
    centres = []
    for i, (rid, verb, title, lines, tt) in enumerate(specs):
        x = L + i * (wl + gap)
        box(ax, x, yl, wl, hl, rid, verb, title, lines)
        cx = x + wl / 2
        centres.append((cx, tt))
        arrow(ax, (cx - 0.17, yh - 0.02), (cx - 0.17, yl + hl + 0.02),
              REQ, None, 0, 0)
        arrow(ax, (cx + 0.17, yl + hl + 0.02), (cx + 0.17, yh - 0.02),
              RET, None, 0, 0)
        ax.text(cx, (yh + yl + hl) / 2, tt, ha="center", va="center",
                fontsize=7.0, fontweight="bold", color=INK, zorder=7,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                          edgecolor="none"))

    # identity propagation L2 -> L5/L6
    xp = R - 0.06
    arrow(ax, (xp, yb + 0.06), (xp, yl + hl + 0.06), "#9A6BB5", None, 0, 0,
          dashed=True)
    ax.text(xp - 0.08, yl + hl + 0.30,
            "T2: identity and authority context;\nL5/L6 retain "
            "resource-specific enforcement",
            ha="right", va="bottom", fontsize=6.3, color="#7A5490",
            linespacing=1.35, zorder=7)

    # ---- conditional / supporting row --------------------------------
    yc, hc = yl - 0.72, 0.56
    wc = (R - L - 2 * gap) / 3
    box(ax, L, yc, wc, hc, "L7", "Decouple", "Async & event infrastructure",
        ["Not required by the synchronous case"], dashed=True, tfs=7.8,
        lfs=6.4)
    box(ax, L + wc + gap, yc, wc, hc, "L8", "Operate",
        "Deployed service platform",
        ["Hosts the participating components"], tfs=7.8, lfs=6.4)
    box(ax, L + 2 * (wc + gap), yc, wc, hc, "L9", "Improve",
        "Evaluation & observability",
        ["Not exercised by the traced execution"], dashed=True, tfs=7.8,
        lfs=6.4)

    # ---- legend -------------------------------------------------------
    ly = yc - 0.30
    ax.add_patch(FancyArrowPatch((L, ly), (L + 0.30, ly), arrowstyle="-|>",
                                 mutation_scale=8, color=REQ, linewidth=1.15,
                                 shrinkA=0, shrinkB=0))
    ax.text(L + 0.36, ly, "request / intent", ha="left", va="center",
            fontsize=6.6, color=INK)
    ax.add_patch(FancyArrowPatch((L + 1.52, ly), (L + 1.82, ly),
                                 arrowstyle="-|>", mutation_scale=8,
                                 color=RET, linewidth=1.15, shrinkA=0,
                                 shrinkB=0))
    ax.text(L + 1.88, ly, "response / observation", ha="left", va="center",
            fontsize=6.6, color=INK)
    ax.add_patch(FancyArrowPatch((L + 3.46, ly), (L + 3.76, ly),
                                 arrowstyle="-|>", mutation_scale=8,
                                 color="#9A6BB5", linewidth=1.15,
                                 linestyle=(0, (3.5, 2.2)), shrinkA=0,
                                 shrinkB=0))
    ax.text(L + 3.82, ly, "context propagation", ha="left", va="center",
            fontsize=6.6, color=INK)
    ax.text(R, ly, f"dashed box: not instantiated in this case",
            ha="right", va="center", fontsize=6.6, color=MUTED,
            style="italic")

    ax.text(L, ly - 0.22,
            f"Recorded execution: {occ} interaction occurrences realizing "
            f"{nty} of the {tot} defined interaction types (T1–T5); "
            f"T6–T8 not exercised.",
            ha="left", va="center", fontsize=6.8, color=MUTED)

    with open(GOALS, encoding="utf-8") as fh:
        gv = json.load(fh)["summary"]
    ax.text(L, ly - 0.40,
            f"Across {gv['goals']} goals the same coordinator produced "
            f"{gv['distinct_action_sequences']} distinct action sequences and "
            "occurrence counts of "
            + ", ".join(str(c) for c in gv['distinct_occurrence_counts']) + ".",
            ha="left", va="center", fontsize=6.8, color=MUTED)
    ax.text(L, ly - 0.59,
            "Both realization mechanisms \u2014 the deployed service interface "
            "and the same services imported in process \u2014 produce "
            "identical results.",
            ha="left", va="center", fontsize=6.8, color=MUTED)

    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(os.path.join(OUT, f"case-instantiation.{ext}"),
                    format=ext, dpi=400 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.03, facecolor="white")
    plt.close(fig)
    print("wrote case-instantiation.{pdf,svg,png} ->", OUT)
    print(f"  from trace: {occ} occurrences, {nty}/{tot} types")


if __name__ == "__main__":
    draw()
