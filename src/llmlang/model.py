"""Immutable shared syntax; neither model responses nor solver objects live here."""

from dataclasses import dataclass
from typing import Literal

from .diagnostics import diagnostic

type Type = Literal["Int", "Bool"]
type Value = int | bool
PROFILE = "p0"
CHECKER_VERSION = "cert-v0.1"


@dataclass(frozen=True, slots=True)
class Expr:
    op: str
    args: tuple["Expr", ...] = ()
    value: Value | None = None


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    params: tuple[Type, ...]
    returns: Type
    requires: Expr
    ensures: Expr


@dataclass(frozen=True, slots=True)
class Specification:
    functions: tuple[FunctionSpec, ...]
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class Candidate:
    bodies: tuple[Expr, ...]
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class Program:
    spec: Specification
    candidate: Candidate


@dataclass(frozen=True, slots=True)
class Limits:
    max_source_bytes: int = 131072
    max_nodes: int = 12000
    max_parameters: int = 32
    max_depth: int = 96
    max_int_digits: int = 1024
    max_bits: int = 8192
    max_steps: int = 100000
    max_branches: int = 4096
    max_certificate_bytes: int = 2000000
    max_coefficient_bits: int = 8192
    solver_timeout_ms: int = 3000
    max_attempts: int = 3
    factory_timeout_ms: int = 30000


class LanguageError(Exception):
    def __init__(self, code: str, message: str, path: tuple[int, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_dict(self) -> dict[str, object]:
        return diagnostic({"code": self.code, "message": self.message, "path": list(self.path)})


def encode_value(value: Value) -> dict[str, object]:
    if type(value) is bool:
        return {"type": "Bool", "value": value}
    if type(value) is int:
        return {"type": "Int", "value": str(value)}
    raise LanguageError("E_VALUE", "Expected an exact Int or Bool")
