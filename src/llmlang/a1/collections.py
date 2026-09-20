"""A1 bounded collection and deterministic text values.

The module intentionally has no dependency on the P0 model or checker.  Its
values are small, immutable runtime values which can be used by both the
reference interpreter and a generated target.  ``OptionValue`` and
``ResultValue`` are tagged values rather than Python exceptions; exceptions
are reserved for malformed host input and exhausted A1 budgets.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, TypeVar

T = TypeVar("T")
U = TypeVar("U")
A = TypeVar("A")


class A1CollectionError(ValueError):
    """Stable A1 collection/text diagnostic.

    ``phase`` is deliberately explicit because a resource failure must never
    be confused with a rejected value or a capacity Result.
    """

    def __init__(self, code: str, message: str, *, phase: str = "validate") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.phase = phase

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "diagnostic-v1",
            "phase": self.phase,
            "code": self.code,
            "message": self.message,
            "span": None,
            "symbol": None,
        }


class CapacityError(StrEnum):
    """The closed error type used by bounded ``append``."""

    CapacityExceeded = "CapacityExceeded"


@dataclass(frozen=True, slots=True)
class OptionValue[T]:
    """A small canonical ``Option<T>`` value."""

    tag: str
    value: T | None = None

    def __post_init__(self) -> None:
        if self.tag not in {"None", "Some"}:
            raise ValueError("Option tag must be None or Some")
        if self.tag == "None" and self.value is not None:
            raise ValueError("None cannot carry a payload")

    @property
    def is_some(self) -> bool:
        return self.tag == "Some"

    @property
    def is_none(self) -> bool:
        return self.tag == "None"

    def canonical(self) -> dict[str, object]:
        if self.is_none:
            return {"tag": "None"}
        return {"tag": "Some", "value": canonical_value(self.value)}


def option_none() -> OptionValue[Any]:
    return OptionValue("None")


def option_some[T](value: T) -> OptionValue[T]:
    return OptionValue("Some", value)


@dataclass(frozen=True, slots=True)
class ResultValue[T]:
    """A small canonical ``Result<T,E>`` value."""

    tag: str
    value: T | None = None
    error: object | None = None

    def __post_init__(self) -> None:
        if self.tag not in {"Ok", "Err"}:
            raise ValueError("Result tag must be Ok or Err")
        if self.tag == "Ok" and self.error is not None:
            raise ValueError("Ok cannot carry an error")
        if self.tag == "Err" and self.value is not None:
            raise ValueError("Err cannot carry a value")

    @property
    def is_ok(self) -> bool:
        return self.tag == "Ok"

    @property
    def is_err(self) -> bool:
        return self.tag == "Err"

    def canonical(self) -> dict[str, object]:
        if self.is_ok:
            return {"tag": "Ok", "value": canonical_value(self.value)}
        return {"tag": "Err", "error": canonical_value(self.error)}


def result_ok[T](value: T) -> ResultValue[T]:
    return ResultValue("Ok", value=value)


def result_err(error: object) -> ResultValue[Any]:
    return ResultValue("Err", error=error)


@dataclass(frozen=True, slots=True)
class A1CollectionBudget:
    """Immutable bounds used before a collection operation starts."""

    max_list_capacity: int = 256
    max_text_bytes: int = 1_024
    max_collection_steps: int = 100_000

    def __post_init__(self) -> None:
        for name in ("max_list_capacity", "max_text_bytes", "max_collection_steps"):
            _require_nat(getattr(self, name), "A1_BUDGET", f"{name} must be a Nat")

    def check_list(self, capacity: int) -> None:
        if capacity > self.max_list_capacity:
            raise A1CollectionError(
                "A1_BUDGET",
                f"list capacity {capacity} exceeds max_list_capacity {self.max_list_capacity}",
                phase="resource",
            )

    def check_text(self, byte_count: int) -> None:
        if byte_count > self.max_text_bytes:
            raise A1CollectionError(
                "A1_BUDGET",
                f"text byte count {byte_count} exceeds max_text_bytes {self.max_text_bytes}",
                phase="resource",
            )

    def check_steps(self, steps: int) -> None:
        if steps > self.max_collection_steps:
            raise A1CollectionError(
                "A1_BUDGET",
                f"collection steps {steps} exceed max_collection_steps {self.max_collection_steps}",
                phase="resource",
            )

    def check_list_operation(self, capacity: int, steps: int) -> None:
        self.check_list(capacity)
        self.check_steps(steps)


CollectionBudget = A1CollectionBudget
A1Budget = A1CollectionBudget


@dataclass(frozen=True, slots=True)
class BoundedList[T]:
    """An immutable ordered ``List<T,N>`` whose length never exceeds ``N``."""

    values: tuple[T, ...]
    capacity: int

    def __init__(self, values: tuple[T, ...] | list[T], capacity: int) -> None:
        _require_nat(capacity, "A1_TYPE_CAPACITY", "list capacity must be a non-negative Nat")
        frozen_values = tuple(values)
        if len(frozen_values) > capacity:
            raise A1CollectionError(
                "A1_LIST_BOUNDS",
                f"list length {len(frozen_values)} exceeds capacity {capacity}",
            )
        object.__setattr__(self, "values", frozen_values)
        object.__setattr__(self, "capacity", capacity)

    @classmethod
    def empty(cls, capacity: int) -> BoundedList[Any]:
        return cls((), capacity)

    @classmethod
    def from_values(cls, values: list[T] | tuple[T, ...], capacity: int) -> BoundedList[T]:
        return cls(values, capacity)

    @property
    def length(self) -> int:
        return len(self.values)

    def __iter__(self) -> Iterator[T]:
        return iter(self.values)

    def __len__(self) -> int:
        """Expose Python's collection protocol without adding ``length(Text)``."""
        return self.length

    def __getitem__(self, position: int) -> T:
        return self.values[position]

    def to_tuple(self) -> tuple[T, ...]:
        return self.values

    def canonical(self) -> dict[str, object]:
        return {
            "kind": "list",
            "capacity": self.capacity,
            "values": [canonical_value(value) for value in self.values],
        }

    def validate_budget(self, budget: A1CollectionBudget) -> None:
        budget.check_list(self.capacity)

    def index(self, position: int) -> OptionValue[T]:
        _require_nat(position, "A1_LIST_BOUNDS", "list index must be a non-negative Nat")
        if position >= self.length:
            return option_none()
        return option_some(self.values[position])

    def append(self, value: T) -> ResultValue[BoundedList[T]]:
        if self.length == self.capacity:
            return result_err(CapacityError.CapacityExceeded)
        return result_ok(BoundedList(self.values + (value,), self.capacity))

    def map(
        self,
        callback: Callable[[T], U],
        *,
        budget: A1CollectionBudget | None = None,
    ) -> BoundedList[U]:
        if budget is not None:
            budget.check_list_operation(self.capacity, self.length)
        # The comprehension is intentionally left-to-right: callback count
        # and order are part of the A1 semantics.
        return BoundedList(tuple(callback(value) for value in self.values), self.capacity)

    def fold(
        self,
        initial: A,
        callback: Callable[[A, T], A],
        *,
        budget: A1CollectionBudget | None = None,
    ) -> A:
        if budget is not None:
            budget.check_list_operation(self.capacity, self.length)
        accumulator = initial
        for value in self.values:
            accumulator = callback(accumulator, value)
        return accumulator


