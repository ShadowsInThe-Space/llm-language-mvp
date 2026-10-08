"""Immutable typed web composition; checking produces a bound IR snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, NoReturn, cast

from llmlang.a1.effects import CHECKER as EFFECT_CHECKER
from llmlang.a1.effects import (
    REGISTRY_VERSION,
    EffectCheckResult,
    EffectError,
    EffectFunction,
    check_effect_graph,
)
from llmlang.a1.ir import canonical_bytes as a1_canonical_bytes
from llmlang.a1.ir import module_hash, validate_module
from llmlang.diagnostics import diagnostic

from .codecs import (
    MAX_NODES,
    MAX_WIRE_BYTES,
    BoolType,
    CodecType,
    ListType,
    OptionType,
    RecordType,
    ScalarType,
    TextType,
    decode_value,
    encode_value,
    max_wire_bytes,
    max_wire_nodes,
    type_descriptor,
    validate_type,
)
from .queries import (
    MAX_COLUMNS,
    MAX_TABLES,
    Column,
    CompiledQuery,
    ConditionalUpdate,
    Insert,
    Order,
    Param,
    Query,
    Scalar,
    Schema,
    SelectList,
    SelectUnique,
    Table,
    compile_query,
)

type Authorization = Literal["public", "authenticated", "admin"]
type Control = Literal["input", "select", "checkbox"]
FORMAT = "web-program-v1"
CODEC_VERSION = "web-codecs-v1"
QUERY_VERSION = "web-queries-v1"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")


class ProgramError(ValueError):
    def __init__(self, code: str, message: str, path: str = "program") -> None:
        self.code, self.message, self.path = code, message, path
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        return diagnostic({"code": self.code, "message": self.message, "path": self.path})


@dataclass(frozen=True, slots=True)
class QueryAction:
    name: str
    params: tuple[Param, ...]
    query: Query
    authorization: Authorization = "public"


@dataclass(frozen=True, slots=True)
class ViewStates:
    loading: str
    error: str
    empty: str
    success: str


@dataclass(frozen=True, slots=True)
class InputField:
    param: str
    label: str
    control: Control = "input"
    choices: tuple[tuple[str, Scalar], ...] = ()


@dataclass(frozen=True, slots=True)
class DisplayColumn:
    column: str
    label: str


@dataclass(frozen=True, slots=True)
class FormView:
    name: str
    action: str
    fields: tuple[InputField, ...]
    states: ViewStates
    submit_label: str = "Save"
    clear_label: str = "Clear"


@dataclass(frozen=True, slots=True)
class Selection:
    detail: str
    param: str
    column: str


@dataclass(frozen=True, slots=True)
class ListView:
    name: str
    action: str
    columns: tuple[DisplayColumn, ...]
    states: ViewStates
    selection: Selection | None = None


@dataclass(frozen=True, slots=True)
class DetailView:
    name: str
    action: str
    columns: tuple[DisplayColumn, ...]
    states: ViewStates


@dataclass(frozen=True, slots=True)
class ComponentUse:
    name: str


type View = FormView | ListView | DetailView
type ViewNode = View | ComponentUse


@dataclass(frozen=True, slots=True)
class ComponentDef:
    name: str
    children: tuple[ViewNode, ...]


@dataclass(frozen=True, slots=True)
class ComponentLibrary:
    name: str
    definitions: tuple[ComponentDef, ...]


@dataclass(frozen=True, slots=True)
class ComponentImport:
    library: str
    component: str
    alias: str


@dataclass(frozen=True, slots=True)
class WebProgram:
    name: str
    title: str
    schema: Schema
    actions: tuple[QueryAction, ...]
    views: tuple[ViewNode, ...]
    components: tuple[ComponentDef, ...] = ()
    libraries: tuple[ComponentLibrary, ...] = ()
    imports: tuple[ComponentImport, ...] = ()
    pure_library: bytes | None = None


@dataclass(frozen=True, slots=True)
class ProgramLimits:
    max_actions: int = 64
    max_components: int = 64
    max_nodes: int = 256
    max_component_depth: int = 16
    max_ir_bytes: int = 262144
    max_pure_bytes: int = 131072


DEFAULT_LIMITS = ProgramLimits()


@dataclass(frozen=True, slots=True)
class ActionContract:
    name: str
    params: tuple[Param, ...]
    query: Query
    authorization: Authorization
    compiled: CompiledQuery
    input_codec: RecordType | None
    output_codec: CodecType

    def decode_input(self, wire: object) -> dict[str, object]:
        if self.input_codec is None:
            if type(wire) is not dict or wire:
                _fail("W_PROGRAM_INPUT", "Empty action input object required", "input")
            result: dict[str, object] = {}
        else:
            decoded = cast(dict[str, Any], decode_value(self.input_codec, wire))
            result = cast(dict[str, object], decoded["fields"])
        self.validate_inputs(result)
        return result

    def validate_inputs(self, params: Mapping[str, object]) -> tuple[Scalar, ...]:
        return self.compiled.bind(params)

    def encode_output(self, value: object) -> object:
        return encode_value(self.output_codec, value)


@dataclass(frozen=True, slots=True)
class CheckedWebProgram:
    actions: tuple[ActionContract, ...]
    expanded_views: tuple[View, ...]
    effects: EffectCheckResult
    canonical_bytes: bytes
    semantic_hash: str

    def action(self, name: str) -> ActionContract:
        for action in self.actions:
            if action.name == name:
                return action
        raise KeyError(name)

    def snapshot(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.canonical_bytes))


def _fail(code: str, message: str, path: str) -> NoReturn:
    raise ProgramError(code, message, path)


def _name(value: object, path: str) -> None:
    if type(value) is not str or _NAME.fullmatch(value) is None:
        _fail("W_PROGRAM_BINDING", "ASCII identifier of 1..64 characters required", path)


def _label(value: object, path: str) -> None:
    if type(value) is not str or not value:
        _fail("W_PROGRAM_VIEW", "Nonempty display text required", path)
    try:
        encode_value(TextType(512), value)
    except ValueError as error:
        raise ProgramError("W_PROGRAM_VIEW", "Bounded scalar display text required",
                           path) from error


def _tuple(value: object, path: str) -> None:
    if type(value) is not tuple:
        _fail("W_PROGRAM_BINDING", "Immutable declaration tuple required", path)


def _schema(schema: Schema) -> Schema:
    if type(schema) is not Schema:
        _fail("W_PROGRAM_SCHEMA", "Declared schema required", "schema")
    try:
        _tuple(schema.tables, "schema.tables")
        if not 1 <= len(schema.tables) <= MAX_TABLES:
            _fail("W_PROGRAM_SCHEMA", "Table declaration budget exceeded", "schema.tables")
        tables = []
        for table in schema.tables:
            if type(table) is not Table:
                _fail("W_PROGRAM_SCHEMA", "Declared table required", "schema.tables")
            _tuple(table.columns, "schema.columns")
            if not 1 <= len(table.columns) <= MAX_COLUMNS:
                _fail("W_PROGRAM_SCHEMA", "Column declaration budget exceeded", "schema.columns")
            columns = []
            for column in table.columns:
                if type(column) is not Column:
                    _fail("W_PROGRAM_SCHEMA", "Declared column required", "schema.columns")
                validate_type(column.type)
                columns.append(Column(column.name, column.type, column.primary_key, column.unique))
            tables.append(Table(table.name, tuple(columns)))
        return Schema(tuple(tables))
    except ValueError as error:
        if isinstance(error, ProgramError):
            raise
        raise ProgramError("W_PROGRAM_SCHEMA", "Schema violates the typed query contract",
                           "schema") from error


def _query_shape(query: Query, path: str) -> None:
    if type(query) not in (Insert, SelectUnique, SelectList, ConditionalUpdate):
        _fail("W_PROGRAM_ACTION", "Closed query node required", path)
    _tuple(query.projection, path + ".projection")
    if len(query.projection) > MAX_COLUMNS:
        _fail("W_PROGRAM_ACTION", "Projection declaration budget exceeded", path)
    inputs: list[object] = []
    if isinstance(query, (Insert, ConditionalUpdate)):
        _tuple(query.values, path + ".values")
        if len(query.values) > MAX_COLUMNS:
            _fail("W_PROGRAM_ACTION", "Field binding budget exceeded", path)
        for pair in query.values:
            _tuple(pair, path + ".values")
            if len(pair) != 2:
                _fail("W_PROGRAM_ACTION", "Exact field binding required", path)
            inputs.append(pair[1])
    if isinstance(query, SelectList):
        _tuple(query.order, path + ".order")
        if any(type(order) is not Order for order in query.order):
            _fail("W_PROGRAM_ACTION", "Declared ordering required", path)
        _tuple(query.where, path + ".where")
        if len(query.where) > MAX_COLUMNS or len(query.order) > MAX_COLUMNS:
            _fail("W_PROGRAM_ACTION", "Predicate/ordering budget exceeded", path)
        for pair in query.where:
            _tuple(pair, path + ".where")
            if len(pair) != 2:
                _fail("W_PROGRAM_ACTION", "Exact predicate binding required", path)
            inputs.append(pair[1])
    elif isinstance(query, SelectUnique):
        inputs.append(query.value)
    elif isinstance(query, ConditionalUpdate):
        inputs.extend((query.key_value, query.expected_revision))
    for value in inputs:
        if isinstance(value, Param):
            if type(value) is not Param:
                _fail("W_PROGRAM_ACTION", "Declared parameter required", path)
            Param(value.name, value.type)
            validate_type(value.type)
        elif type(value) not in (str, int, bool):
            _fail("W_PROGRAM_ACTION", "Scalar literal or parameter required", path)


def _action(action: QueryAction, schema: Schema) -> ActionContract:
    if type(action) is not QueryAction:
        _fail("W_PROGRAM_ACTION", "Declared query action required", "actions")
    path = "actions." + action.name if isinstance(action.name, str) else "actions"
    _name(action.name, path + ".name")
    _tuple(action.params, path + ".params")
    if len(action.params) > MAX_COLUMNS:
        _fail("W_PROGRAM_ACTION", "Parameter declaration budget exceeded", path)
    if action.authorization not in ("public", "authenticated", "admin"):
        _fail("W_PROGRAM_ACTION", "Unknown server authorization policy", path)
    try:
        declared: dict[str, ScalarType] = {}
        for param in action.params:
            if type(param) is not Param or param.name in declared:
                _fail("W_PROGRAM_ACTION", "Unique declared parameters required", path)
            Param(param.name, param.type)
            validate_type(param.type)
            declared[param.name] = param.type
        _query_shape(action.query, path + ".query")
        compiled = compile_query(schema, action.query)
        used = {binding.value.name: binding.type for binding in compiled.bindings
                if isinstance(binding.value, Param)}
        if declared != used:
            _fail("W_PROGRAM_ACTION", "Declared parameters must exactly match typed query uses",
                  path)
        input_codec = (
            RecordType(action.name + "Input", tuple(declared.items())) if declared else None
        )
        row = RecordType(action.name + "Row", tuple((column.name, column.type)
                                                    for column in compiled.result.columns))
        output: CodecType = row
        if compiled.result.cardinality in ("optional", "conditional"):
            output = OptionType(row)
        elif compiled.result.cardinality == "bounded":
            output = ListType(row, compiled.result.max_rows)
        if input_codec is not None:
            validate_type(input_codec)
        validate_type(output)
        input_bytes = 2 if input_codec is None else max_wire_bytes(input_codec)
        # Request decoding includes the closed action/input envelope, not just the value.
        envelope_bytes = len(json.dumps(
            {"action": action.name, "input": None}, ensure_ascii=True,
            sort_keys=True, separators=(",", ":"),
        ).encode("ascii")) - len(b"null")
        if input_bytes + envelope_bytes > MAX_WIRE_BYTES:
            _fail("W_PROGRAM_LIMIT", "Action request exceeds the worst-case wire budget",
                  path + ".input")
        if max_wire_bytes(output) > MAX_WIRE_BYTES:
            _fail("W_PROGRAM_LIMIT", "Action result exceeds the worst-case wire budget",
                  path + ".output")
        input_nodes = 1 if input_codec is None else max_wire_nodes(input_codec)
        if input_nodes + 4 > MAX_NODES:
            _fail("W_PROGRAM_LIMIT", "Action request exceeds the worst-case JSON node budget",
                  path + ".input")
        if max_wire_nodes(output) > MAX_NODES:
            _fail("W_PROGRAM_LIMIT", "Action result exceeds the worst-case JSON node budget",
                  path + ".output")
    except ValueError as error:
        if isinstance(error, ProgramError):
            raise
        raise ProgramError("W_PROGRAM_ACTION", "Action violates the typed query contract",
                           path) from error
    return ActionContract(action.name, action.params, action.query, action.authorization,
                          compiled, input_codec, output)


def _view(view: View, actions: dict[str, ActionContract]) -> None:
    if type(view) not in (FormView, ListView, DetailView):
        _fail("W_PROGRAM_VIEW", "Closed view node required", "views")
    _name(view.name, "views.name")
    path = "views." + view.name
    _name(view.action, path + ".action")
    if view.action not in actions:
        _fail("W_PROGRAM_VIEW", "Unknown bound action", path)
    action = actions[view.action]
    if type(view.states) is not ViewStates:
        _fail("W_PROGRAM_VIEW", "All four view states required", path)
    for name in ("loading", "error", "empty", "success"):
        _label(getattr(view.states, name), path + ".states." + name)
    if isinstance(view, FormView):
        _tuple(view.fields, path + ".fields")
        _label(view.submit_label, path + ".submit_label")
        _label(view.clear_label, path + ".clear_label")
        if not isinstance(action.query, (Insert, ConditionalUpdate)) or not action.params:
            _fail("W_PROGRAM_VIEW", "Forms require a parameterized write action", path)
        params = {param.name: param.type for param in action.params}
        seen: set[str] = set()
        for field in view.fields:
            if type(field) is not InputField:
                _fail("W_PROGRAM_VIEW", "Declared input field required", path)
            _name(field.param, path + ".fields")
            _label(field.label, path + ".fields.label")
            if field.param not in params or field.param in seen:
                _fail("W_PROGRAM_VIEW", "Input fields must match distinct action parameters", path)
            seen.add(field.param)
            type_ = params[field.param]
            _tuple(field.choices, path + ".choices")
            if field.control not in ("input", "select", "checkbox"):
                _fail("W_PROGRAM_VIEW", "Unknown field control", path)
            if isinstance(type_, BoolType) != (field.control == "checkbox"):
                _fail("W_PROGRAM_VIEW", "Bool requires checkbox; checkbox requires Bool", path)
            if field.control == "select":
                if not field.choices or len(field.choices) > 64:
                    _fail("W_PROGRAM_VIEW", "Select requires 1..64 typed choices", path)
                seen_choices: set[tuple[type[object], Scalar]] = set()
                for choice in field.choices:
                    _tuple(choice, path + ".choices")
                    if len(choice) != 2:
                        _fail("W_PROGRAM_VIEW", "Choice requires label and typed scalar", path)
                    _label(choice[0], path + ".choices.label")
                    try:
                        encode_value(type_, choice[1])
                    except ValueError as error:
                        raise ProgramError("W_PROGRAM_VIEW", "Choice type differs from parameter",
                                           path) from error
                    key = (type(choice[1]), choice[1])
                    if key in seen_choices:
                        _fail("W_PROGRAM_VIEW", "Duplicate select value", path)
                    seen_choices.add(key)
            elif field.choices:
                _fail("W_PROGRAM_VIEW", "Only select controls declare choices", path)
        if seen != set(params):
            _fail("W_PROGRAM_VIEW", "Every action input needs one declared field", path)
    else:
        _tuple(view.columns, path + ".columns")
        if not view.columns:
            _fail("W_PROGRAM_VIEW", "Explicit display columns required", path)
        projected = {column.name for column in action.compiled.result.columns}
        seen_columns: set[str] = set()
        for column in view.columns:
            if type(column) is not DisplayColumn:
                _fail("W_PROGRAM_VIEW", "Declared display column required", path)
            _name(column.column, path + ".columns.column")
            _label(column.label, path + ".columns.label")
            if column.column not in projected or column.column in seen_columns:
                _fail("W_PROGRAM_VIEW", "Display columns must be distinct projected fields", path)
            seen_columns.add(column.column)
        if isinstance(view, ListView):
            if not isinstance(action.query, SelectList) or action.params:
                _fail("W_PROGRAM_VIEW", "Lists require a parameter-free bounded SelectList", path)
            if view.selection is not None:
                if type(view.selection) is not Selection:
                    _fail("W_PROGRAM_VIEW", "Declared selection binding required", path)
                for name in (view.selection.detail, view.selection.param, view.selection.column):
                    _name(name, path + ".selection")
        elif not isinstance(action.query, SelectUnique):
            _fail("W_PROGRAM_VIEW", "Details require SelectUnique cardinality", path)


def _selection(views: tuple[View, ...], actions: dict[str, ActionContract]) -> None:
    table: dict[str, View] = {}
    for view in views:
        if view.name in table:
            _fail("W_PROGRAM_VIEW", "Expanded view IDs must be unique", "views." + view.name)
        table[view.name] = view
    for view in views:
        if not isinstance(view, ListView) or view.selection is None:
            continue
        path = "views." + view.name + ".selection"
        selection = view.selection
        detail = table.get(selection.detail)
        if not isinstance(detail, DetailView):
            _fail("W_PROGRAM_VIEW", "Selection must target a declared detail view", path)
        source, target = actions[view.action], actions[detail.action]
        query = target.query
        if not isinstance(query, SelectUnique) or len(target.params) != 1:
            _fail("W_PROGRAM_VIEW", "Selection requires exactly one typed unique-action input",
                  path)
        param = target.params[0]
        columns = {column.name: column for column in source.compiled.result.columns}
        if (selection.param != param.name or selection.column not in columns
                or not isinstance(query.value, Param) or query.value.name != param.name
                or query.key != selection.column or query.table != source.query.table
                or columns[selection.column].type != param.type):
            _fail("W_PROGRAM_VIEW", "Selection must bind the same typed table unique key", path)


def _input(value: object, type_: ScalarType) -> dict[str, object]:
    if isinstance(value, Param):
        return {"param": value.name, "type": type_descriptor(value.type)}
    return {"literal": encode_value(type_, value)}


def _query_snapshot(query: Query, schema: Schema) -> dict[str, object]:
    table = schema.table(query.table)
    result: dict[str, object] = {"table": query.table, "projection": list(query.projection)}
    if isinstance(query, (Insert, ConditionalUpdate)):
        result["values"] = [{"column": name, "input": _input(value, table.column(name).type)}
                            for name, value in query.values]
    if isinstance(query, Insert):
        result["kind"] = "insert"
    elif isinstance(query, SelectList):
        result.update(kind="select_list", order=[
                      {"column": item.column, "direction": item.direction} for item in query.order],
                      limit=query.limit, offset=query.offset,
                      where=[{"column": name, "input": _input(value, table.column(name).type)}
                             for name, value in query.where])
    elif isinstance(query, SelectUnique):
        result.update(kind="select_unique", key=query.key,
                      value=_input(query.value, table.column(query.key).type))
    else:
        result.update(kind="conditional_update", key=query.key,
                      key_value=_input(query.key_value, table.column(query.key).type),
                      revision=query.revision,
                      expected_revision=_input(
                          query.expected_revision, table.column(query.revision).type))
    return result


def _view_snapshot(view: ViewNode, actions: dict[str, ActionContract]) -> dict[str, object]:
    if isinstance(view, ComponentUse):
        return {"kind": "component_use", "name": view.name}
    states = {name: getattr(view.states, name) for name in ("loading", "error", "empty", "success")}
    result: dict[str, object] = {"name": view.name, "action": view.action, "states": states}
    if isinstance(view, FormView):
        params = {param.name: param.type for param in actions[view.action].params}
        result.update(kind="form", submit_label=view.submit_label, clear_label=view.clear_label,
                      clear="local", fields=[{"param": field.param, "label": field.label,
                      "control": field.control, "type": type_descriptor(params[field.param]),
                      "choices": [{"label": label,
                                   "value": encode_value(params[field.param], value)}
                                  for label, value in field.choices]} for field in view.fields])
    else:
        result.update(kind="list" if isinstance(view, ListView) else "detail",
                      columns=[{"column": column.column, "label": column.label}
                               for column in view.columns])
        if isinstance(view, ListView):
            result["selection"] = None if view.selection is None else {
                "detail": view.selection.detail, "param": view.selection.param,
                "column": view.selection.column,
            }
    return result


def _pure(source: bytes | None, limits: ProgramLimits) -> dict[str, Any] | None:
    if source is None:
        return None
    if type(source) is not bytes or len(source) > limits.max_pure_bytes:
        _fail("W_PROGRAM_PURE", "Bounded canonical pure-library bytes required", "pure_library")
    try:
        module = json.loads(source)
        if not isinstance(module, dict) or a1_canonical_bytes(module) != source:
            _fail("W_PROGRAM_PURE", "Exact canonical pure-library IR required", "pure_library")
        if not isinstance(module.get("functions"), list) or len(module["functions"]) > 64:
            _fail("W_PROGRAM_PURE", "Pure library permits at most 64 functions", "pure_library")
        validate_module(module)
        return {"ir_hash": module_hash(module), "ir": module, "role": "provenance_only"}
    except (ValueError, RecursionError, TypeError) as error:
        if isinstance(error, ProgramError):
            raise
        raise ProgramError("W_PROGRAM_PURE", "Invalid canonical pure-library IR",
                           "pure_library") from error


def validate_program(
    program: WebProgram, *, limits: ProgramLimits = DEFAULT_LIMITS,
) -> CheckedWebProgram:
    """Always reconstruct checking; CheckedWebProgram is never an accepted shortcut."""
    if type(program) is not WebProgram:
        _fail("W_PROGRAM_BINDING", "Unchecked WebProgram declaration required", "program")
    if type(limits) is not ProgramLimits or any(type(value) is not int or value < 0 for value in (
        limits.max_actions, limits.max_components, limits.max_nodes, limits.max_component_depth,
        limits.max_ir_bytes, limits.max_pure_bytes,
    )) or limits.max_component_depth == 0:
        _fail("W_PROGRAM_LIMIT", "Valid nonnegative structural budgets required", "limits")
    _name(program.name, "name")
    _label(program.title, "title")
    for name in ("actions", "views", "components", "libraries", "imports"):
        _tuple(getattr(program, name), name)
    if not program.actions or len(program.actions) > limits.max_actions or not program.views:
        _fail("W_PROGRAM_LIMIT", "Nonempty bounded actions and views required", "program")
    if (len(program.views) > limits.max_nodes
            or len(program.components) > limits.max_components
            or len(program.libraries) > limits.max_components
            or len(program.imports) > limits.max_components):
        _fail("W_PROGRAM_LIMIT", "UI declaration budget exceeded", "program")
    schema = _schema(program.schema)
    actions: dict[str, ActionContract] = {}
    for declaration in program.actions:
        contract = _action(declaration, schema)
        if contract.name in actions:
            _fail("W_PROGRAM_BINDING", "Duplicate action name", "actions." + contract.name)
        actions[contract.name] = contract

    scopes: dict[str, dict[str, ComponentDef]] = {}
    component_count = 0
    node_count = len(program.views)

    def definitions(items: tuple[ComponentDef, ...], scope: str) -> None:
        nonlocal component_count, node_count
        _tuple(items, "components")
        if len(items) + component_count > limits.max_components:
            _fail("W_PROGRAM_LIMIT", "Component declaration budget exceeded", "components")
        index: dict[str, ComponentDef] = {}
        for item in items:
            if type(item) is not ComponentDef:
                _fail("W_PROGRAM_COMPONENT", "Declared component required", "components")
            _name(item.name, "components.name")
            _tuple(item.children, "components.children")
            if not item.children or item.name in index:
                _fail("W_PROGRAM_COMPONENT", "Unique nonempty components required", "components")
            index[item.name] = item
            component_count += 1
            node_count += len(item.children)
            if node_count > limits.max_nodes:
                _fail("W_PROGRAM_LIMIT", "Component node budget exceeded", "components")
        scopes[scope] = index

    definitions(program.components, "")
    for library in program.libraries:
        if type(library) is not ComponentLibrary:
            _fail("W_PROGRAM_COMPONENT", "Declared component library required", "libraries")
        _name(library.name, "libraries.name")
        _tuple(library.definitions, "libraries.definitions")
        if not library.definitions:
            _fail("W_PROGRAM_COMPONENT", "Library requires explicit definitions", "libraries")
        if library.name in scopes:
            _fail("W_PROGRAM_BINDING", "Duplicate library name", "libraries")
        definitions(library.definitions, library.name)
    if (component_count > limits.max_components or node_count > limits.max_nodes
            or len(program.imports) > limits.max_components
            or len(program.libraries) > limits.max_components):
        _fail("W_PROGRAM_LIMIT", "Component declaration budget exceeded", "components")
    imported: dict[str, tuple[str, str]] = {}
    for item in program.imports:
        if type(item) is not ComponentImport:
            _fail("W_PROGRAM_BINDING", "Explicit component import required", "imports")
        for name in (item.library, item.component, item.alias):
            _name(name, "imports")
        if (item.library not in scopes or item.component not in scopes[item.library]
                or item.alias in imported or item.alias in scopes[""]):
            _fail("W_PROGRAM_BINDING", "Unresolved or ambiguous component import", "imports")
        imported[item.alias] = (item.library, item.component)

    expansion_count = 0

    def expand(
        nodes: tuple[ViewNode, ...], scope: str, stack: tuple[tuple[str, str], ...],
    ) -> list[View]:
        nonlocal expansion_count
        result: list[View] = []
        for node in nodes:
            expansion_count += 1
            if expansion_count > limits.max_nodes:
                _fail("W_PROGRAM_LIMIT", "Component expansion budget exceeded", "views")
            if isinstance(node, ComponentUse):
                if type(node) is not ComponentUse:
                    _fail("W_PROGRAM_VIEW", "Closed view node required", "views")
                _name(node.name, "components.use")
                reference = imported.get(node.name) if not scope else None
                if reference is None:
                    reference = (scope, node.name)
                next_scope, name = reference
                if name not in scopes[next_scope]:
                    _fail("W_PROGRAM_BINDING", "Component use requires explicit declaration/import",
                          "components.use")
                if reference in stack:
                    _fail("W_PROGRAM_COMPONENT", "Cyclic component composition", "components.use")
                if len(stack) >= limits.max_component_depth:
                    _fail("W_PROGRAM_LIMIT", "Component depth budget exceeded", "components.use")
                result.extend(expand(
                    scopes[next_scope][name].children, next_scope, (*stack, reference)))
            else:
                _view(node, actions)
                result.append(node)
        return result

    # Unused definitions must also obey closed nodes, static bindings and acyclicity.
    for scope, components in scopes.items():
        for name, component in components.items():
            expand(component.children, scope, ((scope, name),))
    expanded = tuple(expand(program.views, "", ()))
    if not expanded:
        _fail("W_PROGRAM_VIEW", "Composition requires concrete views", "views")
    _selection(expanded, actions)
    # Selection references in unused definitions must also resolve. The view
    # namespace spans sibling definitions/libraries and the concrete composition.
    # Identical reused declarations coalesce; conflicting IDs never resolve silently.
    declared_views: dict[str, View] = {view.name: view for view in expanded}
    for components in scopes.values():
        for component in components.values():
            for node in component.children:
                if isinstance(node, ComponentUse):
                    continue
                existing = declared_views.get(node.name)
                if existing is not None and existing != node:
                    _fail("W_PROGRAM_VIEW", "Ambiguous view ID across component definitions",
                          "views." + node.name)
                declared_views[node.name] = node
    _selection(tuple(declared_views.values()), actions)
    pure = _pure(program.pure_library, limits)

    effect_functions: list[EffectFunction] = []
    for action in actions.values():
        effect = "db.write" if isinstance(action.query, (Insert, ConditionalUpdate)) else "db.read"
        capabilities = {effect}
        if action.authorization != "public":
            capabilities.add("identity.authenticated")
        if action.authorization == "admin":
            capabilities.add("identity.admin")
        effect_functions.append(EffectFunction(
            "server:" + action.name, "server", frozenset({effect}), frozenset(capabilities),
            host_calls=(effect,)))
    for view in expanded:
        calls = (
            ("ui:" + view.selection.detail,)
            if isinstance(view, ListView) and view.selection else ()
        )
        effect_functions.append(EffectFunction(
            "ui:" + view.name, "client", frozenset({"network.call"}),
            frozenset({"network.call"}), calls, ("network.call",)))
    try:
        effects = check_effect_graph(
            effect_functions, client_entries=tuple("ui:" + view.name for view in expanded),
            server_entries=tuple("server:" + name for name in actions))
    except EffectError as error:
        raise ProgramError("W_PROGRAM_EFFECT", "Derived graph violates the effect boundary",
                           ".".join(error.path)) from error

    def component_snapshot(component: ComponentDef) -> dict[str, object]:
        return {"name": component.name,
                "children": [_view_snapshot(node, actions) for node in component.children]}

    snapshot = {
        "format": FORMAT, "name": program.name, "title": program.title,
        "versions": {"codec": CODEC_VERSION, "query": QUERY_VERSION,
                     "effect_checker": EFFECT_CHECKER, "host_registry": REGISTRY_VERSION},
        "schema": [{"name": table.name, "columns": [
            {"name": column.name, "type": type_descriptor(column.type),
             "primary_key": column.primary_key, "unique": column.unique} for column in table.columns
        ]} for table in schema.tables],
        "actions": [{"name": action.name, "authorization": action.authorization,
                     "params": [{"name": param.name, "type": type_descriptor(param.type)}
                                for param in action.params],
                     "query": _query_snapshot(action.query, schema),
                     "input_codec": (None if action.input_codec is None
                                     else type_descriptor(action.input_codec)),
                     "output_codec": type_descriptor(action.output_codec),
                     "cardinality": action.compiled.result.cardinality}
                    for action in actions.values()],
        "views": [_view_snapshot(node, actions) for node in program.views],
        "expanded_views": [_view_snapshot(view, actions) for view in expanded],
        "components": [component_snapshot(component) for component in program.components],
        "libraries": [{"name": library.name,
                       "definitions": [component_snapshot(component)
                                       for component in library.definitions]}
                      for library in program.libraries],
        "imports": [{"library": item.library, "component": item.component, "alias": item.alias}
                    for item in program.imports],
        "pure_library": pure, "effects": effects.to_dict(),
        "limits": {name: getattr(limits, name) for name in limits.__dataclass_fields__},
    }
    canonical = json.dumps(snapshot, ensure_ascii=True, allow_nan=False, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    if len(canonical) > limits.max_ir_bytes:
        _fail("W_PROGRAM_LIMIT", "Canonical WebIR byte budget exceeded", "program")
    parts = (b"llmlang:web-program", FORMAT.encode(), canonical)
    framed = b"".join(len(part).to_bytes(8, "big") + part for part in parts)
    return CheckedWebProgram(tuple(actions.values()), expanded, effects, canonical,
                             hashlib.sha256(framed).hexdigest())
