# ESG Portfolio Agent — Reference Architecture Instantiation

Replication package for the architecture instantiation and evaluation reported
in *A Reference Architecture for Enterprise Agentic AI Integration*
(responsibilities L0–L9, interaction types T1–T8, boundary invariants I1–I4).

## What the agent does

Portfolio managers and sustainability analysts at asset managers must report
the carbon footprint of their funds (TCFD, SFDR). The agent answers their
questions about a portfolio in plain language, for example:

- *What is the carbon intensity of my portfolio, and which holdings drive it?*
- *Has it improved since 2022?*
- *I want to buy 5 points more NXP, funded from Infineon. Does it comply with
  the fund's mandate? If so, submit it.*

A language model (Claude) decides each step. The agent looks up in an existing
enterprise **ESG knowledge graph** which metric measures carbon intensity and
how it is calculated, has the existing **ESG computation service** compute it
for each holding, and has a **portfolio service** compute the portfolio's
weighted average carbon intensity (WACI, the TCFD-recommended metric).
Holdings without data are reported with the reason, not estimated.

For a proposed trade, the agent runs a **pre-trade compliance check** against
the fund's ESG mandate, which is held by the compliance service, not supplied
in the request:

| Limit (illustrative) | Value |
|---|---|
| portfolio WACI | ≤ 150 t CO2e per USD million |
| weight in holdings with intensity > 300 | ≤ 25% |
| any single holding | ≤ 35% |

Submitting a trade is a consequential action. L6 re-runs the check itself: a
compliant trade is **cleared**; a breaching trade is **held** until a
compliance officer, who is not the submitter, approves an override. No order
management system is connected, so no order is ever placed.

The model never calculates a number itself. A **number check** verifies that
every number in its answer occurs in the request or in a result returned by the
knowledge graph or the services.

- Existing enterprise system: <https://github.com/Inspiring-Ming/ESG-Metric-System>

## Quick start

```bash
git clone https://github.com/Inspiring-Ming/ESG-Metric-System ../esg-system
export ESG_REPO=../esg-system   # path to the existing ESG system
cp .env.example .env            # add your ANTHROPIC_API_KEY
docker compose up -d --build    # ESG system, three MCP servers, agent service
open http://localhost:8090      # ask the agent, watch each step, approve overrides
./evaluate.sh                   # reproduce the recorded results (REPEATS=3 default)
```

## Architecture as deployed

| Responsibility | Realized by | Origin |
|---|---|---|
| L1 Client & Experience | FastAPI service + portfolio analyst page (`service/api.py`, `ui/`) | this package |
| L2 Access, Identity & Safety Control | signed session token, role-based entitlements (portfolio manager, compliance officer), request validation, rate limit, egress check (`l2_protect.py`) | this package |
| L3 Agent & Workflow Orchestration | Claude tool-use loop with execution constraints (`l3_coordinate.py`) | this package |
| L4 Model Access & Inference | Claude model access, output-contract validation, server-side fallback (`l4_infer.py`) | this package |
| L5 Enterprise Context & Knowledge | ESG knowledge graph (competency questions CQ1–CQ5), exposed by an MCP server (`mcp_servers/knowledge_server.py`) | **existing system**; MCP server in this package |
| L6 Tool & Action Runtime | metric computation, exposed by an MCP server (`mcp_servers/compute_server.py`) | **existing system**; MCP server in this package |
| L6 Tool & Action Runtime | portfolio and compliance service (WACI, pre-trade mandate check) as an MCP server (`mcp_servers/portfolio_server.py`); entitlement checks, trade submission and override gate (`l6_act.py`) | this package |
| L8 Platform & Delivery Infrastructure | Docker Compose deployment | this package |

L0, L7 and L9 are not instantiated as runtime components.

```
Portfolio manager ─T1─▶ FastAPI (L1) ─▶ access gate (L2) ─T2─▶ agent loop (L3)
                                                         │ each decision ─T3─▶ Claude (L4)
                         MCP: knowledge graph      (L5) ◀─T4─┤
                         MCP: computation          (L6) ◀─T5─┤
                         MCP: portfolio/compliance (L6) ◀─T5─┤
                         override gate             (L6) ◀─T5─┘  (breaching trades only)
```

| Compose service | Port | Role |
|---|---|---|
| `esg` | 8080 | existing ESG Metric System (knowledge graph + computation API) |
| `mcp-knowledge` | 8101 | MCP server for L5 |
| `mcp-compute` | 8102 | MCP server for the L6 computation service |
| `mcp-portfolio` | 8103 | MCP server for the L6 portfolio and compliance service |
| `agent` | 8090 | L1–L4 and the L6 action runtime |

### Execution constraints owned by L3

