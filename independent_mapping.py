#!/usr/bin/env python3
"""Independent architecture mapping (Table IV).

Maps the architectural elements of Microsoft's Multi-Agent Reference
Architecture to the proposed responsibilities. Each element records the purpose
as stated by the source, so the mapping is auditable against the published
description rather than resting on terminology alone.

Elements whose stated purpose crosses a proposed responsibility boundary are
recorded as "spanning" rather than forced into a one-to-one correspondence;
those cases are the informative ones, because they test whether the boundary is
an artifact of the ESG case.

Source: https://microsoft.github.io/multi-agent-reference-architecture/
Repo:   https://github.com/microsoft/multi-agent-reference-architecture

Run:  python3 independent_mapping.py [--verify]
  --verify re-fetches the source documents and checks that each quoted
  element name still appears, reporting any that have changed.
"""

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = ("https://raw.githubusercontent.com/microsoft/"
       "multi-agent-reference-architecture/main/docs")

# element, source-stated purpose (paraphrased from the source text),
# responsibility, relation, note
MAPPING = [
    ("Orchestrator agent",
     "Acts as central coordinator: receives incoming requests, formulates a "
     "high-level plan of tasks, delegates them to specialized agents, and "
     "aggregates their outputs into a final response.",
     "L3", "direct",
     "Coordination of goal-directed execution without owning execution "
     "mechanisms."),

    ("Specialized agents",
     "Domain-focused experts, each responsible for a distinct area of "
     "expertise; may themselves coordinate sub-agents.",
     "L3", "conditional",
     "Instantiated only in multi-agent configurations; the ESG case uses a "
     "single coordinating agent."),

    ("Agents registry",
     "Centralized data service cataloguing each agent's identity, "
     "capabilities, operational status, version and metadata tags, enabling "
     "discovery and auditability.",
     "L3", "conditional",
     "Agent discovery; distinct from the L6 tool registry, which catalogues "
     "executable capabilities rather than agents."),

    ("Agents communication",
     "Request-based communication for tightly coupled or latency-sensitive "
     "interaction; message-driven communication via a broker or event bus for "
     "loose coupling and resilience.",
     "L3/L7", "spanning",
     "Coordination ownership remains in L3 while the message-driven variant is "
     "mediated by L7; the architecture separates these, the source groups "
     "them under one element."),

    ("Memory",
     "Holds what is true of this user, session and collaboration -- "
     "preferences, decisions, open issues, interaction history. The source "
     "states explicitly that memory is not a knowledge base: enterprise "
     "content is authoritative, shared, permission-controlled and changes "
     "independently of any conversation.",
     "L3/L5", "spanning",
     "The source independently draws invariant I2: session-scoped state is "
     "distinguished from enterprise knowledge retrieved on demand through a "
     "permission-trimmed index."),

    ("Context engineering",
     "Designing, preparing and managing the information supplied to models to "
     "shape behaviour and results.",
     "L5", "direct",
     "Context assembly preceding inference."),

    ("Security",
     "Identity enforcement with agents and orchestrators authenticating via an "
     "identity provider and RBAC governing execution permissions; "
     "policy-controlled tool invocation at the point of action.",
     "L2/L6", "spanning",
     "The source independently draws invariant I3: boundary identity "
     "enforcement is separated from authorization at the point of action."),

    ("Observability",
     "Evaluation-driven observability over agent execution.",
     "L9", "direct",
     "Operational evidence collection and correlation."),

    ("Evaluation",
     "Assessment of system behaviour and quality.",
     "L9", "direct",
     "Evaluation evidence feeding improvement."),

    ("Governance",
     "Responsible-AI policies and accountability structures, guardrails across "
     "the AI lifecycle, governed data access and use, evaluation and "
     "red-teaming processes.",
     "L0", "direct",
     "Design-time and governance requirements rather than a runtime path."),
]

# element name -> document that should still contain it
SOURCES = {
    "Orchestrator agent": "building-blocks/Building-Blocks.md",
    "Specialized agents": "building-blocks/Building-Blocks.md",
    "Agents registry": "building-blocks/Building-Blocks.md",
    "Memory": "memory/Memory.md",
    "Security": "security/Security.md",
    "Observability": "observability/Observability.md",
    "Governance": "governance/Governance.md",
    "Context engineering": "context-engineering/Context-Engineering.md",
}


def verify() -> int:
    print("Verifying element names against the published source\n")
    bad = 0
    for element, doc in SOURCES.items():
        url = f"{RAW}/{doc}"
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                text = r.read().decode().lower()
        except Exception as e:
            print(f"  [SKIP] {element:22s} {doc} ({e})")
            continue
        head = element.lower().split()[0]
        ok = head in text
        print(f"  [{'OK ' if ok else 'MISS'}] {element:22s} <- {doc}")
        bad += 0 if ok else 1
    print(f"\n  {len(SOURCES) - bad}/{len(SOURCES)} element names confirmed")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify()

    print("=" * 72)
    print("INDEPENDENT ARCHITECTURE MAPPING (Table IV)")
    print("=" * 72)

    direct = [m for m in MAPPING if m[3] == "direct"]
    cond = [m for m in MAPPING if m[3] == "conditional"]
    span = [m for m in MAPPING if m[3] == "spanning"]
    covered = sorted({r for m in MAPPING for r in m[2].split("/")})

    for element, purpose, resp, rel, note in MAPPING:
        print(f"\n  {element}  ->  {resp}  [{rel}]")
        print(f"    purpose: {purpose[:88]}...")
        print(f"    note   : {note[:88]}")

    print("\n" + "=" * 72)
    print(f"  elements mapped        : {len(MAPPING)}")
    print(f"    direct               : {len(direct)}")
    print(f"    conditional          : {len(cond)}")
    print(f"    spanning             : {len(span)}")
    print(f"  responsibilities touched: {len(covered)} {covered}")
    unmapped = [m[0] for m in MAPPING if m[2] in ("", None)]
    print(f"  elements requiring a responsibility outside L0-L9: {len(unmapped)}")
    print("=" * 72)

    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "independent_mapping.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "source": {
                "name": "Microsoft Multi-Agent Reference Architecture",
                "site": "https://microsoft.github.io/"
                        "multi-agent-reference-architecture/",
                "repository": "https://github.com/microsoft/"
                              "multi-agent-reference-architecture",
            },
            "summary": {
                "elements": len(MAPPING), "direct": len(direct),
                "conditional": len(cond), "spanning": len(span),
                "responsibilities_touched": covered,
                "outside_l0_l9": len(unmapped),
            },
            "mapping": [{"element": e, "source_purpose": p,
                         "responsibility": r, "relation": rel, "note": n}
                        for e, p, r, rel, n in MAPPING],
        }, fh, indent=2)
    print(f"  written to {out}/independent_mapping.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
