#!/usr/bin/env python3
"""Normalized capability analysis for the enterprise agentic AI reference architecture.

Reads the evidence base (sources.csv, capabilities.csv) and produces:
  - summary statistics reported in Section III-A / VI
  - the evidence-to-responsibility traceability table (LaTeX)
  - a per-responsibility source-coverage table (LaTeX)

Every number printed here is derived from the CSV evidence base, so the paper
never states a count that is not reproducible from the data.
"""

import csv
import os
from collections import Counter, OrderedDict, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")

RESP_NAME = OrderedDict([
    ("L0", ("Business \\& Solution Design", "Decide")),
    ("L1", ("Client \\& Experience", "Interact")),
    ("L2", ("Access, Identity \\& Safety Control", "Protect")),
    ("L3", ("Agent \\& Workflow Orchestration", "Coordinate")),
    ("L4", ("Model Access \\& Inference", "Infer")),
    ("L5", ("Enterprise Context \\& Knowledge", "Ground")),
    ("L6", ("Tool \\& Action Runtime", "Act")),
    ("L7", ("Async \\& Event Infrastructure", "Decouple")),
    ("L8", ("Platform \\& Delivery Infrastructure", "Operate")),
    ("L9", ("Evaluation, Observability \\& Improvement", "Improve")),
])

# Responsibilities instantiated by the ESG case scenario.
CASE_INSTANTIATED = {"L1", "L2", "L3", "L4", "L5", "L6", "L8"}