- the model may act only on the request's fund, holdings and years;
- holdings and intensities passed to the portfolio and compliance service are
  assembled by L3 from L6 results, never supplied by the model;
- **number check**: every number in the answer must occur in the request or in
  an L5/L6 result; a draft that fails is returned to the model once;
- a bound on model calls (12).

### Roles (L2) and authorization (L6)

| Role | Entitlements |
|---|---|
| portfolio manager | compute metrics, analyze portfolios, submit trades |
| compliance officer | analyze portfolios, approve overrides of breaching trades |

L6 refuses an override from a principal without the override entitlement and
from the principal who submitted the trade (four-eyes rule).

## Data coverage

The existing system holds ESG data for semiconductor companies and revenue for
North American-listed ones. Carbon intensity can be computed for seven
companies (STMicroelectronics, Infineon, NXP, Microchip, ON Semiconductor, UMC,
Micron) for 2021–2023; for others, such as TSMC, the system reports missing
revenue, which the agent passes on.

## Configuration

| Variable | Values |
|---|---|
| `ANTHROPIC_API_KEY` | required (in `.env`) |
| `ANTHROPIC_MODEL` | default `claude-opus-5-5` |
| `SESSION_SECRET` | signing key for L2 session tokens |
| `ESG_REPO` | path to the ESG Metric System checkout |

## Experiments

| Script | What it measures |
|---|---|
| `experiments/run_case.py` | the worked example, recorded as interaction occurrences |
| `experiments/run_goals.py` | goal-conditioned variation over seven portfolio and trade questions; `--repeats` for consistency |
| `experiments/test_invariants.py` | boundary invariants I1–I4, each probed with a violating operation |
| `experiments/independent_mapping.py` | mapping of an independently published architecture (`--verify` re-fetches the source) |
| `figures/make_fig_sequence.py` | the recorded-execution figure, generated from `output/` |

`experiments/run_case.py` and `experiments/run_goals.py` send requests through `agentic/system.py`, the
same request path the service uses; `experiments/test_invariants.py` assembles the same
components with call counters around L5 and L6. Scenarios are defined in
`agentic/scenarios.py`. All results are written to `output/`.

## Recorded results

**Worked example** (4 holdings, TSMC without revenue data, 2023): WACI 163.59
t CO2e per USD million over the 80% of the portfolio with data; Micron
contributes 84%; TSMC reported as excluded with the reason. 27 interaction
occurrences realizing T1–T5; 5 model calls; answer passed the number check.

**Goal variation** (7 questions × 3 executions):

| Goal | Question | Occ. | L6 calls | Outcome |
|---|---|---|---|---|
| G1 | intensity and drivers, 4 holdings | 27 | 5 | answered |
| G2 | change since 2022 | 39–41 | 10 | answered |
| G3 | as G1, one holding without data | 27 | 5 | answered; gap reported |
| G4 | intensity and drivers, 7 holdings | 35 | 8 | answered |
| G5 | trade within the mandate; submit | 31–33 | 6–7 | cleared (WACI 144.4 → 146.33) |
| G6 | trade breaching the mandate; override | 33 | 7 | held for override (WACI 164.94 > 150; 30% > 25% high-intensity) |
| G7 | share prices | 5 | 0 | declined |

Seven distinct action sequences. Within a question, executions differed only in
one G5 execution (the model also computed the current WACI first) and where the
number check flagged a figure the model had derived (one G2 and all three G4
drafts), which was revised once. All 21 final answers passed the number check.

**Boundary invariants** — 8 probes, all four invariants preserved, including
the override gate (refused for the portfolio manager and for the submitter,
accepted for the compliance officer).

**Independent mapping** — 10 elements of Microsoft's Multi-Agent Reference
Architecture; none required a responsibility outside L0–L9.

## Scope and limitations

- One domain (semiconductor portfolios), limited data coverage, a single
  coordinating agent, synchronous execution.
- The fund mandate is illustrative; analysis and pre-trade checks only, no
  order management system is connected.
- The model-driven planner is not deterministic; consistency is measured over
  repeated executions rather than assumed.
- The independent mapping is a descriptive analysis of a published source.

## Layout

```
agentic/
  responsibilities/   one module per instantiated responsibility
  system.py           the request paths shared by the service and the scripts
  scenarios.py        portfolios and questions used by the experiments
  adapters/           MCP clients; HTTP adapter used by the MCP servers
  trace/              interaction recorder and the T1–T8 interaction types
mcp_servers/          MCP servers: knowledge graph, computation, portfolio/compliance
experiments/          worked example, goal variation, invariant probes, mapping
service/              FastAPI service (L1)
ui/                   portfolio analyst page
output/               recorded results (JSON)
figures/              recorded-execution figure and its generator
```
