#!/usr/bin/env python3
"""Independent architecture mapping (Section VI).

Maps the components of a published reference architecture that is not among
the 11 synthesis sources -- Lu et al., "Towards Responsible Generative AI: A
Reference Architecture for Designing Foundation Model Based Agents" (ICSA-C
2024) -- to the proposed responsibilities. Each element records the purpose as
stated by the source, so the mapping is auditable against the published
description rather than resting on terminology alone.

The elements are the component groups of the source's reference-architecture
figure (Fig. 2); its responsible-AI plugins are grouped by concern. Elements
whose stated purpose crosses a proposed responsibility boundary are recorded as
"spanning" rather than forced into a one-to-one correspondence; those cases are
the informative ones.

Source: https://doi.org/10.1109/ICSA-C63560.2024.00028
Text:   https://arxiv.org/html/2311.13148v3

Run:  python experiments/independent_mapping.py [--verify]
  --verify re-fetches the source text and checks that each element name
  still appears.
"""

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
SOURCE_URL = "https://arxiv.org/html/2311.13148v3"

# element, source-stated purpose (paraphrased from the source text),
# responsibility, relation, note
MAPPING = [
    ("Context engineering",
     "Dialogue interface, multimodal context injection, and passive or "
     "proactive goal creators that collect and structure the context needed "
     "to understand the user's goals.",
     "L1/L3", "spanning",
     "Interaction surfaces belong to L1; interpreting goals belongs to L3."),

    ("Prompt/response engineering",
     "Prompt/response generator using templates and personas to produce "
     "prompts and responses aligned with the goal.",
     "L3", "direct",
     "Prompt and runtime configuration within coordination."),

    ("Memory",
     "Short-term memory (configuration, recent events, working context) "
     "within the model's context window; long-term memory (event history, "
     "knowledge and past experiences) outside it, moved in through memory "
     "retrieval.",
     "L3/L5", "spanning",
     "In-context working state is execution-bound (L3); long-term knowledge "
     "and experience is reusable context (L5), consistent with I2."),

    ("Planning",
     "Single- or multi-path plan generation with one-shot or incremental model "
     "querying, refined through self-, cross-, or human reflection.",
     "L3", "direct",
     "Coordination; human reflection corresponds to conditional human "
     "interaction."),

    ("Cooperation with other agents",
     "Voting-, role-, and debate-based cooperation among agents.",
     "L3", "conditional",
     "Multi-agent collaboration; the case uses one agent."),

    ("Execution engine",
     "Task executor performing the planned tasks, using tools or other agents, "
     "and a task monitor managing queued tasks.",
     "L3/L6", "spanning",
     "The source places deciding and performing a task in one component; the "
     "proposed structure separates coordination (L3) from capability "
     "execution (L6), consistent with I1."),

    ("Tool/agent selector and registry",
     "Search, rank, or generate tools and agents, drawing on a tool/agent "
     "registry or marketplace.",
     "L3/L6", "spanning",
     "Agent discovery is an L3 collaboration capability; the tool catalogue "
     "belongs to L6."),

    ("Guardrails",
     "Input, output, RAG, execution, and intermediate guardrails controlling "
     "the inputs and outputs of models, retrieval, and tools.",
     "L2/L5/L6", "spanning",
     "Boundary input/output controls (L2), retrieval constraints (L5), and "
     "permitted actions (L6): resource-specific enforcement, consistent "
     "with I3."),

    ("Recording and risk assessment",
     "Black box recorder of runtime data across components, continuous risk "
     "assessor of AI risk metrics, and explainer of outputs and rationale.",
     "L9", "direct",
     "Accountability and operational evidence."),

    ("AIBOM and co-versioning registries",
     "Supply-chain records of tools, agents, and models, used to refuse "
     "components of questionable provenance; co-versioning of model "
     "variants.",
     "L0/L4", "spanning",
     "Provenance policy is an L0 governance decision; co-versioned model "
     "variants are managed by L4."),

    ("AI models",
     "External, fine-tuned, or sovereign foundation models, optionally used "
     "through N-version programming.",
     "L4", "direct",
     "Model access, selection, and provider policy."),
]

# element names expected in the source text
SOURCES = {
    "Context engineering": "context engineering",
    "Prompt/response engineering": "prompt/response",
    "Memory": "long-term memory",
    "Planning": "plan generation",
    "Cooperation with other agents": "cooperation",
    "Execution engine": "task executor",
    "Tool/agent selector and registry": "tool/agent selector",
    "Guardrails": "guardrails",
    "Recording and risk assessment": "black box recorder",
    "AIBOM and co-versioning registries": "aibom",
    "AI models": "sovereign",
}


def verify() -> int:
    print("Verifying element names against the published source\n")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as r:
            text = r.read().decode(errors="ignore").lower()
    except Exception as e:
        print(f"  [SKIP] could not fetch {SOURCE_URL} ({e})")
        return 1
    bad = 0
    for element, term in SOURCES.items():
        ok = term in text
        print(f"  [{'OK ' if ok else 'MISS'}] {element:34s} '{term}'")
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
    print("INDEPENDENT ARCHITECTURE MAPPING")
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
                "name": "Lu et al., A Reference Architecture for Designing "
                        "Foundation Model Based Agents (ICSA-C 2024)",
                "doi": "10.1109/ICSA-C63560.2024.00028",
                "text": SOURCE_URL,
                "synthesis_source": False,
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
