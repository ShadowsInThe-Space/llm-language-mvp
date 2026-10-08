"""Closed typed queries with a reference SQLite executor.

SQL generation is independent of connection state. This module does not implement
or claim execution evidence for Cloudflare D1 or cross-statement transactions.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .codecs import (
    MAX_SAFE_INTEGER,
    BoolType,
    IntType,
    NatType,
    ScalarType,
    TextType,
    encode_value,
)

MAX_TABLES = 16
MAX_COLUMNS = 32
MAX_LIST_ROWS = 1000
MAX_LIST_OFFSET = 10000
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
type Scalar = str | int | bool


class QueryError(ValueError):
    """A schema, query, binding or result violated the closed query contract."""


def _name(value: str) -> None:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise QueryError("Identifiers must be ASCII names of 1..64 characters")


def _tuple(value: object) -> None:
    if not isinstance(value, tuple):
        raise QueryError("Declarations and query collections must be immutable tuples")


def _scalar(type_: ScalarType, value: object) -> Scalar:
    try:
        encode_value(type_, value)
    except ValueError as error:
        raise QueryError(str(error)) from error
    if not isinstance(value, (str, int, bool)):
        raise QueryError("Unsupported scalar value")
    return value


def _validate_type(type_: ScalarType) -> None:
    sample: Scalar = (
        "" if isinstance(type_, TextType) else False if isinstance(type_, BoolType) else 0
    )
    _scalar(type_, sample)


def _projection(names: tuple[str, ...]) -> None:
    _tuple(names)
    for name in names:
        _name(name)
    if not names or len(names) > MAX_COLUMNS or len(set(names)) != len(names):
        raise QueryError("Projection must be nonempty, bounded and contain no duplicates")


def _quote(name: str) -> str:
    # Only resolved and already validated schema names reach this function.
    return '"' + name + '"'


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: ScalarType
    primary_key: bool = False
    unique: bool = False

    def __post_init__(self) -> None:
        _name(self.name)
        if not isinstance(self.type, (TextType, IntType, NatType, BoolType)):
            raise QueryError("Columns support only non-null Text, Int, Nat and Bool")
        _validate_type(self.type)
        if type(self.primary_key) is not bool or type(self.unique) is not bool:
            raise QueryError("Column flags must be booleans")


@dataclass(frozen=True, slots=True)
class Table:
    name: str
    columns: tuple[Column, ...]

    def __post_init__(self) -> None:
        _name(self.name)
        _tuple(self.columns)
        if not 1 <= len(self.columns) <= MAX_COLUMNS:
            raise QueryError("A table requires 1..32 columns")
        if not all(isinstance(column, Column) for column in self.columns):
            raise QueryError("Table columns must be declared Columns")
        names = [column.name.casefold() for column in self.columns]
        if len(set(names)) != len(names):
            raise QueryError("Column identifiers must be unique ignoring ASCII case")
        if sum(column.primary_key for column in self.columns) != 1:
            raise QueryError("A table requires exactly one primary key")

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise QueryError(f"Unknown column {name!r} in table {self.name}")

    @property
    def primary_key(self) -> Column:
        return next(column for column in self.columns if column.primary_key)


@dataclass(frozen=True, slots=True)
class Schema:
    tables: tuple[Table, ...]

    def __post_init__(self) -> None:
        _tuple(self.tables)
        if not 1 <= len(self.tables) <= MAX_TABLES:
            raise QueryError("A schema requires 1..16 tables")
        if not all(isinstance(table, Table) for table in self.tables):
            raise QueryError("Schema tables must be declared Tables")
        names = [table.name.casefold() for table in self.tables]
        if len(set(names)) != len(names):
            raise QueryError("Table identifiers must be unique ignoring ASCII case")
        if any(table.name.casefold().startswith("sqlite_") for table in self.tables):
            raise QueryError("SQLite reserved table names are forbidden")

    def table(self, name: str) -> Table:
        for table in self.tables:
            if table.name == name:
                return table
        raise QueryError(f"Unknown table {name!r}")


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    type: ScalarType

    def __post_init__(self) -> None:
        _name(self.name)
        if not isinstance(self.type, (TextType, IntType, NatType, BoolType)):
            raise QueryError("Parameters must have scalar types")
        _validate_type(self.type)


type Input = Scalar | Param


@dataclass(frozen=True, slots=True)
class Insert:
    table: str
    values: tuple[tuple[str, Input], ...]
    projection: tuple[str, ...]

    def __post_init__(self) -> None:
        _name(self.table)
        _tuple(self.projection)
        _tuple(self.values)


@dataclass(frozen=True, slots=True)
class SelectUnique:
    table: str
    key: str
    value: Input
    projection: tuple[str, ...]

    def __post_init__(self) -> None:
        _name(self.table)
        _tuple(self.projection)


@dataclass(frozen=True, slots=True)
class Order:
    column: str
    direction: Literal["asc", "desc"] = "asc"


@dataclass(frozen=True, slots=True)
class SelectList:
    table: str
    projection: tuple[str, ...]
    order: tuple[Order, ...]
    limit: int
    offset: int = 0
    where: tuple[tuple[str, Input], ...] = ()

    def __post_init__(self) -> None:
        _name(self.table)
        _tuple(self.projection)
        _tuple(self.order)
        _tuple(self.where)


@dataclass(frozen=True, slots=True)
class ConditionalUpdate:
    table: str
    key: str
    key_value: Input
    revision: str
    expected_revision: Input
    values: tuple[tuple[str, Input], ...]
    projection: tuple[str, ...]

    def __post_init__(self) -> None:
        _name(self.table)
        _tuple(self.projection)
        _tuple(self.values)


type Query = Insert | SelectUnique | SelectList | ConditionalUpdate


@dataclass(frozen=True, slots=True)
class Binding:
    type: ScalarType
    value: Input
    incrementable: bool = False

    def resolve(self, params: Mapping[str, object]) -> Scalar:
        raw = params[self.value.name] if isinstance(self.value, Param) else self.value
        value = _scalar(self.type, raw)
        if self.incrementable and value == MAX_SAFE_INTEGER:
            raise QueryError("Revision increment would exceed the safe integer range")
        return int(value) if isinstance(self.type, BoolType) else value


@dataclass(frozen=True, slots=True)
class ResultDescriptor:
    columns: tuple[Column, ...]
    cardinality: Literal["one", "optional", "bounded", "conditional"]
    max_rows: int


@dataclass(frozen=True, slots=True)
class CompiledQuery:
    sql: str
    bindings: tuple[Binding, ...]
    result: ResultDescriptor

    def bind(self, params: Mapping[str, object] | None = None) -> tuple[Scalar, ...]:
        supplied = {} if params is None else params
        expected = {binding.value.name for binding in self.bindings
                    if isinstance(binding.value, Param)}
        if set(supplied) != expected:
            raise QueryError(f"Expected parameter names {sorted(expected)}")
        return tuple(binding.resolve(supplied) for binding in self.bindings)


@dataclass(frozen=True, slots=True)
class Rows:
    columns: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]


@dataclass(frozen=True, slots=True)
class ConditionNotMet:
    """The atomic UPDATE matched no row, including a stale revision or absent key."""


def _check_sql(column: Column) -> str:
    name = _quote(column.name)
    if isinstance(column.type, TextType):
        return (
            f"typeof({name}) = 'text' AND instr({name}, char(0)) = 0 "
            f"AND length(CAST({name} AS BLOB)) <= {column.type.capacity}"
        )
    if isinstance(column.type, BoolType):
        return f"typeof({name}) = 'integer' AND {name} IN (0, 1)"
    minimum = 0 if isinstance(column.type, NatType) else -MAX_SAFE_INTEGER
    return (f"typeof({name}) = 'integer' AND {name} >= {minimum} "
            f"AND {name} <= {MAX_SAFE_INTEGER}")


def schema_sql(schema: Schema) -> tuple[str, ...]:
    """Create non-null schema DDL with UTF-8 byte and storage-class CHECKs."""
    statements = []
    for table in schema.tables:
        definitions = []
        for column in table.columns:
            storage = "TEXT" if isinstance(column.type, TextType) else "INTEGER"
            key = " PRIMARY KEY" if column.primary_key else " UNIQUE" if column.unique else ""
            definitions.append(f"{_quote(column.name)} {storage} NOT NULL{key} "
                               f"CHECK ({_check_sql(column)})")
        statements.append(f"CREATE TABLE {_quote(table.name)} ({', '.join(definitions)})")
    return tuple(statements)


def _fields(
    table: Table, fields: tuple[tuple[str, Input], ...]
) -> tuple[tuple[Column, Input], ...]:
    _tuple(fields)
    if len(fields) > MAX_COLUMNS:
        raise QueryError("Too many fields")
    values: dict[str, Input] = {}
    for pair in fields:
        _tuple(pair)
        if len(pair) != 2:
            raise QueryError("Field bindings require a column name and value")
        name, value = pair
        table.column(name)
        if name in values:
            raise QueryError(f"Duplicate field {name}")
        values[name] = value
    return tuple((column, values[column.name]) for column in table.columns if column.name in values)


def _key(table: Table, name: str) -> Column:
    column = table.column(name)
    if not (column.primary_key or column.unique):
        raise QueryError("Single-row queries require a declared unique key")
    return column


def compile_query(schema: Schema, query: Query) -> CompiledQuery:
    """Compile a closed query, validating literal inputs and typed parameter uses."""
    if not isinstance(query, (Insert, SelectUnique, SelectList, ConditionalUpdate)):
        raise QueryError("Unsupported query kind")
    table = schema.table(query.table)
    _projection(query.projection)
    columns = tuple(table.column(name) for name in query.projection)
    projection = ", ".join(_quote(column.name) for column in columns)
    bindings: list[Binding] = []
    param_types: dict[str, ScalarType] = {}

    def bind(column: Column, value: Input, *, incrementable: bool = False) -> str:
        if isinstance(value, Param):
            if value.type != column.type:
                raise QueryError("Parameter type must equal the column type")
            previous = param_types.setdefault(value.name, value.type)
            if previous != value.type:
                raise QueryError("Repeated parameter names require the same type")
        else:
            checked = _scalar(column.type, value)
            if incrementable and checked == MAX_SAFE_INTEGER:
                raise QueryError("Revision increment would exceed the safe integer range")
        bindings.append(Binding(column.type, value, incrementable))
        return "?"

    cardinality: Literal["one", "optional", "bounded", "conditional"]
    max_rows = 1
    if isinstance(query, Insert):
        fields = _fields(table, query.values)
        if len(fields) != len(table.columns):
            raise QueryError("Insert must supply every column exactly once")
        names = ", ".join(_quote(column.name) for column, _ in fields)
        markers = ", ".join(bind(column, value) for column, value in fields)
        sql = (
            f"INSERT INTO {_quote(table.name)} ({names}) VALUES ({markers}) "
            f"RETURNING {projection}"
        )
        cardinality = "one"
    elif isinstance(query, SelectUnique):
        column = _key(table, query.key)
        marker = bind(column, query.value)
        sql = (
            f"SELECT {projection} FROM {_quote(table.name)} "
            f"WHERE {_quote(column.name)} = {marker}"
        )
        cardinality = "optional"
    elif isinstance(query, SelectList):
        _tuple(query.order)
        if not query.order or len(query.order) > MAX_COLUMNS:
            raise QueryError("Lists require an explicit bounded ordering")
        if type(query.limit) is not int or not 1 <= query.limit <= MAX_LIST_ROWS:
            raise QueryError("List limit must be an integer in 1..1000")
        if type(query.offset) is not int or not 0 <= query.offset <= MAX_LIST_OFFSET:
            raise QueryError("List offset must be an integer in 0..10000")
        ordering = []
        ordered_names = set()
        for order in query.order:
            if not isinstance(order, Order) or order.direction not in ("asc", "desc"):
                raise QueryError("Ordering requires declared columns and asc/desc direction")
            column = table.column(order.column)
            if column.name in ordered_names:
                raise QueryError("Duplicate order column")
            ordered_names.add(column.name)
            ordering.append(f"{_quote(column.name)} {order.direction.upper()}")
        if table.primary_key.name not in ordered_names:
            ordering.append(f"{_quote(table.primary_key.name)} ASC")
        predicates = [f"{_quote(column.name)} = {bind(column, value)}"
                      for column, value in _fields(table, query.where)]
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        bindings.extend((Binding(NatType(), query.limit), Binding(NatType(), query.offset)))
        sql = (f"SELECT {projection} FROM {_quote(table.name)}{where} "
               f"ORDER BY {', '.join(ordering)} LIMIT ? OFFSET ?")
        cardinality, max_rows = "bounded", query.limit
    else:
        key = _key(table, query.key)
        revision = table.column(query.revision)
        if not isinstance(revision.type, NatType) or revision.primary_key or revision.unique:
            raise QueryError("Revision must be a non-key Nat column")
        fields = _fields(table, query.values)
        if not fields or any(column.primary_key or column.name in (key.name, revision.name)
                             for column, _ in fields):
            raise QueryError("Update requires fields excluding keys and revision")
        assignments = [f"{_quote(column.name)} = {bind(column, value)}" for column, value in fields]
        assignments.append(f"{_quote(revision.name)} = {_quote(revision.name)} + 1")
        key_marker = bind(key, query.key_value)
        revision_marker = bind(revision, query.expected_revision, incrementable=True)
        sql = (f"UPDATE {_quote(table.name)} SET {', '.join(assignments)} "
               f"WHERE {_quote(key.name)} = {key_marker} AND {_quote(revision.name)} = "
               f"{revision_marker} RETURNING {projection}")
        cardinality = "conditional"
    return CompiledQuery(sql, tuple(bindings), ResultDescriptor(columns, cardinality, max_rows))


def _decode_cell(column: Column, raw: object) -> Scalar:
    if isinstance(column.type, TextType):
        valid = type(raw) is str
    else:
        valid = type(raw) is int
    if not valid:
        raise QueryError(f"Invalid SQLite storage class for {column.name}")
    if isinstance(column.type, BoolType):
        if raw not in (0, 1):
            raise QueryError(f"Invalid SQLite Bool for {column.name}")
        raw = bool(raw)
    return _scalar(column.type, raw)


def execute_sqlite(
    connection: sqlite3.Connection,
    schema: Schema,
    query: Query,
    params: Mapping[str, object] | None = None,
) -> Rows | ConditionNotMet:
    """Execute one validated statement; the caller owns commit/rollback boundaries."""
    compiled = compile_query(schema, query)
    cursor = connection.execute(compiled.sql, compiled.bind(params))
    try:
        raw_rows = cursor.fetchmany(compiled.result.max_rows + 1)
        if len(raw_rows) > compiled.result.max_rows:
            raise QueryError("Database violated declared result cardinality")
        if not raw_rows and compiled.result.cardinality == "conditional":
            return ConditionNotMet()
        if not raw_rows and compiled.result.cardinality == "one":
            raise QueryError("Insert did not return its declared row")
        columns = compiled.result.columns
        rows = tuple(
            tuple(_decode_cell(column, raw) for column, raw in zip(columns, row, strict=True))
            for row in raw_rows
        )
        return Rows(tuple(column.name for column in columns), rows)
    finally:
        cursor.close()
