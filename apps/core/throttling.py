"""DRF throttles backed by atomic ArangoDB windows (:mod:`apps.core.arango.rate_limits`).

Same policy as the stock ``AnonRateThrottle`` + ``UserRateThrottle`` + ``ScopedRateThrottle``
(rates from ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``, client identity from ``get_ident``
honouring ``NUM_PROXIES``, sliding windows, the stock ``wait()`` for ``Retry-After``), but each
request's checks are decided and recorded in one atomic statement instead of a get + set per
throttle.
"""

from __future__ import annotations

import time
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle

from apps.core.arango import rate_limits
from apps.core.arango.rate_limits import Check


def _rate(scope: str) -> tuple[int, float]:
    rates = SimpleRateThrottle.THROTTLE_RATES or {}
    if scope not in rates:
        raise ImproperlyConfigured(f"No default throttle rate set for {scope!r} scope")
    num, duration = SimpleRateThrottle.parse_rate(None, rates[scope])  # type: ignore[arg-type]
    if num is None or duration is None:
        raise ImproperlyConfigured(f"Throttle rate for {scope!r} is disabled")
    return int(num), float(duration)


class _AtomicThrottle(BaseThrottle):
    timer = staticmethod(time.time)

    def __init__(self) -> None:
        self._wait: float | None = None

    def checks(self, request: Request, view: Any) -> list[Check]:
        raise NotImplementedError

    @staticmethod
    def _check(scope: str, ident: str) -> Check:
        limit, duration = _rate(scope)
        return Check(scope, ident, limit, duration)

    def allow_request(self, request: Request, view: Any) -> bool:
        checks = self.checks(request, view)
        if not checks:
            return True
        now = self.timer()
        outcomes = rate_limits.hit(checks, now)
        waits = [w for o in outcomes if (w := o.wait(now)) is not None]
        self._wait = max(waits) if waits else None
        return all(o.allowed for o in outcomes)

    def wait(self) -> float | None:
        return self._wait


class DefaultRateThrottle(_AtomicThrottle):
    """``anon`` for anonymous clients plus ``user`` for everyone (the two stock defaults)."""

    def checks(self, request: Request, view: Any) -> list[Check]:
        user = request.user
        if user is not None and user.is_authenticated:
            return [self._check("user", str(user.pk))]
        ident = str(self.get_ident(request))
        return [self._check("anon", ident), self._check("user", ident)]


class ScopedRateThrottle(_AtomicThrottle):
    """Per-view ``throttle_scope`` (e.g. ``expensive``, ``export``), keyed by user or client."""

    def checks(self, request: Request, view: Any) -> list[Check]:
        scope = getattr(view, "throttle_scope", None)
        if not scope:
            return []
        user = request.user
        if user is not None and user.is_authenticated:
            return [self._check(scope, str(user.pk))]
        return [self._check(scope, str(self.get_ident(request)))]
