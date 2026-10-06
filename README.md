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
- *Propose a reweighting that cuts it by at least 30%.*

A language model (Claude) decides each step. The agent looks up in an existing
enterprise **ESG knowledge graph** which metric measures carbon intensity and
how it is calculated, has the existing **ESG computation service** compute it
for each holding, and has a **portfolio service** compute the portfolio's
weighted average carbon intensity (WACI, the TCFD-recommended metric).
Holdings without data are reported with the reason, not estimated. A proposed
reweighting is a consequential action: it stops at an **approval gate** until a
portfolio manager, not the requester, approves it. No trades are placed.

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
open http://localhost:8090      # ask the agent, watch each step, approve proposals
./evaluate.sh                   # reproduce the recorded results (REPEATS=3 default)
```

## Architecture as deployed

| Responsibility | Realized by | Origin |
|---|---|---|
| L1 Client & Experience | FastAPI service + portfolio analyst page (`service/api.py`, `ui/`) | this package |
| L2 Access, Identity & Safety Control | signed session token, role-based entitlements (analyst, portfolio manager), request validation, rate limit, egress check (`l2_protect.py`) | this package |
| L3 Agent & Workflow Orchestration | Claude tool-use loop with execution constraints (`l3_coordinate.py`) | this package |
| L4 Model Access & Inference | Claude model access, output-contract validation, server-side fallback (`l4_infer.py`) | this package |
| L5 Enterprise Context & Knowledge | ESG knowledge graph (competency questions CQ1–CQ5), exposed by an MCP server (`mcp_servers/knowledge_server.py`) | **existing system**; MCP server in this package |
| L6 Tool & Action Runtime | metric computation, exposed by an MCP server (`mcp_servers/compute_server.py`) | **existing system**; MCP server in this package |
| L6 Tool & Action Runtime | portfolio service (WACI, rebalance evaluation) as an MCP server (`mcp_servers/portfolio_server.py`); entitlement checks and approval gate (`l6_act.py`) | this package |
| L8 Platform & Delivery Infrastructure | Docker Compose deployment | this package |

L0, L7 and L9 are not instantiated as runtime components.

```
Portfolio manager ─T1─▶ FastAPI (L1) ─▶ access gate (L2) ─T2─▶ agent loop (L3)
                                                         │ each decision ─T3─▶ Claude (L4)
                         MCP: knowledge graph      (L5) ◀─T4─┤
                         MCP: computation          (L6) ◀─T5─┤
                         MCP: portfolio service    (L6) ◀─T5─┤
                         approval gate             (L6) ◀─T5─┘  (rebalancing only)
```

| Compose service | Port | Role |
|---|---|---|
| `esg` | 8080 | existing ESG Metric System (knowledge graph + computation API) |
| `mcp-knowledge` | 8101 | MCP server for L5 |
| `mcp-compute` | 8102 | MCP server for the L6 computation service |
| `mcp-portfolio` | 8103 | MCP server for the L6 portfolio service |
| `agent` | 8090 | L1–L4 and the L6 action runtime |

### Execution constraints owned by L3

- the model may act only on the request's holdings and years;
- holdings and intensities passed to the portfolio service are assembled by L3
  from L6 results, never supplied by the model;
- **number check**: every number in the answer must occur in the request or in
  an L5/L6 result;
- a bound on model calls (12).

### Roles (L2) and authorization (L6)

| Role | Entitlements |
|---|---|
| analyst | compute metrics, analyze portfolios, propose rebalancing |
| portfolio manager | compute metrics, analyze portfolios, approve rebalancing |

L6 refuses an approval from a principal without the approval entitlement and
from the principal who requested the proposal (four-eyes rule).

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
| `run_case.py` | the worked example, recorded as interaction occurrences |
| `run_goals.py` | goal-conditioned variation over six portfolio questions; `--repeats` for consistency |
| `test_invariants.py` | boundary invariants I1–I4, each probed with a violating operation |
| `independent_mapping.py` | mapping of an independently published architecture (`--verify` re-fetches the source) |
| `figures/make_fig_sequence.py` | the recorded-execution figure, generated from `output/` |

`run_case.py` and `run_goals.py` send requests through `agentic/system.py`, the
same request path the service uses; `test_invariants.py` assembles the same
components with call counters around L5 and L6. Scenarios are defined in
`agentic/scenarios.py`. All results are written to `output/`.

## Recorded results

**Worked example** (4 holdings, TSMC without revenue data, 2023): WACI 163.59
t CO2e per USD million over the 80% of the portfolio with data; Micron
contributes 84%; TSMC reported as excluded with the reason. 27 interaction
occurrences realizing T1–T5; 5 model calls; answer passed the number check.

**Goal variation** (6 questions × 3 executions):

| Goal | Question | Occ. | L6 calls | Outcome |
|---|---|---|---|---|
| G1 | intensity and drivers, 4 holdings | 27 | 5 | answered |
| G2 | change since 2022 | 39 | 10 | answered |
| G3 | as G1, one holding without data | 27 | 5 | answered; gap reported |
| G4 | intensity and drivers, 7 holdings | 33/35 | 8 | answered |
| G5 | reweighting to cut intensity by 30% | 31 | 6 | proposal pending approval |
| G6 | share prices and trades | 5 | 0 | declined |

Five distinct action sequences; each question followed the same sequence in
all three executions, except two G4 executions in which the number check
flagged a figure the model had derived and the answer was revised once. All 18
final answers passed the number check.

**Boundary invariants** — 8 probes, all four invariants preserved, including
the approval gate (refused for the analyst and for the requester, accepted for
the portfolio manager).

**Independent mapping** — 10 elements of Microsoft's Multi-Agent Reference
Architecture; none required a responsibility outside L0–L9.

## Scope and limitations

- One domain (semiconductor portfolios), limited data coverage, a single
  coordinating agent, synchronous execution.
- Analysis and proposals only; no trading system is connected.
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
mcp_servers/          MCP servers: knowledge graph, computation, portfolio
service/              FastAPI service (L1)
ui/                   portfolio analyst page
output/               recorded results (JSON)
figures/              recorded-execution figure and its generator
```