def read(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # normalize: missing/short trailing fields read back as None
    return [{k: (v if v is not None else "") for k, v in r.items()} for r in rows]


def main():
    sources = read("sources.csv")
    caps = read("capabilities.csv")

    retained = [s for s in sources if s["retained"].strip().lower() == "yes"]
    by_cat = Counter(s["category"] for s in retained)

    # Normalized capabilities: unique normalized_id
    norm = OrderedDict()
    for c in caps:
        nid = c["normalized_id"]
        if nid not in norm:
            norm[nid] = {
                "name": c["normalized_capability"],
                "resp": c["responsibility"],
                "applicability": c["applicability"],
                "raw": [],
                "sources": set(),
                "mechs": set(),
            }
        norm[nid]["raw"].append(c["raw_id"])
        norm[nid]["sources"].add(c["source_id"])
        if c["mechanism_examples"].strip():
            for m in c["mechanism_examples"].split("/"):
                norm[nid]["mechs"].add(m.strip())

    per_resp = defaultdict(list)
    for nid, n in norm.items():
        per_resp[n["resp"]].append((nid, n))

    general = [n for n in norm.values() if n["applicability"] == "general"]
    conditional = [n for n in norm.values() if n["applicability"] != "general"]

    # ---- console summary -------------------------------------------------
    print("=" * 66)
    print("EVIDENCE BASE")
    print("=" * 66)
    print(f"Retained sources          : {len(retained)}")
    for cat, n in sorted(by_cat.items()):
        print(f"  - {cat:<22}: {n}")
    print(f"Raw capabilities extracted: {len(caps)}")
    print(f"Normalized capabilities   : {len(norm)}")
    print(f"  - generally applicable  : {len(general)}")
    print(f"  - condition-dependent   : {len(conditional)}")
    ratio = len(caps) / len(norm)
    print(f"Consolidation ratio       : {len(caps)}/{len(norm)} = {ratio:.2f} raw per normalized")

    multi = [n for n in norm.values() if len(n["sources"]) > 1]
    print(f"Capabilities corroborated by >1 source: {len(multi)} "
          f"({100.0*len(multi)/len(norm):.0f}%)")

    print()
    print("=" * 66)
    print("PER-RESPONSIBILITY")
    print("=" * 66)
    print(f"{'ID':<4}{'Responsibility':<38}{'NC':>3}{'Raw':>5}{'Src':>5}{'Cond':>6}")
    for rid in RESP_NAME:
        items = per_resp.get(rid, [])
        raws = sum(len(n["raw"]) for _, n in items)
        srcs = set()
        for _, n in items:
            srcs |= n["sources"]
        cond = sum(1 for _, n in items if n["applicability"] != "general")
        print(f"{rid:<4}{RESP_NAME[rid][0].replace(chr(92)+'&','&'):<38}"
              f"{len(items):>3}{raws:>5}{len(srcs):>5}{cond:>6}")

    unassigned = [nid for nid, n in norm.items() if n["resp"] not in RESP_NAME]
    print(f"\nNormalized capabilities not assigned to L0-L9: {len(unassigned)}")

    # every retained source must contribute at least one capability
    contributing = {c["source_id"] for c in caps}
    missing = [s["source_id"] for s in retained if s["source_id"] not in contributing]
    print(f"Retained sources contributing no capability : {len(missing)} {missing if missing else ''}")

    # case coverage
    case_nc = sum(len(per_resp.get(r, [])) for r in CASE_INSTANTIATED)
    print(f"\nResponsibilities instantiated by the ESG case: "
          f"{len(CASE_INSTANTIATED)}/10 ({sorted(CASE_INSTANTIATED)})")
    print(f"Normalized capabilities under those responsibilities: {case_nc}")

    os.makedirs(OUT, exist_ok=True)

    # ---- Table: evidence -> responsibility -> case ------------------------
    case_real = {
        "L0": "Design-time concern; not in runtime trace",
        "L1": "Analyst interface",
        "L2": "Outside selected runtime scope",
        "L3": "Agent runtime / orchestrator",
        "L4": "Model access for interpretation and explanation",
        "L5": "ESG knowledge graph and structured data",
        "L6": "Metric-computation services",
        "L7": "Not required by selected scenario",
        "L8": "Case deployment infrastructure",
        "L9": "Not exercised in selected runtime trace",
    }

    lines = []
    for rid in RESP_NAME:
        items = per_resp.get(rid, [])
        srcs = set()
        for _, n in items:
            srcs |= n["sources"]
        cond = sum(1 for _, n in items if n["applicability"] != "general")
        examples = "; ".join(n["name"] for _, n in items[:3])
        lines.append(
            f"{rid} -- {RESP_NAME[rid][1]} & {len(items)} & {len(srcs)} & {cond} & "
            f"{examples} & {case_real[rid]} \\\\"
        )

    tbl = r"""\begin{table*}[t]
\centering
\caption{Traceability from the normalized capability set to responsibilities and case-system realization.
NC = normalized capabilities assigned to the responsibility; Src = distinct evidence sources contributing
to them; Cond = condition-dependent capabilities among them.}
\label{tab:evaluation-traceability}
\small
\begin{tabular}{p{0.115\textwidth} c c c p{0.315\textwidth} p{0.235\textwidth}}
\hline
\textbf{Responsibility} & \textbf{NC} & \textbf{Src} & \textbf{Cond} &
\textbf{Representative normalized capabilities} & \textbf{Case realization} \\
\hline
""" + "\n".join(lines) + r"""
\hline
\end{tabular}
\end{table*}
"""
    with open(os.path.join(OUT, "table_traceability.tex"), "w", encoding="utf-8") as fh:
        fh.write(tbl)

    # ---- Appendix-style full capability listing ---------------------------
    rows = []
    for rid in RESP_NAME:
        for nid, n in per_resp.get(rid, []):
            src = ", ".join(sorted(n["sources"]))
            app = "general" if n["applicability"] == "general" else \
                  n["applicability"].split(":", 1)[1]
            rows.append(f"{nid} & {n['name']} & {rid} & {app} & {src} \\\\")
    full = r"""\begin{table}[t]
\centering
\caption{Normalized capability set with evidence provenance.}
\label{tab:capability-set}
\scriptsize
\begin{tabular}{p{0.05\textwidth} p{0.36\textwidth} p{0.04\textwidth} p{0.13\textwidth} p{0.20\textwidth}}
\hline
\textbf{ID} & \textbf{Normalized capability} & \textbf{R} & \textbf{Applicability} & \textbf{Sources} \\
\hline
""" + "\n".join(rows) + r"""
\hline
\end{tabular}
\end{table}
"""
    with open(os.path.join(OUT, "table_capability_set.tex"), "w", encoding="utf-8") as fh:
        fh.write(full)

    # ---- machine-readable summary ----------------------------------------
    with open(os.path.join(OUT, "summary.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["responsibility", "verb", "normalized_capabilities",
                    "raw_capabilities", "distinct_sources", "conditional"])
        for rid in RESP_NAME:
            items = per_resp.get(rid, [])
            srcs = set()
            for _, n in items:
                srcs |= n["sources"]
            w.writerow([rid, RESP_NAME[rid][1], len(items),
                        sum(len(n["raw"]) for _, n in items), len(srcs),
                        sum(1 for _, n in items if n["applicability"] != "general")])

    print(f"\nWrote -> {OUT}/table_traceability.tex")
    print(f"Wrote -> {OUT}/table_capability_set.tex")
    print(f"Wrote -> {OUT}/summary.csv")


if __name__ == "__main__":
    main()
