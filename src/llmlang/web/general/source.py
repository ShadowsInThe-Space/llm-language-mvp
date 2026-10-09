"""Closed bounded web/component source lowered to the general typed program.

The reader accepts declarations, static queries and generic views, never host
code or embedded SQL/IR JSON. External libraries are explicit source snapshots.
"""

from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, NoReturn, cast

from llmlang.a1.ir import canonical_bytes
from llmlang.a1.source import A1SourceError
from llmlang.a1.source import SourceLimits as PureSourceLimits
from llmlang.a1.source import parse_source as parse_pure_source

from .codecs import BoolType, IntType, NatType, ScalarType, TextType
from .program import (
    Authorization,
    CheckedWebProgram,
    ComponentDef,
    ComponentImport,
    ComponentLibrary,
    ComponentUse,
    Control,
    DetailView,
    DisplayColumn,
    FormView,
    InputField,
    ListView,
    Pagination,
    ParamTransform,
    ProgramError,
    ProgramLimits,
    QueryAction,
    Selection,
    ViewNode,
    ViewStates,
    WebProgram,
    validate_program,
)
from .queries import (
    Column,
    ConditionalUpdate,
    Input,
    Insert,
    Order,
    Param,
    Query,
    QueryError,
    Scalar,
    Schema,
    SelectList,
    SelectUnique,
    Table,
)


@dataclass(frozen=True, slots=True)
class WebSourceSpan:
    offset: int
    line: int
    column: int


class WebSourceError(ValueError):
    """A deterministic source error with original character positions."""

    def __init__(
        self, code: str, message: str, location: str = "module",
        span: WebSourceSpan | None = None,
    ) -> None:
        self.code, self.location, self.span = code, location, span
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code, "message": str(self), "location": self.location,
            "line": self.span.line if self.span else None,
            "column": self.span.column if self.span else None,
        }


@dataclass(frozen=True, slots=True)
class WebSourceLimits:
    """Combined root/library reader budgets; expansion has ProgramLimits."""

    max_bytes: int = 262144
    max_depth: int = 32
    max_nodes: int = 8192
    max_integer_digits: int = 16

    def __post_init__(self) -> None:
        for name, ceiling in (("max_bytes", 1048576), ("max_depth", 64),
                              ("max_nodes", 65536), ("max_integer_digits", 16)):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= ceiling:
                raise WebSourceError("W_SOURCE_LIMIT", f"invalid {name}")


@dataclass(frozen=True, slots=True)
class ParsedComponentLibrary:
    library: ComponentLibrary
    canonical_source: str
    source_hash: str
    source_map: Mapping[str, WebSourceSpan]


@dataclass(frozen=True, slots=True)
class ParsedWebSource:
    program: WebProgram
    checked: CheckedWebProgram
    canonical_source: str
    source_hash: str
    semantic_hash: str
    source_map: Mapping[str, WebSourceSpan]


@dataclass(frozen=True, slots=True)
class _Node:
    kind: str
    value: Any
    span: WebSourceSpan


@dataclass(slots=True)
class _Budget:
    limits: WebSourceLimits
    bytes: int = 0
    nodes: int = 0

    def source(self, text: str) -> None:
        if not isinstance(text, str):
            raise WebSourceError("W_SOURCE_ENCODING", "source must be Unicode text")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise WebSourceError("W_SOURCE_ENCODING", "source contains a non-scalar") from exc
        if "\x00" in text:
            raise WebSourceError("W_SOURCE_ENCODING", "source contains NUL")
        self.bytes += size
        if self.bytes > self.limits.max_bytes:
            raise WebSourceError("W_SOURCE_LIMIT", "combined source byte budget exceeded")

    def node(self, span: WebSourceSpan) -> None:
        self.nodes += 1
        if self.nodes > self.limits.max_nodes:
            raise WebSourceError(
                "W_SOURCE_LIMIT", "combined source node budget exceeded", span=span
            )


_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")


def _fail(message: str, node: _Node, code: str = "SYNTAX", location: str = "module") -> NoReturn:
    raise WebSourceError(f"W_SOURCE_{code}", message, location, node.span)


