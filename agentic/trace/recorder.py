"""Interaction trace recorder.

Records every cross-responsibility interaction as it happens, so the runtime
trace reported in Section V-B is produced by the running system rather than
asserted in prose. Each record names the source and target responsibility, the
interaction purpose, and the information exchanged.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json
import time


# Interaction types defined by the architecture (Section IV-E). A runtime
# execution produces OCCURRENCES of these types; several occurrences may share
# a type, and a type may not occur at all in a given execution.
T_TYPES = {
    "T1": "Client Request / Response",
    "T2": "Identity & Authority Context",
    "T3": "Inference Request / Result",
    "T4": "Context Query / Grounded Context",
    "T5": "Action Intent / Observation",
    "T6": "Async Task / Observation Event",
    "T7": "Operational & Evaluation Evidence",
    "T8": "Improvement Feedback",
}


@dataclass
class Interaction:
    seq: int
    source: str          # responsibility id, e.g. "L3"
    target: str
    purpose: str         # e.g. "context retrieval"
    ttype: Optional[str] = None   # architecture interaction type (T1-T8)
    payload: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: Optional[float] = None

    def line(self) -> str:
        pay = ", ".join(f"{k}={v}" for k, v in self.payload.items())
        t = f" <{self.ttype}>" if self.ttype else ""
        return (f"({self.seq}){t} {self.source} -> {self.target}: "
                f"{self.purpose}" + (f" [{pay}]" if pay else ""))


class Trace:
    """Collects the ordered interactions of a single execution."""

    def __init__(self, scenario: str):
        self.scenario = scenario
        self.interactions: List[Interaction] = []
        self._t0 = time.time()

    def record(self, source: str, target: str, purpose: str,
               ttype: Optional[str] = None, **payload: Any) -> Interaction:
        it = Interaction(
            seq=len(self.interactions) + 1,
            source=source, target=target, purpose=purpose, ttype=ttype,
            payload={k: v for k, v in payload.items() if v is not None},
            elapsed_ms=round((time.time() - self._t0) * 1000, 1),
        )
        self.interactions.append(it)
        return it

    # -- reporting ---------------------------------------------------------
    def responsibilities_touched(self) -> List[str]:
        seen = []
        for it in self.interactions:
            for r in (it.source, it.target):
                if r not in seen:
                    seen.append(r)
        return sorted(seen)

    def types_observed(self) -> List[str]:
        return sorted({i.ttype for i in self.interactions if i.ttype})

    def occurrences_by_type(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for i in self.interactions:
            if i.ttype:
                out[i.ttype] = out.get(i.ttype, 0) + 1
        return dict(sorted(out.items()))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "interaction_occurrences": len(self.interactions),
            "interaction_types_defined": len(T_TYPES),
            "interaction_types_observed": self.types_observed(),
            "occurrences_by_type": self.occurrences_by_type(),
            "responsibilities_touched": self.responsibilities_touched(),
            "interactions": [asdict(i) for i in self.interactions],
        }

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.as_dict(), fh, indent=2)

    def print_trace(self) -> None:
        print(f"\nRuntime trace — {self.scenario}")
        print("-" * 68)
        for it in self.interactions:
            print("  " + it.line())
        print("-" * 68)
        obs = self.occurrences_by_type()
        print(f"  {len(self.interactions)} interaction occurrences across "
              f"{len(self.responsibilities_touched())} responsibilities: "
              f"{', '.join(self.responsibilities_touched())}")
        print(f"  realizing {len(obs)} of {len(T_TYPES)} defined interaction "
              f"types: " + ", ".join(f"{t}x{n}" for t, n in obs.items()))
