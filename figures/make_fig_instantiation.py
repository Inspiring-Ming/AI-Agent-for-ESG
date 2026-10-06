#!/usr/bin/env python3
"""Figure 3: instantiation of the reference architecture in the ESG case.

Designed for a full-width (figure*) placement in a two-column IEEE paper. The
canvas is kept close to the printed width so text remains legible after
scaling, and each box carries only its responsibility, the case component that
realizes it, and at most a few short facts.

  * solid boxes: instantiated responsibilities; dashed boxes: not instantiated
  * solid arrows: interaction types realized in the recorded execution;
    dashed arrows: types defined by the architecture but not exercised
  * the results line is read from output/*.json, so the figure cannot drift
    from the recorded experiment

Writes case-instantiation.{pdf,svg,png} to --out (default: figures/).
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                         # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACE = os.path.join(HERE, "output", "runtime_trace.json")
GOALS = os.path.join(HERE, "output", "goal_variation.json")

C = {  # fill, edge
    "L0": ("#DCEBFA", "#2F6DB5"), "L1": ("#E3F4E3", "#3C9A4A"),
    "L2": ("#FCF2DC", "#C99A2E"), "L3": ("#FBE5E5", "#C94A4A"),
    "L4": ("#F1E8F8", "#8A55B5"), "L5": ("#E3EEFB", "#3B78C2"),
    "L6": ("#E5F4E6", "#3E9A52"), "L7": ("#F2F2F2", "#8C8C8C"),
    "L8": ("#E3EEFB", "#3B78C2"), "L9": ("#F2F2F2", "#8C8C8C"),
}
INK, MUTED, GROUP = "#141414", "#454545", "#A0A0A0"
SOLID, DASH = "#141414", "#808080"
DASHSTYLE = (0, (4, 2.5))

FW, FH = 10.5, 5.15

# font sizes (pt); the figure is scaled by about 7.16 / FW when printed
F_BADGE, F_NAME, F_COMP, F_BUL, F_ARROW, F_GROUP, F_NOTE = (
    10.5, 9.4, 8.6, 8.2, 9.6, 9.8, 8.6)


def group(ax, x0, y0, x1, y1, title):
    ax.add_patch(FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.08",
        facecolor="white", edgecolor=GROUP, linewidth=0.9, linestyle=DASHSTYLE,
        zorder=1))
    ax.text(x0 + 0.10, y1 - 0.15, title, ha="left", va="center",
            fontsize=F_GROUP, fontweight="bold", color=INK, zorder=2)


def resp(ax, x, y, w, h, rid, name, comp, bullets=(), dashed=False,
         fname=F_NAME):
    fill, edge = C[rid]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06",
        facecolor=fill, edgecolor=edge, linewidth=1.4,
        linestyle=DASHSTYLE if dashed else "-", zorder=3))
    cx, top = x + w / 2, y + h
    ax.text(cx, top - 0.15, rid, ha="center", va="center", fontsize=F_BADGE,
            fontweight="bold", color=INK, zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor=edge, linewidth=0.9))
    yy = top - 0.36
    for line in name.split("\n"):
        ax.text(cx, yy, line, ha="center", va="top", fontsize=fname,
                fontweight="bold", color=INK, zorder=5)
        yy -= 0.17
    yy -= 0.03
    ax.text(cx, yy, comp, ha="center", va="top", fontsize=F_COMP,
            color=MUTED, style="italic", zorder=5)
    yy -= 0.19
    for b in bullets:
        ax.text(cx, yy, b, ha="center", va="top", fontsize=F_BUL,
                color=INK, zorder=5)
        yy -= 0.155


def link(ax, p0, p1, dashed=False, both=True):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle="<|-|>" if both else "-|>", mutation_scale=11,
        color=DASH if dashed else SOLID, linewidth=1.3,
        linestyle=DASHSTYLE if dashed else "-", shrinkA=1, shrinkB=1,
        zorder=6))


def label(ax, x, y, text, dashed=False, ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=F_ARROW,
            fontweight="bold", color=DASH if dashed else INK, zorder=7)


def person(ax, x, y):
    ax.add_patch(Circle((x, y + 0.30), 0.11, facecolor="white",
                        edgecolor=INK, linewidth=1.3, zorder=4))
    ax.add_patch(FancyBboxPatch((x - 0.17, y - 0.04), 0.34, 0.19,
                                boxstyle="round,pad=0,rounding_size=0.09",
                                facecolor="white", edgecolor=INK,
                                linewidth=1.3, zorder=4))
    ax.text(x, y - 0.20, "Analyst", ha="center", va="center",
            fontsize=F_NAME, fontweight="bold", color=INK)


def draw(out_dir):
    with open(TRACE, encoding="utf-8") as fh:
        tr = json.load(fh)
    with open(GOALS, encoding="utf-8") as fh:
        gv = json.load(fh)["summary"]
    occ = tr["interaction_occurrences"]
    realized = tr["interaction_types_observed"]
    ntypes = tr["interaction_types_defined"]

    fig = plt.figure(figsize=(FW, FH))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FW)
    ax.set_ylim(0, FH)
    ax.axis("off")

    # ---- L0 -------------------------------------------------------------
    fill, edge = C["L0"]
    ax.add_patch(FancyBboxPatch(
        (0.10, 4.62), FW - 0.20, 0.45, boxstyle="round,pad=0,rounding_size=0.06",
        facecolor=fill, edgecolor=edge, linewidth=1.4, zorder=3))
    ax.text(0.30, 4.845, "L0", ha="left", va="center", fontsize=F_BADGE,
            fontweight="bold", color=INK, zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor=edge, linewidth=0.9))
    ax.text(0.68, 4.845, "Business & Solution Design", ha="left",
            va="center", fontsize=F_NAME, fontweight="bold", color=INK,
            zorder=5)
    ax.text(2.95, 4.845,
            "case requirements and governance: ESG metric definitions, "
            "reporting requirements, control policies (design time)",
            ha="left", va="center", fontsize=F_COMP, style="italic",
            color=MUTED, zorder=5)

    # ---- groups ---------------------------------------------------------
    group(ax, 0.10, 0.95, 3.30, 4.45, "Client and Access")
    group(ax, 3.42, 0.95, 7.98, 4.45,
          "Agentic Coordination and Enterprise Services")
    group(ax, 8.10, 0.95, FW - 0.10, 4.45, "Platform and Evaluation")

    # ---- client and access ---------------------------------------------
    person(ax, 0.42, 2.95)
    link(ax, (0.60, 3.05), (0.72, 3.05), both=False)
    resp(ax, 0.72, 2.10, 1.10, 1.80, "L1", "Client &\nExperience",
         "Analyst interface", ["Submit request", "Present result"])
    resp(ax, 2.12, 2.10, 1.12, 1.80, "L2", "Access, Identity\n& Safety Control",
         "Access gate", ["Authentication", "Validation, rate", "limit"],
         fname=8.3)
    link(ax, (1.82, 3.05), (2.12, 3.05))
    label(ax, 1.97, 3.25, "T1")

    # ---- coordination and enterprise services --------------------------
    resp(ax, 3.52, 1.95, 1.70, 2.20, "L3", "Agent & Workflow\nOrchestration",
         "Goal-directed agent",
         ["Plans the next action", "from observations:", "discover, select,",
          "ground, compute,", "explain, terminate"])
    link(ax, (3.24, 3.05), (3.52, 3.05))
    label(ax, 3.38, 3.25, "T2")

    resp(ax, 5.62, 3.38, 2.24, 0.82, "L4", "Model Access & Inference",
         "Explanation provider (replaceable)")
    resp(ax, 5.62, 2.43, 2.24, 0.82, "L5", "Enterprise Context & Knowledge",
         "ESG knowledge graph (CQ1–CQ7)", fname=8.4)
    resp(ax, 5.62, 1.48, 2.24, 0.82, "L6", "Tool & Action Runtime",
         "Metric-computation services")

    link(ax, (5.22, 3.70), (5.62, 3.80))
    label(ax, 5.42, 3.94, "T3")
    link(ax, (5.22, 2.84), (5.62, 2.84))
    label(ax, 5.42, 3.00, "T4")
    link(ax, (5.22, 2.10), (5.62, 1.89))
    label(ax, 5.42, 1.82, "T5")

    resp(ax, 3.52, 1.05, 1.70, 0.72, "L7", "Async & Event Infrastructure",
         "not instantiated", dashed=True, fname=7.6)
    link(ax, (4.37, 1.95), (4.37, 1.77), dashed=True, both=False)
    label(ax, 4.53, 1.86, "T6", dashed=True, ha="left")

    # ---- platform and evaluation ----------------------------------------
    resp(ax, 8.22, 2.85, FW - 8.44, 1.30, "L9",
         "Evaluation, Observability\n& Improvement", "not instantiated",
         dashed=True, fname=8.9)
    resp(ax, 8.22, 1.10, FW - 8.44, 1.55, "L8", "Platform & Delivery\n"
         "Infrastructure", "Deployed service platform",
         ["hosting the ESG services"], fname=9.0)
    link(ax, (7.86, 3.79), (8.22, 3.55), dashed=True, both=False)
    label(ax, 8.04, 3.40, "T7", dashed=True)

    # ---- legend and recorded results -----------------------------------
    ax.add_patch(FancyArrowPatch((0.15, 0.62), (0.62, 0.62),
                                 arrowstyle="<|-|>", mutation_scale=10,
                                 color=SOLID, linewidth=1.3))
    ax.text(0.72, 0.62, "interaction type realized in the recorded execution",
            ha="left", va="center", fontsize=F_NOTE, color=INK)
    ax.add_patch(FancyArrowPatch((4.85, 0.62), (5.32, 0.62),
                                 arrowstyle="<|-|>", mutation_scale=10,
                                 color=DASH, linewidth=1.3,
                                 linestyle=DASHSTYLE))
    ax.text(5.42, 0.62, "defined but not exercised;  dashed box: not "
            "instantiated in this case", ha="left", va="center",
            fontsize=F_NOTE, color=DASH)
    ax.text(0.15, 0.27,
            f"Recorded execution: {occ} interaction occurrences realizing "
            f"{len(realized)} of {ntypes} types ({realized[0]}–"
            f"{realized[-1]}).   Across {gv['goals']} goals: "
            f"{gv['distinct_action_sequences']} distinct action sequences, "
            f"occurrence counts "
            f"{', '.join(str(c) for c in gv['distinct_occurrence_counts'])}.",
            ha="left", va="center", fontsize=F_NOTE, color=INK)

    os.makedirs(out_dir, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(os.path.join(out_dir, f"case-instantiation.{ext}"),
                    format=ext, dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.03, facecolor="white")
    plt.close(fig)
    print(f"wrote case-instantiation.{{pdf,svg,png}} -> {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "figures"))
    draw(ap.parse_args().out)