def _read(source: str, budget: _Budget) -> _Node:
    budget.source(source)
    starts = [0] + [i + 1 for i, char in enumerate(source) if char == "\n"]

    def span(offset: int) -> WebSourceSpan:
        line = bisect_right(starts, offset)
        return WebSourceSpan(offset, line, offset - starts[line - 1] + 1)

    roots: list[_Node] = []
    stack: list[tuple[WebSourceSpan, list[_Node]]] = []
    offset = 0
    while offset < len(source):
        char = source[offset]
        if char in " \t\r\n":
            offset += 1
            continue
        at = span(offset)
        if char == ")":
            if not stack:
                raise WebSourceError("W_SOURCE_SYNTAX", "unexpected closing parenthesis", span=at)
            opened, children = stack.pop()
            (stack[-1][1] if stack else roots).append(_Node("list", tuple(children), opened))
            offset += 1
            continue
        budget.node(at)
        if char == "(":
            if len(stack) >= budget.limits.max_depth:
                raise WebSourceError("W_SOURCE_LIMIT", "source depth budget exceeded", span=at)
            stack.append((at, []))
            offset += 1
            continue
        begin = offset
        if char == '"':
            offset += 1
            escaped = False
            while offset < len(source):
                current = source[offset]
                offset += 1
                if current == '"' and not escaped:
                    break
                escaped = current == "\\" and not escaped
            else:
                raise WebSourceError("W_SOURCE_SYNTAX", "unterminated string", span=at)
            try:
                value = json.loads(source[begin:offset])
                value.encode("utf-8")
            except (ValueError, UnicodeEncodeError) as exc:
                raise WebSourceError(
                    "W_SOURCE_ENCODING", "invalid string escape/scalar", span=at
                ) from exc
            if "\x00" in value:
                raise WebSourceError("W_SOURCE_ENCODING", "string contains NUL", span=at)
            node = _Node("string", value, at)
        else:
            while offset < len(source) and source[offset] not in "() \t\r\n\"":
                offset += 1
            token = source[begin:offset]
            if _INTEGER.fullmatch(token):
                if len(token.lstrip("-")) > budget.limits.max_integer_digits:
                    raise WebSourceError("W_SOURCE_LIMIT", "integer digit budget exceeded", span=at)
                node = _Node("integer", int(token), at)
            elif _NAME.fullmatch(token):
                node = _Node("symbol", token, at)
            else:
                raise WebSourceError("W_SOURCE_SYNTAX", "invalid atom", span=at)
        (stack[-1][1] if stack else roots).append(node)
    if stack:
        raise WebSourceError("W_SOURCE_SYNTAX", "unclosed parenthesis", span=stack[-1][0])
    if len(roots) != 1:
        raise WebSourceError("W_SOURCE_SYNTAX", "exactly one source module required")
    return roots[0]


def _items(node: _Node, minimum: int = 0, maximum: int | None = None) -> tuple[_Node, ...]:
    if node.kind != "list" or len(node.value) < minimum:
        _fail("invalid form or missing argument", node)
    if maximum is not None and len(node.value) > maximum:
        _fail("unexpected argument", node)
    return cast(tuple[_Node, ...], node.value)


def _name(node: _Node) -> str:
    if node.kind != "symbol" or node.value in {"true", "false"}:
        _fail("identifier required", node)
    return str(node.value)


def _string(node: _Node) -> str:
    if node.kind != "string":
        _fail("quoted text required", node)
    return str(node.value)


def _number(node: _Node) -> int:
    if node.kind != "integer" or node.value < 0:
        _fail("non-negative integer required", node)
    return int(node.value)


def _form(
    node: _Node, head: str, minimum: int = 1, maximum: int | None = None,
) -> tuple[_Node, ...]:
    items = _items(node, minimum, maximum)
    if _name(items[0]) != head:
        _fail(f"{head} form required", node)
    return items[1:]


def _scalar(node: _Node) -> Scalar:
    if node.kind == "string":
        return str(node.value)
    if node.kind == "integer":
        return int(node.value)
    if node.kind == "symbol" and node.value in {"true", "false"}:
        return str(node.value) == "true"
    _fail("scalar literal required", node)


def _type(node: _Node) -> ScalarType:
    if node.kind == "symbol":
        types: dict[str, ScalarType] = {"Int": IntType(), "Nat": NatType(), "Bool": BoolType()}
        if node.value in types:
            return types[node.value]
    elif node.kind == "list":
        args = _form(node, "Text", 2, 2)
        return TextType(_number(args[0]))
    _fail("only Text, Int, Nat and Bool column/parameter types are supported", node, "TYPE")


