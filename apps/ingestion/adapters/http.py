"""Resilient HTTP client for upstream sources (the only module family allowed to use httpx).

Behaviour (ESD §13):
* explicit connect/read timeouts on every request;
* retries only transient failures — timeouts, transport errors, 429 and 5xx — with full-jitter
  exponential backoff, honouring ``Retry-After``;
* non-transient responses (other 4xx) fail immediately and do not trip the circuit breaker;
* one exhausted call counts as one circuit-breaker failure; success closes the circuit;
* every call yields a :class:`SourceRequest` provenance record (url, params, status, attempts,
  byte size, SHA-256) persisted with ingestion runs and research manifests.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any, NoReturn

import httpx

from apps.core import metrics
from apps.core.clock import now_iso
from apps.core.errors import UpstreamError
from apps.core.resilience import CircuitBreaker, backoff_delay
from config.logging import get_logger

log = get_logger(__name__)

MAX_RESPONSE_BYTES = 50 * 1024 * 1024
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class SourceRequest:
    source: str
    url: str
    params: dict[str, str]
    requested_at: str
    status_code: int | None
    attempts: int
    elapsed_ms: float
    response_bytes: int
    response_sha256: str | None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FetchResult:
    body: bytes
    request: SourceRequest


class UpstreamRequestFailed(UpstreamError):
    """UpstreamError that also carries the provenance of the failed call."""

    def __init__(self, base: UpstreamError, request: SourceRequest) -> None:
        super().__init__(
            base.message,
            transient=base.transient,
            status_code=base.status_code,
            retry_after_seconds=base.retry_after_seconds,
            details={**base.details, "request": request.as_dict()},
        )
        self.request = request


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None  # HTTP-date form: fall back to computed backoff


class ResilientHttpClient:
    def __init__(
        self,
        *,
        source: str,
        breaker: CircuitBreaker,
        connect_timeout: float,
        read_timeout: float,
        max_retries: int,
        user_agent: str,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.source = source
        self.breaker = breaker
        self.max_retries = max_retries
        self._sleep = sleep
        self._client = httpx.Client(
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def get(self, url: str, params: Mapping[str, str] | None = None) -> FetchResult:
        query = dict(params or {})
        requested_at = now_iso()
        started = time.perf_counter()
        self.breaker.before_call()

        attempt = 0
        while True:
            attempt += 1
            error: UpstreamError
            try:
                response = self._client.get(url, params=query)
            except httpx.TimeoutException as exc:
                error = UpstreamError(f"{self.source} timeout: {exc}", transient=True)
            except httpx.TransportError as exc:
                error = UpstreamError(f"{self.source} transport error: {exc}", transient=True)
            else:
                body = response.content
                if response.status_code == 200:
                    if len(body) > MAX_RESPONSE_BYTES:
                        self._fail(
                            UpstreamError("response too large", transient=False),
                            url, query, requested_at, started, attempt, 200, count=False,
                        )  # fmt: skip
                    elapsed = round((time.perf_counter() - started) * 1000, 2)
                    self.breaker.record_success()
                    metrics.observe(f"source_latency_ms:{self.source}", elapsed)
                    metrics.incr(f"source_requests_ok:{self.source}")
                    return FetchResult(
                        body=body,
                        request=SourceRequest(
                            source=self.source,
                            url=str(response.url),
                            params=query,
                            requested_at=requested_at,
                            status_code=200,
                            attempts=attempt,
                            elapsed_ms=elapsed,
                            response_bytes=len(body),
                            response_sha256=hashlib.sha256(body).hexdigest(),
                        ),
                    )
                transient = response.status_code in TRANSIENT_STATUS
                error = UpstreamError(
                    f"{self.source} HTTP {response.status_code}",
                    transient=transient,
                    status_code=response.status_code,
                    retry_after_seconds=_retry_after(response),
                )
                if not transient:
                    self._fail(
                        error, url, query, requested_at, started, attempt,
                        response.status_code, count=False,
                    )  # fmt: skip

            if attempt > self.max_retries:
                self._fail(error, url, query, requested_at, started, attempt, error.status_code)
            delay = backoff_delay(attempt, retry_after=error.retry_after_seconds)
            log.info(
                "source_retry",
                source=self.source,
                attempt=attempt,
                delay_s=round(delay, 2),
                reason=error.message,
            )
            metrics.incr(f"source_retries:{self.source}")
            self._sleep(delay)

    def _fail(
        self,
        error: UpstreamError,
        url: str,
        query: dict[str, str],
        requested_at: str,
        started: float,
        attempts: int,
        status_code: int | None,
        *,
        count: bool = True,
    ) -> NoReturn:
        if count:
            self.breaker.record_failure()
        metrics.incr(f"source_requests_failed:{self.source}")
        request = SourceRequest(
            source=self.source,
            url=url,
            params=query,
            requested_at=requested_at,
            status_code=status_code,
            attempts=attempts,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            response_bytes=0,
            response_sha256=None,
            error=error.message,
        )
        log.warning(
            "source_request_failed",
            source=self.source,
            url=url,
            status=status_code,
            attempts=attempts,
            transient=error.transient,
            error=error.message,
        )
        raise UpstreamRequestFailed(error, request)
