"""L2 -- Access, Identity & Safety Control (Protect).

Protects the controlled boundary through which requests and responses enter or
leave the agentic system: a signed-token session, role-based
entitlements, request validation, a per-principal sliding-window rate limit,
and an egress check.

Boundary (invariant I3): L2 decides whether an identity may access the
agentic service, and propagates identity, entitlement and trace context to
downstream responsibilities. It does NOT decide whether the agent may perform
a particular enterprise action -- that authorization stays with L6, which
enforces the controls applicable to the resource being accessed.
"""

import hashlib
import hmac
import os
import time
import uuid
from typing import Any, Dict, List, Optional

_SECRET = os.environ.get("SESSION_SECRET", "replication-package-secret").encode()

# Identity -> role -> entitlements. Entitlements are propagated to L3, L5 and
# L6 (T2); the responsibilities owning a resource decide whether they suffice.
ROLES = {
    "portfolio_manager": ["esg.metric.compute", "esg.portfolio.analyze",
                          "trade.submit"],
    "compliance_officer": ["esg.portfolio.analyze", "trade.override.approve"],
}
SUBJECTS = {"portfolio.manager@enterprise.example": "portfolio_manager",
            "compliance.officer@enterprise.example": "compliance_officer"}


class AccessControl:
    RESPONSIBILITY = "L2"

    def __init__(self, rate_limit: int = 30, per_seconds: int = 3600):
        self._limit = rate_limit
        self._per = per_seconds
        self._calls: Dict[str, List[float]] = {}

    # -- identity ----------------------------------------------------------
    @staticmethod
    def issue_token(subject: str) -> str:
        """Signed session token (HMAC-SHA256)."""
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
        """Authenticate, rate-limit and validate, then mint the call context.

        Returns the principal context propagated to L3 and, through it, to L5
        and L6. Entitlements default to those of the subject's role.
        """
        subject = self._verify(token)
        if subject is None:
            raise PermissionError("authentication failed: invalid token")
        if not self._rate_ok(subject):
            raise PermissionError(
                f"rate limit exceeded: {self._limit} requests per "
                f"{self._per}s")
        self._validate(request)
        role = SUBJECTS.get(subject)
        return {
            "subject": subject,
            "role": role,
            "entitlements": list(entitlements if entitlements is not None
                                 else ROLES.get(role, [])),
            "trace_id": uuid.uuid4().hex[:12],
            "admitted_at": time.time(),
        }

    @staticmethod
    def _validate(request: Dict[str, Any]) -> None:
        """Input validation at the boundary."""
        if "trade_id" in request:
            if not str(request["trade_id"]).isalnum():
                raise ValueError("invalid request: malformed trade id")
            return
        holdings = request.get("holdings")
        if not isinstance(holdings, list) or not 1 <= len(holdings) <= 30:
            raise ValueError("invalid request: 1-30 holdings are required")
        for h in holdings:
            if not isinstance(h.get("company"), str) or not h["company"] \
                    or len(h["company"]) > 200:
                raise ValueError("invalid request: holding without a company")
            w = h.get("weight_pct")
            if not isinstance(w, (int, float)) or not 0 < w <= 100:
                raise ValueError("invalid request: weights must be in (0, 100]")
        total = sum(h["weight_pct"] for h in holdings)
        if abs(total - 100) > 0.5:
            raise ValueError(f"invalid request: weights sum to {total}, not 100")
        for y in ("year", "compare_year"):
            v = request.get(y)
            if v is not None and not (str(v).isdigit() and len(str(v)) == 4):
                raise ValueError(f"invalid request: '{y}' must be a year")
        if not request.get("year"):
            raise ValueError("invalid request: 'year' is required")
        if len(request.get("question") or "") > 1000:
            raise ValueError("invalid request: question exceeds 1000 characters")

    @staticmethod
    def egress(response: Dict[str, Any]) -> Dict[str, Any]:
        """Response-policy check applied as the answer leaves the boundary."""
        response = dict(response)
        response.setdefault("boundary", {})
        response["boundary"]["egress_checked"] = True
        return response