def _input(node: _Node, params: dict[str, Param]) -> Input:
    if node.kind == "symbol" and node.value not in {"true", "false"}:
        name = _name(node)
        if name not in params:
            _fail("query references an undeclared parameter", node, "BINDING")
        return params[name]
    return _scalar(node)


def _pairs(node: _Node, head: str, params: dict[str, Param]) -> tuple[tuple[str, Input], ...]:
    result: list[tuple[str, Input]] = []
    names: set[str] = set()
    for pair in _form(node, head):
        key, value = _items(pair, 2, 2)
        name = _name(key)
        if name in names:
            _fail("duplicate column binding", pair, "BINDING")
        names.add(name)
        result.append((name, _input(value, params)))
    return tuple(result)


def _projection(node: _Node) -> tuple[str, ...]:
    return tuple(_name(item) for item in _form(node, "project", 2))


def _query(node: _Node, params: dict[str, Param]) -> Query:
    items = _items(node, 1)
    kind = _name(items[0])
    if kind == "insert":
        table, values, project = _form(node, kind, 4, 4)
        return Insert(_name(table), _pairs(values, "values", params), _projection(project))
    if kind == "select_unique":
        table, key, value, project = _form(node, kind, 5, 5)
        return SelectUnique(_name(table), _name(key), _input(value, params), _projection(project))
    if kind == "select_list":
        table, project, order, limit, offset, where, *cursor_nodes = _form(node, kind, 7, 8)
        ordering: list[Order] = []
        for item in _form(order, "order", 2):
            column, direction = _items(item, 2, 2)
            spelling = _name(direction)
            if spelling not in {"asc", "desc"}:
                _fail("order direction must be asc or desc", direction)
            ordering.append(Order(_name(column), cast(Literal["asc", "desc"], spelling)))
        return SelectList(
            _name(table), _projection(project), tuple(ordering),
            _number(_form(limit, "limit", 2, 2)[0]),
            _number(_form(offset, "offset", 2, 2)[0]), _pairs(where, "where", params),
            _pairs(cursor_nodes[0], "cursor", params) if cursor_nodes else (),
        )
    if kind == "conditional_update":
        table, key, key_value, revision, expected, values, project = _form(node, kind, 8, 8)
        return ConditionalUpdate(
            _name(table), _name(key), _input(key_value, params), _name(revision),
            _input(expected, params), _pairs(values, "values", params), _projection(project),
        )
    _fail("unsupported static query", node, "QUERY")


def _schema(node: _Node, source_map: dict[str, WebSourceSpan]) -> Schema:
    tables: list[Table] = []
    for t_index, item in enumerate(_form(node, "schema", 2)):
        parts = _form(item, "table", 3)
        columns: list[Column] = []
        path = f"schema.tables[{t_index}]"
        source_map[path] = item.span
        for c_index, column in enumerate(parts[1:]):
            data = _items(column, 2, 4)
            flags = [_name(flag) for flag in data[2:]]
            if len(set(flags)) != len(flags) or set(flags) - {"primary", "unique"}:
                _fail("column flags are unique primary/unique markers", column)
            columns.append(Column(
                _name(data[0]), _type(data[1]), "primary" in flags, "unique" in flags
            ))
            source_map[f"{path}.columns[{c_index}]"] = column.span
        tables.append(Table(_name(parts[0]), tuple(columns)))
    return Schema(tuple(tables))


def _action(node: _Node, path: str, source_map: dict[str, WebSourceSpan]) -> QueryAction:
    name, params_node, authorization, query, *transform_nodes = _form(node, "action", 5)
    params: dict[str, Param] = {}
    source_map[path] = node.span
    source_map.setdefault(f"actions.{_name(name)}", node.span)
    source_map[f"{path}.query"] = query.span
    for index, item in enumerate(_items(params_node)):
        param, type_node = _items(item, 2, 2)
        spelling = _name(param)
        if spelling in params:
            _fail("duplicate action parameter", item, "BINDING", path)
        params[spelling] = Param(spelling, _type(type_node))
        source_map[f"{path}.params[{index}]"] = item.span
    policy = _name(authorization)
    if policy not in {"public", "authenticated", "admin"}:
        _fail("unsupported authorization policy", authorization, "POLICY", path)
    transforms: list[ParamTransform] = []
    for index, transform_node in enumerate(transform_nodes):
        param_node, function_node, args_node = _form(transform_node, "transform", 4, 4)
        transforms.append(ParamTransform(
            _name(param_node), _name(function_node),
            tuple(_name(arg) for arg in _items(args_node)),
        ))
        source_map[f"{path}.transforms[{index}]"] = transform_node.span
        source_map.setdefault(
            f"actions.{_name(name)}.transforms.{index}", transform_node.span
        )
    return QueryAction(
        _name(name), tuple(params.values()), _query(query, params), cast(Authorization, policy),
        tuple(transforms),
    )


