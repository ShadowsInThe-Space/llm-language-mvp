"""Immutable data model for the A1 nominal type core.

The classes in this module deliberately contain no parser or target-runtime
logic.  They are the small, typed boundary shared by the A1 checker,
interpreter and lowerers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


class A1Error(Exception):
    """A stable, machine-readable A1 diagnostic."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: tuple[str, ...] = (),
        symbol: str | None = None,
        phase: str = "type",
    ) -> None:
        self.code = code
        self.message = message
        self.path = path
        self.symbol = symbol
        self.phase = phase
        super().__init__(message)

    def to_diagnostic(self) -> dict[str, object]:
        """Return the stable diagnostic-v1 shape used by A1 tooling."""

        return {
            "schema": "diagnostic-v1",
            "phase": self.phase,
            "code": self.code,
            "message": self.message,
            "path": list(self.path),
            "span": None,
            "symbol": self.symbol,
        }


@dataclass(frozen=True, slots=True)
class TypeRef:
    """A nominal type name and its (already resolved) type arguments."""

    name: str
    args: tuple[TypeRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise A1Error("E_A1_NAME", "Type name must not be empty")
        if not all(isinstance(arg, TypeRef) for arg in self.args):
            raise A1Error("E_A1_TYPE", "Type arguments must be resolved TypeRef values")

    @property
    def qualified_name(self) -> str:
        if not self.args:
            return self.name
        return f"{self.name}<{','.join(arg.qualified_name for arg in self.args)}>"

    def __str__(self) -> str:
        return self.qualified_name


UNIT: Final = TypeRef("Unit")
BOOL: Final = TypeRef("Bool")
INT: Final = TypeRef("Int")
NAT: Final = TypeRef("Nat")
TEXT: Final = TypeRef("Text")


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str
    type_ref: TypeRef


@dataclass(frozen=True, slots=True)
class RecordDef:
    name: str
    fields: tuple[FieldDef, ...] = ()
    type_params: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise A1Error("E_A1_NAME", f"Duplicate record field in {self.name}")
        if len(self.type_params) != len(set(self.type_params)):
            raise A1Error("E_A1_NAME", f"Duplicate type parameter in {self.name}")

    @property
    def type_ref(self) -> TypeRef:
        return TypeRef(self.name)

    @property
    def field_map(self) -> Mapping[str, FieldDef]:
        return {field.name: field for field in self.fields}


@dataclass(frozen=True, slots=True)
class ConstructorDef:
    name: str
    payload: TypeRef | None = None

    @property
    def has_payload(self) -> bool:
        # Unit is the source-level spelling of a constructor without a value.
        return self.payload is not None and self.payload != UNIT


@dataclass(frozen=True, slots=True)
class VariantDef:
    name: str
    constructors: tuple[ConstructorDef, ...] = ()
    type_params: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        names = [ctor.name for ctor in self.constructors]
        if len(names) != len(set(names)):
            raise A1Error("E_A1_NAME", f"Duplicate variant constructor in {self.name}")
        if len(self.type_params) != len(set(self.type_params)):
            raise A1Error("E_A1_NAME", f"Duplicate type parameter in {self.name}")

    @property
    def type_ref(self) -> TypeRef:
        return TypeRef(self.name)

    @property
    def constructor_map(self) -> Mapping[str, ConstructorDef]:
        return {constructor.name: constructor for constructor in self.constructors}


class TypeEnv:
    """A small mutable symbol table whose declarations remain immutable."""

    def __init__(self) -> None:
        self._records: dict[str, RecordDef] = {}
        self._variants: dict[str, VariantDef] = {}

    def add_record(self, definition: RecordDef) -> None:
        if definition.name in self._records or definition.name in self._variants:
            raise A1Error("E_A1_NAME", f"Duplicate type {definition.name}", symbol=definition.name)
        self._records[definition.name] = definition

    def add_variant(self, definition: VariantDef) -> None:
        if definition.name in self._records or definition.name in self._variants:
            raise A1Error("E_A1_NAME", f"Duplicate type {definition.name}", symbol=definition.name)
        self._variants[definition.name] = definition

    def record(self, name: str) -> RecordDef:
        try:
            return self._records[name]
        except KeyError as error:
            raise A1Error("E_A1_NAME", f"Unknown record {name}", symbol=name) from error

    def variant(self, name: str) -> VariantDef:
        try:
            return self._variants[name]
        except KeyError as error:
            raise A1Error("E_A1_NAME", f"Unknown variant {name}", symbol=name) from error


@dataclass(frozen=True, slots=True)
class TypedValue:
    value: object
    type_ref: TypeRef


@dataclass(frozen=True, slots=True)
class RecordValue:
    type_ref: TypeRef
    fields: tuple[tuple[str, TypedValue], ...]

    def get(self, name: str) -> TypedValue:
        for field_name, value in self.fields:
            if field_name == name:
                return value
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class VariantValue:
    type_ref: TypeRef
    constructor: str
    payload: TypedValue | None = None


def option_type(value_type: TypeRef) -> TypeRef:
    return TypeRef("Option", (value_type,))


def result_type(ok_type: TypeRef, error_type: TypeRef) -> TypeRef:
    return TypeRef("Result", (ok_type, error_type))
