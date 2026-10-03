"""L4 -- Model Access & Inference (Infer).

Provides controlled and replaceable access to the models used during agent
execution. Two interchangeable providers are supplied to demonstrate the
replaceability the responsibility is defined by (Section IV-C):

  * DeterministicProvider -- template-based, no network, used by default so the
    case study is reproducible and runs without credentials.
  * ClaudeProvider        -- calls the Anthropic Messages API when a key is
                             present.

Boundary: validation performed here concerns whether an inference result can be
consumed by the application (output contract). Whether information may leave
the controlled system boundary remains with L2.
"""

import os
from typing import Any, Dict, Optional, Protocol


class InferenceProvider(Protocol):
    name: str

    def complete(self, prompt: str, context: Dict[str, Any]) -> str: ...


class DeterministicProvider:
    """Template-based explanation generator.

    Produces the natural-language explanation from the grounded context and the
    computed result, with no model call, so the trace is byte-reproducible.
    """

    name = "deterministic-template"

    def complete(self, prompt: str, context: Dict[str, Any]) -> str:
        ctx = context.get("metric_context", {})
        res = context.get("computation", {})
        prov = res.get("provenance", {})
        inputs = prov.get("inputs", {}) or {}
        parts = [
            f"{ctx.get('metric')} for {context.get('company')} in "
            f"{context.get('year')} is {res.get('display_value')} "
            f"{res.get('unit') or ctx.get('unit') or ''}".strip() + ".",
        ]
        if prov.get("equation"):
            parts.append(f"It is computed as {prov['equation']}.")
        if inputs:
            vals = ", ".join(f"{k} = {v:,.0f}" if isinstance(v, (int, float))
                             else f"{k} = {v}" for k, v in inputs.items())
            parts.append(f"Input values: {vals}.")
        if prov.get("model"):
            parts.append(f"Calculation model: {prov['model']}.")
        return " ".join(parts)


class ClaudeProvider:
    """Anthropic Messages API provider (used when ANTHROPIC_API_KEY is set)."""

    name = "claude"

    def __init__(self, model: str = "claude-sonnet-5"):
        # model id is configurable; see ANTHROPIC_MODEL
        self.model = model

    def complete(self, prompt: str, context: Dict[str, Any]) -> str:
        import os
        from anthropic import Anthropic  # imported lazily
        client = Anthropic()
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", self.model),
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")


class ModelAccess:
    """Unified model access with selection, invocation and output validation."""

    RESPONSIBILITY = "L4"

    def __init__(self, provider: Optional[InferenceProvider] = None):
        if provider is None:
            provider = (ClaudeProvider() if os.environ.get("ANTHROPIC_API_KEY")
                        else DeterministicProvider())
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.name

    def explain(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(context)
        text = self.provider.complete(prompt, context)
        return self._validate(text)

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        return (
            "Explain the following ESG metric result to an analyst in two or "
            "three sentences. Use only the values given; do not compute or "
            "estimate any number yourself.\n\n"
            f"{context}"
        )

    @staticmethod
    def _validate(text: str) -> Dict[str, Any]:
        """Output contract validation: consumable by the response assembler."""
        ok = isinstance(text, str) and len(text.strip()) > 0
        return {"status": "success" if ok else "contract_violation",
                "explanation": text.strip() if ok else None}