def _states(node: _Node) -> ViewStates:
    loading, error, empty, success = _form(node, "states", 5, 5)
    return ViewStates(*(_string(item) for item in (loading, error, empty, success)))


def _columns(node: _Node) -> tuple[DisplayColumn, ...]:
    columns: list[DisplayColumn] = []
    for item in _form(node, "columns", 2):
        column, label = _items(item, 2, 2)
        columns.append(DisplayColumn(_name(column), _string(label)))
    return tuple(columns)


def _pagination(node: _Node) -> Pagination:
    action, *pairs = _form(node, "paginate", 3)
    bindings: list[tuple[str, str]] = []
    names: set[str] = set()
    for pair in pairs:
        param, column = _items(pair, 2, 2)
        name = _name(param)
        if name in names:
            _fail("duplicate pagination parameter", pair, "BINDING")
        names.add(name)
        bindings.append((name, _name(column)))
    return Pagination(_name(action), tuple(bindings))


def _view(node: _Node, path: str, source_map: dict[str, WebSourceSpan]) -> ViewNode:
    items = _items(node, 1)
    kind = _name(items[0])
    source_map[path] = node.span
    if kind == "use":
        return ComponentUse(_name(_form(node, "use", 2, 2)[0]))
    if kind != "use" and len(items) > 1:
        source_map.setdefault(f"views.{_name(items[1])}", node.span)
    if kind == "form":
        name, action, field_node, state_node, buttons = _form(node, kind, 6, 6)
        fields: list[InputField] = []
        for index, item in enumerate(_form(field_node, "fields", 2)):
            data = _items(item, 3)
            control = _name(data[2])
            if control not in {"input", "textarea", "select", "checkbox"}:
                _fail("unsupported input control", data[2])
            choices: list[tuple[str, Scalar]] = []
            for choice in data[3:]:
                label, value = _form(choice, "choice", 3, 3)
                choices.append((_string(label), _scalar(value)))
            fields.append(InputField(
                _name(data[0]), _string(data[1]), cast(Control, control), tuple(choices)
            ))
            source_map[f"{path}.fields[{index}]"] = item.span
        submit, clear = _form(buttons, "buttons", 3, 3)
        return FormView(
            _name(name), _name(action), tuple(fields), _states(state_node),
            _string(submit), _string(clear),
        )
    if kind in {"list", "detail"}:
        data = _form(node, kind, 5, 7 if kind == "list" else 5)
        name, action, columns, states = data[:4]
        if kind == "detail":
            return DetailView(_name(name), _name(action), _columns(columns), _states(states))
        selection = None
        pagination = None
        for option in data[4:]:
            head = _name(_items(option, 1)[0])
            if head == "select" and selection is None:
                detail, param, column = _form(option, "select", 4, 4)
                selection = Selection(_name(detail), _name(param), _name(column))
                source_map[f"{path}.selection"] = option.span
            elif head == "paginate" and pagination is None:
                pagination = _pagination(option)
                source_map[f"{path}.pagination"] = option.span
                source_map.setdefault(f"views.{_name(name)}.pagination", option.span)
            else:
                _fail("list options are select and paginate, each at most once", option)
        return ListView(
            _name(name), _name(action), _columns(columns), _states(states), selection, pagination,
        )
    _fail("only form/list/detail/use views are supported", node, "VIEW")


def _component(node: _Node, path: str, source_map: dict[str, WebSourceSpan]) -> ComponentDef:
    name, *children = _form(node, "component", 3)
    source_map[path] = node.span
    return ComponentDef(_name(name), tuple(
        _view(child, f"{path}.children[{index}]", source_map)
        for index, child in enumerate(children)
    ))


def _canonical(node: _Node) -> str:
    if node.kind == "list":
        return "(" + " ".join(_canonical(item) for item in node.value) + ")"
    if node.kind == "string":
        return json.dumps(node.value, ensure_ascii=False)
    return str(node.value)


def _hash(parts: tuple[str, ...]) -> str:
    encoded = tuple(part.encode("utf-8") for part in parts)
    framed = b"".join(len(part).to_bytes(8, "big") + part for part in encoded)
    return hashlib.sha256(framed).hexdigest()


