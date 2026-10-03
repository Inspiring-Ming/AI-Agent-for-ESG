"""L2 -- Access, Identity & Safety Control (Protect).

Protects the controlled boundary through which requests and responses enter or
leave the agentic system. Modelled on the access gate of the authors' ESG
analytics demo: a signed-token session, request validation, and a per-principal
sliding-window rate limit.

Boundary (Section IV-B / IV-E): L2 decides whether an identity may access the
agentic service, and propagates identity, entitlement and trace context to
downstream responsibilities. It does NOT decide whether the agent may perform
a particular enterprise action -- that authorization stays with L6, which
enforces the controls applicable to the resource being accessed.
"""

import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, List, Optional

_SECRET = b"case-study-demonstration-secret"


class AccessControl:
    RESPONSIBILITY = "L2"

    def __init__(self, rate_limit: int = 30, per_seconds: int = 3600):
        self._limit = rate_limit
        self._per = per_seconds
        self._calls: Dict[str, List[float]] = {}

    # -- identity ----------------------------------------------------------
    @staticmethod
    def issue_token(subject: str) -> str:
        """Signed session token (HMAC-SHA256), as in the authors' demo gate."""
        issued = str(int(time.time()))
        mac = hmac.new(_SECRET, f"{subject}:{issued}".encode(),
                       hashlib.sha256).hexdigest()
        return f"{subject}:{issued}:{mac}"

    @staticmethod
    def _verify(token: str) -> Optional[str]:
        try:
            subject, issued, mac = token.split(":")
        except ValueError:
            return None
        expected = hmac.new(_SECRET, f"{subject}:{issued}".encode(),
                            hashlib.sha256).hexdigest()
        return subject if hmac.compare_digest(mac, expected) else None

    # -- boundary control --------------------------------------------------
    def _rate_ok(self, subject: str) -> bool:
        now = time.time()
        hits = [t for t in self._calls.get(subject, []) if now - t < self._per]
        hits.append(now)
        self._calls[subject] = hits
        return len(hits) <= self._limit

    def admit(self, token: str, request: Dict[str, Any],
              entitlements: Optional[List[str]] = None) -> Dict[str, Any]:
        """Authenticate, validate and rate-limit, then mint the call context.

        Returns the principal context propagated to L3 and, through it, to the
        information-access and action mechanisms in L5 and L6.
        """
        subject = self._verify(token)
        if subject is None:
            raise PermissionError("authentication failed: invalid token")

        if not self._rate_ok(subject):
            raise PermissionError(
                f"rate limit exceeded: {self._limit} requests per "
                f"{self._per}s")

        # input validation at the boundary
        for field in ("company", "metric", "year", "industry"):
            value = request.get(field)
            if not value or not isinstance(value, str):
                raise ValueError(f"invalid request: '{field}' is required")
            if len(value) > 200:
                raise ValueError(f"invalid request: '{field}' exceeds length")

        return {
            "subject": subject,
            "entitlements": list(entitlements or []),
            "trace_id": uuid.uuid4().hex[:12],
            "admitted_at": time.time(),
        }

    @staticmethod
    def egress(response: Dict[str, Any]) -> Dict[str, Any]:
        """Response-policy check applied as the answer leaves the boundary."""
        response = dict(response)
        response.setdefault("boundary", {})
        response["boundary"]["egress_checked"] = True
        return response
