# AI Agent for ESG — Reference Architecture Instantiation

Replication package for the architecture instantiation and evaluation reported
in *A Reference Architecture for Enterprise Agentic AI Integration*
(responsibilities L0–L9, interaction types T1–T8, boundary invariants I1–I4).

An LLM agent (Claude) is instantiated over an existing enterprise ESG metric
system. The model decides each next step; the existing system's knowledge graph
and computation service are reached through **MCP**; every exchange between
responsibilities is recorded as an *interaction occurrence* (one directed
exchange; a request and its return are counted separately).

- Existing enterprise system: <https://github.com/Inspiring-Ming/ESG-Metric-System>

## Quick start

```bash
git clone https://github.com/Inspiring-Ming/ESG-Metric-System ../esg-system
export ESG_REPO=../esg-system   # path to the existing ESG system
cp .env.example .env            # add your ANTHROPIC_API_KEY
docker compose up -d --build    # ESG system, two MCP servers, agent service
open http://localhost:8090      # watch the agent work, step by step
./evaluate.sh                   # reproduce the recorded results (REPEATS=3 default)
```

Compose builds the existing ESG Metric System from `ESG_REPO` as the `esg`
service; the agent never imports its code.

## Architecture as deployed

| Responsibility | Realized by | Origin |
|---|---|---|
| L1 Client & Experience | FastAPI service + analyst page (`service/api.py`, `ui/`) | this package |
| L2 Access, Identity & Safety Control | signed session token, request validation, rate limit, egress check (`l2_protect.py`) | this package |
| L3 Agent & Workflow Orchestration | Claude tool-use loop; the model chooses each next tool (`l3_coordinate.py`) | this package |
| L4 Model Access & Inference | Claude model access, output-contract validation, server-side fallback (`l4_infer.py`) | this package |
| L5 Enterprise Context & Knowledge | ESG knowledge graph (competency questions CQ1–CQ5), exposed by an MCP server (`mcp_servers/knowledge_server.py`, `l5_ground.py`) | **existing system**; MCP server in this package |
| L6 Tool & Action Runtime | entitlement check (`l6_act.py`) + metric-computation service, exposed by an MCP server (`mcp_servers/compute_server.py`) | **existing system** (computation); entitlement check and MCP server in this package |
| L8 Platform & Delivery Infrastructure | Docker Compose deployment | this package |

L0, L7 and L9 are not instantiated as runtime components.

```
Analyst ─T1─▶ FastAPI (L1) ─▶ access gate (L2) ─T2─▶ agent loop (L3)
                                                   │ each decision ─T3─▶ Claude (L4)
                         MCP: knowledge graph (L5) ◀─T4─┤
                         MCP: computation     (L6) ◀─T5─┘
```

| Compose service | Port | Role |
|---|---|---|
| `esg` | 8080 | existing ESG Metric System (knowledge graph + computation API) |
| `mcp-knowledge` | 8101 | MCP server for L5 |
| `mcp-compute` | 8102 | MCP server for L6 |
| `agent` | 8090 | L1–L4 (FastAPI + agent) |

### Guardrails owned by L3

- the model never supplies company, year or category; it only chooses which
  metric tool to call;
- the reported value is always the one returned by L6, never model text;
- **number check**: every number in the model's answer must occur in what L5
  or L6 returned;
- a bound on model calls (8).

## Configuration

| Variable | Values |
|---|---|
| `ANTHROPIC_API_KEY` | required (in `.env`) |
| `ANTHROPIC_MODEL` | default `claude-opus-5-5` |
| `SESSION_SECRET` | signing key for L2 session tokens |

## Experiments

| Script | What it measures |
|---|---|
| `run_case.py` | the representative request, recorded as interaction occurrences |
| `run_goals.py` | goal-conditioned variation; `--repeats` for consistency of the model-driven planner |
| `test_invariants.py` | boundary invariants I1–I4, each probed with a violating operation |
| `independent_mapping.py` | mapping of an independently published architecture (`--verify` re-fetches the source) |
| `figures/make_fig_sequence.py` | the recorded-execution figure, generated from `output/` |

`run_case.py` and `run_goals.py` send requests through `agentic/system.py`,
the same request path the service uses; `test_invariants.py` assembles the
same components with call counters around L5 and L6. All write to `output/`.

## Recorded results

**Representative request** (GHG emissions intensity, STMicroelectronics, 2023):
45.47 t CO2e per USD million, from Scope 1 = 514,000 t, Scope 2 = 272,000 t,
revenue = USD 17,286 million. 17 interaction occurrences realizing T1–T5;
4 model calls; every number in the answer traced to L5/L6 results.

**Goal variation** (6 goals × 3 executions):

| Goal | Occ. | Types | Outcome |
|---|---|---|---|
| G1 named calculated metric, explanation | 17 | T1–T5 | computed |
| G2 same metric, result only | 17 | T1–T5 | computed |
| G3 named measured metric, explanation | 17 | T1–T5 | computed |
| G4 no metric named; needs a calculation model | 17 | T1–T5 | 1 of 4 selected, computed |
| G5 two metrics | 21 | T1–T5 | both computed |
| G6 metric not in the category | 9 | T1–T4 | refused; L6 not engaged |

Each goal took the same path in all three executions; all 18 answers passed
the number check.

**Boundary invariants** — 7 probes, all four invariants preserved.

**Independent mapping** — 10 elements of Microsoft's Multi-Agent Reference
Architecture; none required a responsibility outside L0–L9.

## Scope and limitations

- One industry case; a single coordinating agent; synchronous execution.
  Multi-agent collaboration, asynchronous mediation, persistent memory, human
  approval and execution isolation are variation points, not instantiated.
- The model-driven planner is not deterministic; consistency is measured over
  repeated executions rather than assumed.
- The independent mapping is a descriptive analysis of a published source.

## Layout

```
agentic/
  responsibilities/   one module per instantiated responsibility
  system.py           the request path shared by the service and the scripts
  adapters/           MCP clients; HTTP adapter used by the MCP servers
  trace/              interaction recorder and the T1–T8 interaction types
mcp_servers/          MCP servers exposing L5 and L6 of the existing system
service/              FastAPI service (L1)
ui/                   analyst page
output/               recorded results (JSON)
figures/              recorded-execution figure and its generator
```