def _library(source: str, budget: _Budget) -> ParsedComponentLibrary:
    root = _read(source, budget)
    name, *nodes = _form(root, "webuilib1", 3)
    source_map = {"module": root.span}
    definitions = tuple(_component(node, f"definitions[{index}]", source_map)
                        for index, node in enumerate(nodes))
    names = {definition.name for definition in definitions}
    if len(names) != len(definitions):
        _fail("duplicate library component", root, "BINDING")
    # Library references are lexical: app aliases/local components cannot supply them.
    for definition in definitions:
        for child in definition.children:
            if isinstance(child, ComponentUse) and child.name not in names:
                _fail("library component references an unknown local component", root, "BINDING")
    graph = {
        definition.name: tuple(child.name for child in definition.children
                               if isinstance(child, ComponentUse))
        for definition in definitions
    }
    completed: set[str] = set()
    for start in graph:
        stack: list[tuple[str, bool]] = [(start, False)]
        active: set[str] = set()
        while stack:
            current, leaving = stack.pop()
            if leaving:
                active.remove(current)
                completed.add(current)
            elif current in active:
                _fail("cyclic library component composition", root, "BINDING")
            elif current not in completed:
                active.add(current)
                stack.append((current, True))
                stack.extend((target, False) for target in reversed(graph[current]))
    canonical = _canonical(root)
    return ParsedComponentLibrary(
        ComponentLibrary(_name(name), definitions), canonical,
        _hash(("llmlang:web-ui-source", canonical)), MappingProxyType(source_map),
    )


def parse_component_library(
    source: str, *, limits: WebSourceLimits | None = None,
) -> ParsedComponentLibrary:
    """Read a canonical library snapshot; application checking resolves view types."""
    configured = limits or WebSourceLimits()
    result = _library(source, _Budget(configured))
    if len(result.canonical_source.encode("utf-8")) > configured.max_bytes:
        raise WebSourceError("W_SOURCE_LIMIT", "canonical source byte budget exceeded")
    return result


