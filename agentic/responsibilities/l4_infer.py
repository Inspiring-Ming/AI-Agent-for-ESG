"""L4 -- Model Access & Inference (Infer).

Every model call made on behalf of L3 passes through here, so model choice,
request shaping, refusal handling, and output-contract validation are owned by
L4 rather than by the coordinator.

Output contract: the response must either request one or more *registered*
tools or end its turn with text. Refusals, truncation, and calls to
unregistered tools are contract violations, which L3 treats as failures.

Boundary: validation here concerns whether an inference result can be consumed
by the application. Whether information may leave the controlled system
boundary remains with L2.
"""

import os
from typing import Any, Dict, Optional


class ModelAccess:
    RESPONSIBILITY = "L4"
    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, model: Optional[str] = None, effort: str = "medium"):
        import anthropic
        self._client = anthropic.Anthropic()
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
        self.effort = effort

    @property
    def provider_name(self) -> str:
        return self.model

    def step(self, system: str, messages: list, tools: list) -> Dict[str, Any]:
        """One inference request; returns the response and its contract status."""
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=messages,
            tools=tools,
            output_config={"effort": self.effort},
            # On a policy decline, the API re-runs the request on a fallback
            # model chosen by refusal category, inside the same call.
            betas=[self.FALLBACK_BETA],
            fallbacks="default",
        )
        allowed = {t["name"] for t in tools}
        return {"response": response,
                "contract": self._validate(response, allowed)}

    @staticmethod
    def _validate(response, allowed) -> str:
        if response.stop_reason == "refusal":
            return "refusal"
        if response.stop_reason == "max_tokens":
            return "truncated"
        if response.stop_reason == "tool_use":
            names = [b.name for b in response.content if b.type == "tool_use"]
            return "success" if names and all(n in allowed for n in names) \
                else "unregistered_tool"
        if response.stop_reason == "end_turn":
            return "success"
        return f"unexpected_stop:{response.stop_reason}"