@dataclass(frozen=True, slots=True)
class BoundedText:
    """An immutable Unicode-scalar sequence bounded by UTF-8 bytes."""

    value: str
    max_bytes: int

    def __post_init__(self) -> None:
        _require_nat(self.max_bytes, "A1_TYPE_CAPACITY", "text capacity must be a non-negative Nat")
        try:
            encoded = self.value.encode("utf-8", "strict")
        except (AttributeError, UnicodeEncodeError) as error:
            raise A1CollectionError(
                "A1_TEXT_ENCODING",
                "text must contain valid Unicode scalar values",
            ) from error
        if "\x00" in self.value:
            raise A1CollectionError("A1_TEXT_NUL", "U+0000 is not permitted in A1 Text")
        if len(encoded) > self.max_bytes:
            raise A1CollectionError(
                "A1_TEXT_CAPACITY",
                f"UTF-8 text uses {len(encoded)} bytes, capacity is {self.max_bytes}",
            )

    @classmethod
    def from_utf8(cls, raw: bytes | bytearray | memoryview, max_bytes: int) -> BoundedText:
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            raise A1CollectionError("A1_TEXT_ENCODING", "from_utf8 expects a byte sequence")
        try:
            value = bytes(raw).decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise A1CollectionError(
                "A1_TEXT_ENCODING", "byte sequence is not strict UTF-8"
            ) from error
        return cls(value, max_bytes)

    @property
    def raw_bytes(self) -> bytes:
        return self.value.encode("utf-8")

    @property
    def utf8_bytes(self) -> int:
        return len(self.raw_bytes)

    @property
    def codepoint_count(self) -> int:
        return len(self.value)

    def canonical(self) -> dict[str, object]:
        return {
            "kind": "text",
            "max_bytes": self.max_bytes,
            "utf8_hex": self.raw_bytes.hex(),
        }

    def validate_budget(self, budget: A1CollectionBudget) -> None:
        budget.check_text(self.utf8_bytes)

    def prefix_codepoints(self, count: int) -> BoundedText:
        _require_nat(count, "A1_TEXT_OPERATION", "prefix count must be a non-negative Nat")
        return BoundedText(self.value[:count], self.max_bytes)

    def concat(self, other: BoundedText, *, max_bytes: int | None = None) -> BoundedText:
        if not isinstance(other, BoundedText):
            raise A1CollectionError("A1_TEXT_OPERATION", "concat expects another A1 Text")
        target_capacity = self.max_bytes + other.max_bytes if max_bytes is None else max_bytes
        _require_nat(target_capacity, "A1_TYPE_CAPACITY", "text capacity must be a Nat")
        combined = self.raw_bytes + other.raw_bytes
        if len(combined) > target_capacity:
            raise A1CollectionError(
                "A1_TEXT_CAPACITY",
                f"concatenated text uses {len(combined)} bytes, capacity is {target_capacity}",
            )
        # Decode through the strict constructor to keep one validation path.
        return BoundedText.from_utf8(combined, target_capacity)

    def __str__(self) -> str:
        return self.value


