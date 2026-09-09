"""Bounded candidate-source providers. Model output remains inert source text."""

import ipaddress
import json
import math
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ProviderError(Exception):
    """Safe diagnostics contain fixed messages, never response bodies or API keys."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CandidateProvider(Protocol):
    def generate(self, request: dict[str, object]) -> str:
        """Return one candidate source; the host owns all other configuration."""


class FileCandidates:
    """Consume source strings or host-supplied Paths for session-agent handoff/replay."""

    def __init__(self, sources: Iterable[str | Path], *, max_source_bytes: int = 131072) -> None:
        if type(max_source_bytes) is not int or max_source_bytes <= 0:
            raise ProviderError("E_PROVIDER_CONFIG", "Source byte limit must be positive")
        self._sources = iter(sources)
        self._max_source_bytes = max_source_bytes

    def generate(self, request: dict[str, object]) -> str:
        del request
        try:
            source = next(self._sources)
        except StopIteration:
            raise ProviderError("E_PROVIDER_EXHAUSTED", "Candidate sources exhausted") from None
        try:
            if isinstance(source, Path):
                with source.open("rb") as stream:
                    data = stream.read(self._max_source_bytes + 1)
            elif type(source) is str:
                data = source.encode("utf-8")
            else:
                raise ProviderError(
                    "E_PROVIDER_RESPONSE", "Candidate source must be text or a host Path"
                )
            if len(data) > self._max_source_bytes:
                raise ProviderError("E_PROVIDER_SIZE", "Candidate source exceeds byte limit")
            return data.decode("utf-8", errors="strict")
        except (OSError, UnicodeError):
            raise ProviderError(
                "E_PROVIDER_READ", "Candidate source could not be read as UTF-8"
            ) from None


class _Message(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    role: Literal["assistant"]
    content: str
    refusal: str | None = None


class _Choice(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    index: int = Field(ge=0, le=0)
    message: _Message
    finish_reason: Literal["stop"]

    @field_validator("index", mode="before")
    @classmethod
    def exact_index(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Expected an exact integer index")
        return value


class _Response(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    choices: list[_Choice] = Field(min_length=1, max_length=1)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON value")


_SYSTEM_PROMPT = """You write P0 candidate bodies against an immutable specification.
Return ONLY (candidate p0 (body EXPR) ...) with one body per fn, no Markdown.
You cannot change signatures, preconditions, postconditions or the checker.
Types: mathematical Int and Bool. Literals: canonical integers, true, false.
Expressions: (var N), (let VALUE BODY), (if CONDITION THEN ELSE), (call N ARGS...).
var 0 is the final parameter; let adds var 0 only inside BODY. Calls only target earlier fn indices.
Binary integer operators: int.add, int.sub, int.mul (one literal operand), int.le, int.lt, int.eq.
Boolean operators: unary not; binary and, or, bool.eq. There are no strings, effects or imports.
result is only legal in the specification's ensures. Your response is source data only.
Use prior feedback to repair the previous candidate without changing the specification."""


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    """Explicit full chat-completions endpoint; TLS except literal loopback test hosts.

    Timeout bounds socket operations; elapsed time is checked between bounded reads.
    This synchronous adapter is not a sandbox for arbitrary third-party Python providers.
    """

    endpoint: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = 15.0
    max_response_bytes: int = 262144

    def __post_init__(self) -> None:
        try:
            url = urlsplit(self.endpoint)
            host = url.hostname
            loopback = host is not None and ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        try:
            url = urlsplit(self.endpoint)
            if (
                not url.hostname
                or url.username is not None
                or url.password is not None
                or url.fragment
            ):
                raise ValueError
            if url.scheme != "https" and not (url.scheme == "http" and loopback):
                raise ValueError
            if not isinstance(self.model, str) or not self.model.strip():
                raise ValueError
            if self.api_key is not None and (
                not isinstance(self.api_key, str) or "\r" in self.api_key or "\n" in self.api_key
            ):
                raise ValueError
            if (
                isinstance(self.timeout_seconds, bool)
                or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 60
            ):
                raise ValueError
            if (
                type(self.max_response_bytes) is not int
                or not 0 < self.max_response_bytes <= 2000000
            ):
                raise ValueError
        except (TypeError, ValueError):
            raise ProviderError(
                "E_PROVIDER_CONFIG", "Invalid provider endpoint, model, credentials or limits"
            ) from None

    def generate(self, request: dict[str, object]) -> str:
        try:
            content = json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            body = json.dumps(
                {
                    "model": self.model,
                    "n": 1,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": content},
                    ],
                },
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ProviderError(
                "E_PROVIDER_REQUEST", "Provider request must be JSON data"
            ) from None
        if len(body) > 2000000:
            raise ProviderError("E_PROVIDER_SIZE", "Provider request exceeds byte limit")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        http_request = Request(self.endpoint, data=body, headers=headers, method="POST")
        deadline = time.monotonic() + self.timeout_seconds
        try:
            with build_opener(_NoRedirect()).open(
                http_request, timeout=self.timeout_seconds
            ) as response:
                data = bytearray()
                while True:
                    if time.monotonic() > deadline:
                        raise ProviderError("E_PROVIDER_TIMEOUT", "Provider time budget exhausted")
                    chunk = response.read1(min(65536, self.max_response_bytes + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > self.max_response_bytes:
                        raise ProviderError(
                            "E_PROVIDER_SIZE", "Provider response exceeds byte limit"
                        )
        except HTTPError:
            raise ProviderError(
                "E_PROVIDER_HTTP", "Provider returned an HTTP error or redirect"
            ) from None
        except TimeoutError:
            raise ProviderError("E_PROVIDER_TIMEOUT", "Provider time budget exhausted") from None
        except (URLError, OSError):
            raise ProviderError("E_PROVIDER_NETWORK", "Provider network request failed") from None
        try:
            decoded = json.loads(
                bytes(data).decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            parsed = _Response.model_validate(decoded, strict=True)
            message = parsed.choices[0].message
            if message.refusal is not None:
                raise ValueError("Provider refusal")
            return message.content
        except (UnicodeError, ValueError, ValidationError):
            raise ProviderError(
                "E_PROVIDER_RESPONSE", "Provider response is not a complete candidate message"
            ) from None
