"""L5 -- Enterprise Context & Knowledge (Ground).

Enterprise grounding for this case is ontology-driven traversal of the ESG
Metric Knowledge Graph. The knowledge graph is the enterprise context store;
the CQ1-CQ7 competency questions are its retrieval interface.

The traversal realises the ontology relationship chain

    Industry --ReportsUsing--> Framework --Includes--> Category
             --ConsistsOf--> Metric --IsCalculatedBy--> Model
             --RequiresInputFrom--> InputMetric --> DatasetVariable --> DataSource

so the grounded context returned to L3 carries not only the metric definition
but the provenance chain that makes a later computed value interpretable.

Boundary (Section IV-C): L5 manages information that persists independently of
any single execution and can be retrieved across executions. It does not decide
what to retrieve (L3) and it does not execute calculations (L6).
"""

from typing import Any, Dict, List, Optional


class EnterpriseKnowledgeGraph:
    """Ontology-driven retrieval and context assembly over the ESG KG."""

    RESPONSIBILITY = "L5"

    # competency questions exercised by each traversal step
    CQ = {
        "framework": "CQ1: Which reporting framework applies to this industry?",
        "categories": "CQ2: Which categories does the framework include?",
        "metrics": "CQ3: Which metrics are classified under this category?",
        "method": "CQ4: How is this metric calculated?",
        "inputs": "CQ5: Which input datapoints does the model require?",
        "implementation": "CQ6: Which implementation executes the model?",
        "source": "CQ7: What is the original source of this datapoint?",
    }

    def __init__(self, adapter):
        self._kg = adapter
        self.cq_trace: List[str] = []

    def _cq(self, key: str) -> None:
        self.cq_trace.append(self.CQ[key])

    # -- discovery over the ontology ---------------------------------------
    def frameworks_for_industry(self, industry: str) -> Dict[str, Any]:
        self._cq("framework")
        return self._kg.frameworks(industry)

    def categories_for_framework(self, industry: str,
                                 framework: str) -> Dict[str, Any]:
        self._cq("categories")
        return self._kg.categories(industry, framework)

    def metrics_for_category(self, industry: str,
                             category: str) -> Dict[str, Any]:
        self._cq("metrics")
        return self._kg.metrics(industry, category)

    def metrics_in_category(self, industry: str, category: str):
        """Discovery (CQ3): which metrics the category contains.

        Returns the candidate metrics with the calculation method each
        requires, which is the information the coordinator plans against.
        """
        self._cq("metrics")
        raw = self._kg.metrics(industry, category).get("metrics", [])
        out = []
        for m in raw:
            name = m.get("metric_name") or m.get("name") or m.get("id")
            if not name:
                continue
            out.append({"name": name,
                        "calculation_method": m.get("calculation_method"),
                        "unit": m.get("unit"),
                        "description": m.get("description")})
        return out

    # -- grounded context assembly -----------------------------------------
    def assemble_metric_context(self, industry: str,
                                category: Optional[str],
                                metric: str) -> Dict[str, Any]:
        """Walk the ontology chain and assemble the grounded context.

        Returns the metric definition, its calculation model, the input
        datapoints the model requires, and the provenance of that chain.
        """
        self.cq_trace = []

        # CQ1/CQ2: locate the metric within its framework and category
        fw = self.frameworks_for_industry(industry)
        framework = fw.get("framework")

        self._cq("categories")

        # CQ3: the metric as classified by the knowledge graph
        self._cq("metrics")
        catalogue = self._kg.metrics(industry, category)
        definition = self._find(catalogue.get("metrics", []), metric)

        # CQ4/CQ5/CQ6: calculation model, its inputs, and its implementation
        self._cq("method")
        models = self._kg.models(industry, metric)
        self._cq("inputs")
        self._cq("implementation")

        model = (models.get("models") or [None])[0]

        return {
            "metric": metric,
            "industry": industry,
            "framework": framework,
            "category": category,
            "definition": definition,
            "measurement_method": models.get("measurement_method"),
            "calculation_model": (model or {}).get("model_name"),
            "model_equation": (model or {}).get("model_equation"),
            "required_inputs": (model or {}).get("input_metrics", []),
            "unit": (definition or {}).get("unit"),
            "provenance": {
                "context_store": "ESG Metric Knowledge Graph (RDF)",
                "retrieval": "SPARQL competency questions",
                "competency_questions": list(self.cq_trace),
                "ontology_chain": ("Industry -> Framework -> Category -> Metric "
                                   "-> Model -> InputMetric -> DatasetVariable "
                                   "-> DataSource"),
            },
        }

    @staticmethod
    def _find(metrics: List[Dict[str, Any]],
              name: str) -> Optional[Dict[str, Any]]:
        norm = name.replace(" ", "").lower()
        for m in metrics:
            for key in ("metric_name", "name", "id"):
                v = m.get(key)
                if v and v.replace(" ", "").lower() == norm:
                    return m
        return None
