# AI Agent for ESG — Reference Architecture Instantiation

Replication package for the architecture instantiation and evaluation reported
in *A Reference Architecture for Enterprise Agentic AI Integration*.

A goal-directed agent is instantiated over an existing enterprise ESG metric
computation and reporting system. Each architectural responsibility is a
separate module, so the responsibility boundaries claimed by the architecture
are visible in the source layout and testable at runtime.

The underlying enterprise system is not reimplemented here. Enterprise
knowledge and executable services are reached through its published service
interface:

- Source: <https://github.com/Inspiring-Ming/ESG-Metric-System>
- Deployment: <https://esgalaxy.com.ngrok.dev>

## What is instantiated

| Responsibility | Module | Origin |
|---|---|---|
| L1 Interact  | `agentic/responsibilities/l1_interact.py`  | this package |
| L2 Protect   | `agentic/responsibilities/l2_protect.py`   | this package |
| L3 Coordinate| `agentic/responsibilities/l3_coordinate.py`| this package |
| L4 Infer     | `agentic/responsibilities/l4_infer.py`     | this package |
| L5 Ground    | `agentic/responsibilities/l5_ground.py`    | **existing system** (ESG knowledge graph, CQ1–CQ7) |
| L6 Act       | `agentic/responsibilities/l6_act.py`       | **existing system** (metric-computation services) |
| L8 Operate   | deployment of the existing system          | **existing system** |

L0, L7 and L9 are not instantiated as runtime components in the evaluated
scenario; `output/variability.json` records the condition under which each
would be required.

## The agent

`l3_coordinate.py` implements a plan → act → observe loop. It receives a *goal*,
not a procedure:

- **plan** — inspect the goal and accumulated observations, select the next
  action (`discover`, `select`, `ground`, `compute`, `explain`, `abort`,
  `finish`)
- **act** — engage the responsibility that owns that action
- **observe** — record the result into the working context, conditioning the
  next planning step

Nothing in the coordinator prescribes the order in which L4, L5 and L6 are
engaged. The agent discovers which metrics a category contains by querying the
knowledge graph (CQ3), selects among them, and determines whether a calculation
model is required.

## Running

```bash
python3 run_case.py        # one scenario, end to end, recording its trace
python3 run_goals.py       # five goals; shows how the action sequence varies
python3 test_invariants.py # probes the four boundary invariants
python3 independent_mapping.py          # mapping of an independent architecture
python3 independent_mapping.py --verify # re-fetch and check element names
python3 test_boundaries.py # regression checks
```

Add `--mechanism local --esg-root PATH` (or set `ESG_ROOT`) to import the ESG
services in process instead of calling the deployed API. Both mechanisms
produce the same results; only the realization mechanism differs.

**No API key is required.** L4 defaults to a deterministic explanation provider
so recorded traces are reproducible. Setting `ANTHROPIC_API_KEY` substitutes a
hosted model provider with no change to L3, L5 or L6; `ANTHROPIC_MODEL`
overrides the model id.

> The deployment is tunnelled and may be unavailable at times. If it is, use
> `--mechanism local` against a clone of the ESG Metric System, or inspect the
> recorded results in `output/`.

## Results

Recorded in `output/` and reproduced by the commands above.

**Scenario** — 11 interaction occurrences realizing 5 of the 8 defined
interaction types; 7 of 10 responsibilities instantiated.

**Goal variation** — the same coordinator and responsibilities produce
different action sequences according to the goal:

| Goal | Occ. | Types | Outcome |
|---|---|---|---|
| G1 named metric requiring a calculation model, explanation requested | 8 | T3–T5 | computed, explained |
| G2 same metric, explanation not requested | 6 | T4, T5 | computed |
| G3 directly measured metric, explanation requested | 8 | T3–T5 | computed, explained |
| G4 no metric named; agent selects by required method | 8 | T3–T5 | selected 1 of 4, computed |
| G5 goal no discovered metric satisfies | 2 | T4 | terminated; L6 never engaged |

Three distinct action sequences; occurrence counts of 2, 6 and 8.

**Boundary invariants** — 7 probes, each an operation that would violate an
invariant if the boundary were not enforced; all four invariants preserved.

**Independent mapping** — 10 elements of an independently published agentic
architecture mapped to the responsibilities; none required a responsibility
outside L0–L9.

## Scope and limitations

- The evaluation exercises a single-agent, synchronous configuration.
  Multi-agent collaboration, asynchronous mediation, persistent memory, human
  approval and execution isolation are represented as variation points rather
  than instantiated.
- Of the seven invariant probes, those for I1 and I2 observe calls into the
  external enterprise system; those for I3 and I4 exercise components defined
  in this package.
- The independent mapping is a descriptive analysis of a published
  architecture, which is weaker evidence than instantiation, and that source is
  revised over time.
- Default runs use the deterministic explanation provider, so no model
  inference is performed unless a hosted provider is configured.

## Layout

```
agentic/
  responsibilities/   one module per instantiated responsibility
  adapters/           interchangeable access to the ESG system (HTTP / in-process)
  trace/              interaction recorder and the T1–T8 interaction types
output/               recorded results (JSON)
```