def _require_nat(value: object, code: str, message: str) -> None:
    if type(value) is not int or value < 0:
        raise A1CollectionError(code, message)


def canonical_value(value: object) -> object:
    """Recursively produce the target-independent tagged value form."""

    if hasattr(value, "canonical") and callable(value.canonical):
        return value.canonical()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [canonical_value(item) for item in value]
    if isinstance(value, list):
        return [canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): canonical_value(item) for key, item in value.items()}
    return value


def list_length[T](values: BoundedList[T]) -> int:
    return values.length


def index[T](values: BoundedList[T], position: int) -> OptionValue[T]:
    return values.index(position)


def append[T](values: BoundedList[T], value: T) -> ResultValue[BoundedList[T]]:
    return values.append(value)


def map_list[T, U](
    values: BoundedList[T],
    callback: Callable[[T], U],
    *,
    budget: A1CollectionBudget | None = None,
) -> BoundedList[U]:
    return values.map(callback, budget=budget)


def fold_list[T, A](
    values: BoundedList[T],
    initial: A,
    callback: Callable[[A, T], A],
    *,
    budget: A1CollectionBudget | None = None,
) -> A:
    return values.fold(initial, callback, budget=budget)


def utf8_bytes(value: BoundedText) -> int:
    return value.utf8_bytes


def codepoint_count(value: BoundedText) -> int:
    return value.codepoint_count


def prefix_codepoints(value: BoundedText, count: int) -> BoundedText:
    return value.prefix_codepoints(count)


def concat(left: BoundedText, right: BoundedText, *, max_bytes: int | None = None) -> BoundedText:
    return left.concat(right, max_bytes=max_bytes)


__all__ = [
    "A1CollectionBudget",
    "A1CollectionError",
    "A1Budget",
    "BoundedList",
    "BoundedText",
    "CapacityError",
    "CollectionBudget",
    "OptionValue",
    "ResultValue",
    "append",
    "canonical_value",
    "codepoint_count",
    "concat",
    "fold_list",
    "index",
    "list_length",
    "map_list",
    "option_none",
    "option_some",
    "prefix_codepoints",
    "result_err",
    "result_ok",
    "utf8_bytes",
]
