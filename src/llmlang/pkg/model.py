"""Immutable authorized inputs and explicit bounded package diagnostics."""

from dataclasses import dataclass

from llmlang.model import Candidate, Specification


class PkgError(Exception):
    def __init__(
        self, code: str, message: str, phase: str = "resolve", symbol: str | None = None
    ) -> None:
        super().__init__(message)
        self.code, self.message, self.phase, self.symbol = code, message, phase, symbol

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "diagnostic-v1",
            "code": self.code,
            "message": self.message,
            "phase": self.phase,
            "span": None,
            "symbol": self.symbol,
        }


@dataclass(frozen=True)
class PkgLimits:
    max_packages: int = 64
    max_modules: int = 256
    max_functions: int = 1024
    max_imports: int = 4096
    max_total_bytes: int = 4194304
    max_file_bytes: int = 131072


@dataclass(frozen=True)
class Import:
    alias: str
    package: str
    module: str
    export: str


@dataclass(frozen=True)
class Module:
    name: str
    names: tuple[str, ...]
    imports: tuple[Import, ...]
    exports: tuple[str, ...]
    spec: Specification
    candidate: Candidate


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    dependencies: tuple[tuple[str, str], ...]
    modules: tuple[Module, ...]


@dataclass(frozen=True)
class Snapshot:
    root: str
    packages: tuple[Package, ...]


@dataclass(frozen=True)
class BoundProgram:
    spec: Specification
    candidate: Candidate
    manifest: dict[str, object]