def _parse(
    source: str, library_sources: Mapping[str, str], pure_sources: Mapping[str, str],
    limits: WebSourceLimits, program_limits: ProgramLimits,
) -> ParsedWebSource:
    budget = _Budget(limits)
    root = _read(source, budget)
    name, title, *forms = _form(root, "websrc1", 4)
    schema: Schema | None = None
    actions: list[QueryAction] = []
    views: list[ViewNode] = []
    components: list[ComponentDef] = []
    imports: list[ComponentImport] = []
    declared_libraries: list[str] = []
    pure_name: str | None = None
    source_map = {"module": root.span, "name": name.span, "title": title.span}
    for node in forms:
        data = _items(node, 1)
        kind = _name(data[0])
        if kind == "schema":
            if schema is not None:
                _fail("exactly one schema is required", node)
            source_map["schema"] = node.span
            try:
                schema = _schema(node, source_map)
            except QueryError as exc:
                raise WebSourceError("W_SOURCE_QUERY", str(exc), "schema", node.span) from exc
        elif kind == "action":
            path = f"actions[{len(actions)}]"
            try:
                actions.append(_action(node, path, source_map))
            except QueryError as exc:
                raise WebSourceError("W_SOURCE_QUERY", str(exc), path, node.span) from exc
        elif kind == "component":
            components.append(_component(node, f"components[{len(components)}]", source_map))
        elif kind == "library":
            library = _name(_form(node, kind, 2, 2)[0])
            if library in declared_libraries:
                _fail("duplicate library declaration", node, "BINDING")
            declared_libraries.append(library)
            source_map[f"libraries.{library}"] = node.span
        elif kind == "import":
            library_node, component_node, alias_node = _form(node, kind, 4, 4)
            source_map[f"imports[{len(imports)}]"] = node.span
            imports.append(ComponentImport(
                _name(library_node), _name(component_node), _name(alias_node)
            ))
        elif kind == "pure_library":
            if pure_name is not None:
                _fail("only one pure library snapshot is supported", node)
            pure_name = _name(_form(node, kind, 2, 2)[0])
            source_map["pure_library"] = node.span
        elif kind in {"form", "list", "detail", "use"}:
            views.append(_view(node, f"views[{len(views)}]", source_map))
        else:
            _fail("unsupported web module form", node)
    if schema is None:
        _fail("exactly one schema is required", root)
    if set(library_sources) != set(declared_libraries):
        _fail("library source names must exactly match declared libraries", root, "BINDING")
    if set(pure_sources) != ({pure_name} if pure_name else set()):
        _fail("pure source names must exactly match the declared pure library", root, "BINDING")
    libraries: list[ComponentLibrary] = []
    bound_sources: list[str] = []
    canonical_size = len(_canonical(root).encode("utf-8"))
    for library_name in declared_libraries:
        parsed = _library(library_sources[library_name], budget)
        if parsed.library.name != library_name:
            _fail("library source identity differs from declaration", root, "BINDING")
        libraries.append(parsed.library)
        canonical_size += len(parsed.canonical_source.encode("utf-8"))
        bound_sources.extend(("ui", library_name, parsed.canonical_source))
        source_map.update({f"libraries.{library_name}.{path}": span
                           for path, span in parsed.source_map.items()})
        for path, span in parsed.source_map.items():
            if path.startswith("views."):
                source_map.setdefault(path, span)
    pure_library = None
    if pure_name:
        pure_source = pure_sources[pure_name]
        budget.source(pure_source)
        try:
            remaining_nodes = limits.max_nodes - budget.nodes
            if remaining_nodes <= 0:
                raise WebSourceError("W_SOURCE_LIMIT", "combined source node budget exceeded")
            pure = parse_pure_source(pure_source, limits=PureSourceLimits(
                max_bytes=limits.max_bytes, max_nodes=remaining_nodes,
                max_depth=limits.max_depth, max_integer_digits=limits.max_integer_digits,
            ))
        except A1SourceError as exc:
            raise WebSourceError(
                "W_SOURCE_PURE", str(exc), "pure_library", source_map["pure_library"]
            ) from exc
        pure_library = canonical_bytes(pure.module)
        canonical_size += len(pure.canonical_source.encode("utf-8"))
        bound_sources.extend(("pure", pure_name, pure.canonical_source))
    if canonical_size > limits.max_bytes:
        raise WebSourceError("W_SOURCE_LIMIT", "combined canonical source byte budget exceeded")
    program = WebProgram(
        _name(name), _string(title), schema, tuple(actions), tuple(views),
        tuple(components), tuple(libraries), tuple(imports), pure_library,
    )
    try:
        checked = validate_program(program, limits=program_limits)
    except ProgramError as exc:
        matches = [path for path in source_map if exc.path.startswith(path)]
        nearest = max(matches, key=len) if matches else "module"
        raise WebSourceError("W_SOURCE_PROGRAM", str(exc), exc.path, source_map[nearest]) from exc
    canonical = _canonical(root)
    return ParsedWebSource(
        program, checked, canonical, _hash(("llmlang:web-source", canonical, *bound_sources)),
        checked.semantic_hash, MappingProxyType(source_map),
    )


def parse_web_source(
    source: str, *, library_sources: Mapping[str, str] | None = None,
    pure_sources: Mapping[str, str] | None = None, limits: WebSourceLimits | None = None,
    program_limits: ProgramLimits | None = None,
) -> ParsedWebSource:
    """Reconstruct and check a websrc1 program with explicit source libraries."""
    try:
        return _parse(source, library_sources or {}, pure_sources or {},
                      limits or WebSourceLimits(), program_limits or ProgramLimits())
    except QueryError as exc:
        raise WebSourceError("W_SOURCE_QUERY", str(exc)) from exc
    except RecursionError as exc:
        raise WebSourceError("W_SOURCE_LIMIT", "source/checker traversal budget exceeded") from exc


def lower_web_source(source: str, **kwargs: Any) -> WebProgram:
    return parse_web_source(source, **kwargs).program


def canonicalize_web_source(source: str, **kwargs: Any) -> str:
    return parse_web_source(source, **kwargs).canonical_source


def check_web_source_binding(source: str, offered: object, **kwargs: Any) -> bool:
    """Recompute every library and full bound program; offered hashes are ignored."""
    try:
        parsed = parse_web_source(source, **kwargs)
        if isinstance(offered, WebProgram):
            offered = validate_program(
                offered, limits=kwargs.get("program_limits") or ProgramLimits()
            ).snapshot()
        return parsed.checked.canonical_bytes == canonical_bytes(offered)
    except (WebSourceError, ProgramError, QueryError, ValueError, TypeError, RecursionError):
        return False
