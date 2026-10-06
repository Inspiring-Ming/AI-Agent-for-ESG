#!/usr/bin/env python3
"""Figure 3: instantiation of the reference architecture in the ESG case.

Layout follows the paper's figure: an L0 governance band, then three groups
(client and access; agentic coordination and enterprise services; platform and
evaluation), then a legend. Every element shown corresponds to what the
instantiation implements:

  * solid boxes are instantiated responsibilities; dashed boxes are not
    instantiated in this case (L7, L9);
  * solid arrows are interaction types realized in the recorded execution;
    dashed arrows are types defined by the architecture but not exercised;
  * responsibility names are the names used in the paper text, with the case
    component as a subtitle;
  * the footer is read from output/*.json, so the figure cannot drift from the
    recorded results.

Writes case-instantiation.{pdf,svg,png} to the directory given by --out
(default: figures/).
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACE = os.path.join(HERE, "output", "runtime_trace.json")
GOALS = os.path.join(HERE, "output", "goal_variation.json")

# fill, edge
C = {
    "L0": ("#DCEBFA", "#2F6DB5"), "L1": ("#E3F4E3", "#3C9A4A"),
    "L2": ("#FCF2DC", "#C99A2E"), "L3": ("#FBE5E5", "#C94A4A"),
    "L4": ("#F1E8F8", "#8A55B5"), "L5": ("#E3EEFB", "#3B78C2"),
    "L6": ("#E5F4E6", "#3E9A52"), "L7": ("#EFEFEF", "#8A8A8A"),
    "L8": ("#E3EEFB", "#3B78C2"), "L9": ("#F4F4F4", "#8A8A8A"),
}
INK, MUTED, GROUP = "#1A1A1A", "#4A4A4A", "#9A9A9A"
SOLID, DASH = "#1A1A1A", "#7A7A7A"

FW, FH = 14.0, 7.7


def group(ax, x0, y0, x1, y1, title):
    ax.add_patch(FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.10",
        facecolor="white", edgecolor=GROUP, linewidth=1.0,
        linestyle=(0, (4, 3)), zorder=1))
    ax.text(x0 + 0.15, y1 - 0.22, title, ha="left", va="center",
            fontsize=12, fontweight="bold", color=INK, zorder=2)


def resp(ax, x, y, w, h, rid, name, component, bullets, dashed=False,
         nfs=10.5, cfs=9.6):
    fill, edge = C[rid]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
        facecolor=fill, edgecolor=edge, linewidth=1.6,
        linestyle="-" if not dashed else (0, (4, 2.5)), zorder=3))
    cx = x + w / 2
    ax.text(cx, y + h - 0.20, rid, ha="center", va="center", fontsize=12,
            fontweight="bold", color=INK, zorder=5,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white",
                      edgecolor=edge, linewidth=1.0))
    ax.text(cx, y + h - 0.50, name, ha="center", va="center", fontsize=nfs,
            fontweight="bold", color=INK, zorder=5)
    ax.text(cx, y + h - 0.75, component, ha="center", va="center",
            fontsize=cfs, color=MUTED, style="italic", zorder=5)
    if bullets:
        ax.text(x + 0.14, y + h - 0.98, "\n".join(bullets), ha="left",
                va="top", fontsize=9.2, color=INK, linespacing=1.35, zorder=5)


def link(ax, p0, p1, label=None, lpos=None, dashed=False, both=True,
         ha="center"):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle="<|-|>" if both else "-|>", mutation_scale=13,
        color=DASH if dashed else SOLID, linewidth=1.5,
        linestyle=(0, (4, 2.5)) if dashed else "-", shrinkA=2, shrinkB=2,
        zorder=6))
    if label:
        ax.text(lpos[0], lpos[1], label, ha=ha, va="center", fontsize=11,
                fontweight="bold", color=DASH if dashed else INK, zorder=7)


def person(ax, x, y):
    ax.add_patch(Circle((x, y + 0.42), 0.17, facecolor="white",
                        edgecolor=INK, linewidth=1.6, zorder=4))
    ax.add_patch(FancyBboxPatch((x - 0.27, y - 0.10), 0.54, 0.30,
                                boxstyle="round,pad=0,rounding_size=0.14",
                                facecolor="white", edgecolor=INK,
                                linewidth=1.6, zorder=4))
    ax.text(x, y - 0.32, "Analyst", ha="center", va="center", fontsize=11,
            fontweight="bold", color=INK)


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

    # ---------------- L0 band ----------------------------------------------
    fill, edge = C["L0"]
    ax.add_patch(FancyBboxPatch(
        (0.15, 6.95), FW - 0.30, 0.62, boxstyle="round,pad=0,rounding_size=0.08",
        facecolor=fill, edgecolor=edge, linewidth=1.6, zorder=3))
    ax.text(FW / 2, 7.40, "L0   Business & Solution Design", ha="center",
            va="center", fontsize=12.5, fontweight="bold", color=INK, zorder=5)
    ax.text(FW / 2, 7.13,
            "Case requirements and governance: ESG metric definitions, "
            "reporting requirements, traceability and control policies "
            "(design time, not a runtime path)",
            ha="center", va="center", fontsize=10, color=MUTED, zorder=5)
    link(ax, (2.6, 6.93), (2.6, 6.50), dashed=True, both=False)
    ax.text(2.72, 6.71, "requirements and constraints", ha="left",
            va="center", fontsize=9.6, color=MUTED)

    # ---------------- groups -------------------------------------------------
    group(ax, 0.15, 1.95, 4.75, 6.48, "Client and Access")
    group(ax, 4.95, 1.95, 10.70, 6.48,
          "Agentic Coordination and Enterprise Services")
    group(ax, 10.90, 1.95, FW - 0.15, 6.48, "Platform and Evaluation")

    # ---------------- client and access -------------------------------------
    person(ax, 0.58, 4.15)
    ax.add_patch(FancyArrowPatch((0.86, 4.30), (0.98, 4.30), arrowstyle="-|>",
                                 mutation_scale=12, color=SOLID, linewidth=1.5,
                                 zorder=6))
    resp(ax, 0.98, 3.25, 1.62, 2.45, "L1", "Client & Experience",
         "Analyst interface",
         ["Submit request", "Present result", "and explanation"], nfs=9.8)
    resp(ax, 3.02, 3.25, 1.58, 2.45, "L2", "Access, Identity",
         "& Safety Control",
         ["Signed session", "Request validation", "Rate limit",
          "Identity and trace", "context"], nfs=9.8)
    link(ax, (2.60, 4.55), (3.02, 4.55), "T1", (2.81, 4.80))

    # ---------------- coordination and enterprise services ------------------
    resp(ax, 5.10, 3.12, 2.32, 2.93, "L3", "Agent & Workflow Orchestration",
         "Goal-directed agent runtime",
         ["Plans the next action", "from observations:",
          "discover, select, ground,", "compute, explain, terminate",
          "", "Holds execution-local", "state; bounds execution"],
         nfs=9.0, cfs=9.0)
    link(ax, (4.60, 4.55), (5.10, 4.55), "T2", (4.85, 4.80))

    resp(ax, 7.88, 5.00, 2.67, 1.10, "L4", "Model Access & Inference",
         "Explanation provider (replaceable)",
         ["Output contract validation"], cfs=9.2)
    resp(ax, 7.88, 3.62, 2.67, 1.15, "L5", "Enterprise Context & Knowledge",
         "ESG knowledge graph (CQ1\u2013CQ7)",
         ["Discovery, model, provenance"], nfs=9.8, cfs=9.2)
    resp(ax, 7.88, 2.12, 2.67, 1.20, "L6", "Tool & Action Runtime",
         "Metric-computation services",
         ["Authorize, compute, provenance"], cfs=9.2)

    link(ax, (7.42, 5.45), (7.88, 5.55), "T3", (7.65, 5.78))
    link(ax, (7.42, 4.20), (7.88, 4.20), "T4", (7.65, 4.43))
    link(ax, (7.42, 3.30), (7.88, 2.85), "T5", (7.56, 2.86))

    resp(ax, 5.10, 2.02, 2.32, 0.84, "L7", "Async & Event Infrastructure",
         "not instantiated in this case", [], dashed=True, nfs=8.8, cfs=8.6)
    link(ax, (6.26, 3.12), (6.26, 2.86), dashed=True, both=False)
    ax.text(6.40, 2.99, "T6", ha="left", va="center", fontsize=10.5,
            fontweight="bold", color=DASH)

    # ---------------- platform and evaluation --------------------------------
    resp(ax, 11.10, 4.35, FW - 11.35, 1.75, "L9", "Evaluation, Observability",
         "& Improvement",
         ["Not instantiated in this case:", "no runtime telemetry or",
          "evaluation loop"], dashed=True)
    resp(ax, 11.10, 2.15, FW - 11.35, 1.85, "L8", "Platform & Delivery",
         "Infrastructure",
         ["Deployed service platform", "hosting the ESG services"])
    link(ax, (10.55, 5.40), (11.10, 5.10), dashed=True, both=False)
    ax.text(10.84, 5.05, "T7", ha="center", va="center", fontsize=10.5,
            fontweight="bold", color=DASH)

    # ---------------- legend --------------------------------------------------
    ax.add_patch(FancyBboxPatch((0.15, 0.12), 8.30, 1.65,
                                boxstyle="round,pad=0,rounding_size=0.08",
                                facecolor="white", edgecolor=GROUP,
                                linewidth=1.0, zorder=1))
    ax.text(0.32, 1.55, "Interaction types", ha="left", va="center",
            fontsize=11, fontweight="bold", color=INK)
    names = [("T1", "Client Request / Response"),
             ("T2", "Identity & Authority Context"),
             ("T3", "Inference Request / Result"),
             ("T4", "Context Query / Grounded Context"),
             ("T5", "Action Intent / Observation"),
             ("T6", "Async Task / Observation Event"),
             ("T7", "Operational & Evaluation Evidence"),
             ("T8", "Improvement Feedback")]
    for i, (t, n) in enumerate(names):
        col, row = divmod(i, 4)
        x = 0.32 + col * 4.05
        y = 1.25 - row * 0.27
        done = t in realized
        ax.text(x, y, t, ha="left", va="center", fontsize=10,
                fontweight="bold", color=INK if done else DASH)
        ax.text(x + 0.42, y, n + ("" if done else "  (not exercised)"),
                ha="left", va="center", fontsize=9.6,
                color=INK if done else DASH)

    ax.add_patch(FancyBboxPatch((8.65, 0.12), FW - 8.80, 1.65,
                                boxstyle="round,pad=0,rounding_size=0.08",
                                facecolor="white", edgecolor=GROUP,
                                linewidth=1.0, zorder=1))
    ax.text(8.82, 1.55, "Notation and recorded results", ha="left",
            va="center", fontsize=11, fontweight="bold", color=INK)
    ax.add_patch(FancyArrowPatch((8.85, 1.25), (9.55, 1.25),
                                 arrowstyle="<|-|>", mutation_scale=11,
                                 color=SOLID, linewidth=1.5))
    ax.text(9.68, 1.25, "realized in the recorded execution", ha="left",
            va="center", fontsize=9.6, color=INK)
    ax.add_patch(FancyArrowPatch((8.85, 0.98), (9.55, 0.98),
                                 arrowstyle="<|-|>", mutation_scale=11,
                                 color=DASH, linewidth=1.5,
                                 linestyle=(0, (4, 2.5))))
    ax.text(9.68, 0.98, "defined, not exercised;  dashed box: not "
            "instantiated", ha="left", va="center", fontsize=9.6, color=DASH)
    ax.text(8.82, 0.66,
            f"{occ} interaction occurrences realizing {len(realized)} of "
            f"{ntypes} types ({realized[0]}–{realized[-1]}).",
            ha="left", va="center", fontsize=9.6, color=INK)
    ax.text(8.82, 0.38,
            f"{gv['goals']} goals: {gv['distinct_action_sequences']} action "
            f"sequences, occurrence counts "
            f"{', '.join(str(c) for c in gv['distinct_occurrence_counts'])}.",
            ha="left", va="center", fontsize=9.6, color=INK)

    os.makedirs(out_dir, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(os.path.join(out_dir, f"case-instantiation.{ext}"),
                    format=ext, dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.03, facecolor="white")
    plt.close(fig)
    print(f"wrote case-instantiation.{{pdf,svg,png}} -> {out_dir}")
    print(f"  from recorded results: {occ} occurrences, "
          f"{len(realized)}/{ntypes} types, goals {gv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "figures"))
    draw(ap.parse_args().out)
