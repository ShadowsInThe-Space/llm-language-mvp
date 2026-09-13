"""Bounded S-expression reader and canonical serializer for the w1 web profile."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .check import text_size
from .check import validate_app as validate_app
from .model import (
    DEFAULT_LIMITS,
    ActionButton,
    ClearButton,
    Span,
    TextInput,
    TextOutput,
    TextStore,
    WebAction,
    WebApp,
    WebError,
    WebLimits,
    WebPage,
    Widget,
)


@dataclass(frozen=True)
class _Atom:
    value: str
    quoted: bool
    span: Span


@dataclass(frozen=True)
class _Form:
    items: tuple[_Node, ...]
    span: Span


type _Node = _Atom | _Form
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z", re.ASCII)


class _Reader:
    def __init__(self, source: str, limits: WebLimits) -> None:
        self.source = source
        self.limits = limits
        self.offset = 0
        self.nodes = 0

    def skip_space(self) -> None:
        while self.offset < len(self.source) and self.source[self.offset].isspace():
            self.offset += 1

    def read(self, depth: int = 1) -> _Node:
        self.skip_space()
        start = self.offset
        self.nodes += 1
        if depth > min(self.limits.max_depth, 32) or self.nodes > min(self.limits.max_nodes, 4096):
            raise WebError(
                "W_LIMIT", "Syntax exceeds its node or depth budget.", Span(start, start)
            )
        if start == len(self.source):
            raise WebError("W_PARSE", "Unexpected end of source.", Span(start, start))
        char = self.source[start]
        if char == "(":
            self.offset += 1
            items: list[_Node] = []
            while True:
                self.skip_space()
                if self.offset == len(self.source):
                    raise WebError("W_PARSE", "Unclosed form.", Span(self.offset, self.offset))
                if self.source[self.offset] == ")":
                    self.offset += 1
                    return _Form(tuple(items), Span(start, self.offset))
                items.append(self.read(depth + 1))
        if char == ")":
            raise WebError("W_PARSE", "Unexpected closing parenthesis.", Span(start, start + 1))
        if char == '"':
            return self.read_string()
        while self.offset < len(self.source):
            char = self.source[self.offset]
            if char.isspace() or char in '()"':
                break
            self.offset += 1
        return _Atom(self.source[start : self.offset], False, Span(start, self.offset))

    def read_string(self) -> _Atom:
        start = self.offset
        try:
            value, end = json.JSONDecoder().raw_decode(self.source, start)
        except json.JSONDecodeError as error:
            end = min(error.pos + 1, len(self.source))
            raise WebError("W_LEX", "Invalid JSON string literal.", Span(error.pos, end)) from error
        if not isinstance(value, str):
            raise WebError("W_LEX", "Expected a string literal.", Span(start, end))
        self.offset = end
        if text_size(value, Span(start, end)) > min(self.limits.max_text_bytes, 4096):
            raise WebError("W_LIMIT", "String literal exceeds its byte budget.", Span(start, end))
        return _Atom(value, True, Span(start, end))


def _symbol(node: _Node) -> str:
    if not isinstance(node, _Atom) or node.quoted:
        raise WebError("W_PARSE", "Expected an unquoted symbol.", node.span)
    return node.value


def _string(node: _Node) -> str:
    if not isinstance(node, _Atom) or not node.quoted:
        raise WebError("W_PARSE", "Expected a quoted string.", node.span)
    return node.value


def _head(node: _Node) -> str:
    if not isinstance(node, _Form) or not node.items:
        raise WebError("W_PARSE", "Expected a nonempty declaration form.", node.span)
    return _symbol(node.items[0])


def _form(node: _Node, name: str, minimum: int, maximum: int | None = None) -> _Form:
    if not isinstance(node, _Form) or _head(node) != name:
        raise WebError("W_PARSE", f"Expected a {name} form.", node.span)
    upper = minimum if maximum is None else maximum
    if not minimum <= len(node.items) <= upper:
        raise WebError("W_PARSE", f"Unexpected number of elements in {name}.", node.span)
    return node


def _store(node: _Node) -> TextStore:
    form = _form(node, "store", 3)
    capacity = _form(form.items[2], "Text", 2)
    value = _symbol(capacity.items[1])
    if not _DECIMAL.fullmatch(value):
        raise WebError(
            "W_PARSE", "Expected a canonical nonnegative decimal.", capacity.items[1].span
        )
    if len(value) > 4:
        raise WebError(
            "W_LIMIT", "Text capacity exceeds the profile limit.", capacity.items[1].span
        )
    return TextStore(_symbol(form.items[1]), int(value), form.span)


def _action(node: _Node) -> WebAction:
    form = _form(node, "action", 3)
    effect = _head(form.items[2])
    if effect not in ("read", "write"):
        raise WebError("W_PARSE", "Expected a read or write action.", form.items[2].span)
    target = _form(form.items[2], effect, 2)
    if effect == "read":
        return WebAction(_symbol(form.items[1]), "read", _symbol(target.items[1]), form.span)
    return WebAction(_symbol(form.items[1]), "write", _symbol(target.items[1]), form.span)


def _widget(node: _Node) -> Widget:
    kind = _head(node)
    if kind == "clear":
        form = _form(node, "clear", 4)
        target = _form(form.items[3], "output", 2)
        return ClearButton(
            _symbol(form.items[1]), _string(form.items[2]), _symbol(target.items[1]), form.span
        )
    if kind == "input":
        form = _form(node, "input", 5)
        target = _form(form.items[3], "for", 2)
        initial = _form(form.items[4], "initial", 2)
        return TextInput(
            _symbol(form.items[1]),
            _string(form.items[2]),
            _symbol(target.items[1]),
            _string(initial.items[1]),
            form.span,
        )
    if kind == "output":
        form = _form(node, "output", 3)
        return TextOutput(_symbol(form.items[1]), _string(form.items[2]), form.span)
    if kind == "button":
        form = _form(node, "button", 5)
        invoke = _form(form.items[3], "invoke", 2, 3)
        target = _form(form.items[4], "into", 2)
        input_name = None
        if len(invoke.items) == 3:
            argument = _form(invoke.items[2], "input", 2)
            input_name = _symbol(argument.items[1])
        return ActionButton(
            _symbol(form.items[1]),
            _string(form.items[2]),
            _symbol(invoke.items[1]),
            input_name,
            _symbol(target.items[1]),
            form.span,
        )
    raise WebError("W_PARSE", "Unknown UI widget form.", node.span)


def _app(node: _Node) -> WebApp:
    form = _form(node, "app", 6, 4096)
    profile = _symbol(form.items[1])
    if profile not in ("w1", "w2"):
        raise WebError("W_PROFILE", "Unsupported web language profile.", form.items[1].span)
    stores: list[TextStore] = []
    actions: list[WebAction] = []
    declarations = form.items[3:]
    for declaration in declarations[:-1]:
        kind = _head(declaration)
        if kind == "store" and not actions:
            stores.append(_store(declaration))
        elif kind == "action":
            actions.append(_action(declaration))
        else:
            raise WebError(
                "W_PARSE", "Expected stores, then actions, then one page.", declaration.span
            )
    page_form = _form(declarations[-1], "page", 4, 4096)
    title = _form(page_form.items[2], "title", 2)
    page = WebPage(
        _string(page_form.items[1]),
        _string(title.items[1]),
        tuple(_widget(widget) for widget in page_form.items[3:]),
        page_form.span,
    )
    return WebApp(
        "w2" if profile == "w2" else "w1",
        _symbol(form.items[2]),
        tuple(stores),
        tuple(actions),
        page,
        form.span,
    )


def parse_app(source: str, limits: WebLimits = DEFAULT_LIMITS) -> WebApp:
    """Parse untrusted w1 source and enforce all static rules before returning."""
    if not isinstance(source, str):
        raise WebError("W_LEX", "Source must be UTF-8 text.")
    if len(source) > limits.max_source_bytes:
        raise WebError("W_LIMIT", "Source exceeds its UTF-8 byte budget.", Span(0, len(source)))
    try:
        size = len(source.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as error:
        raise WebError(
            "W_LEX", "Source must contain Unicode scalars.", Span(error.start, error.end)
        ) from error
    if size > limits.max_source_bytes:
        raise WebError("W_LIMIT", "Source exceeds its UTF-8 byte budget.", Span(0, len(source)))
    if "\0" in source:
        position = source.index("\0")
        raise WebError("W_LEX", "Source cannot contain NUL.", Span(position, position + 1))
    reader = _Reader(source, limits)
    node = reader.read()
    reader.skip_space()
    if reader.offset != len(source):
        raise WebError(
            "W_PARSE", "Expected exactly one app form.", Span(reader.offset, len(source))
        )
    return validate_app(_app(node), limits)


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _canonical_widget(widget: Widget) -> str:
    if isinstance(widget, ClearButton):
        return f"(clear {widget.name} {_quoted(widget.label)} (output {widget.output}))"
    if isinstance(widget, TextInput):
        return (
            f"(input {widget.name} {_quoted(widget.label)} (for {widget.store}) "
            f"(initial {_quoted(widget.initial)}))"
        )
    if isinstance(widget, TextOutput):
        return f"(output {widget.name} {_quoted(widget.label)})"
    argument = "" if widget.input is None else f" (input {widget.input})"
    return (
        f"(button {widget.name} {_quoted(widget.label)} "
        f"(invoke {widget.action}{argument}) (into {widget.output}))"
    )


def canonical_app(app: WebApp) -> str:
    validate_app(app)
    stores = " ".join(f"(store {store.name} (Text {store.max_bytes}))" for store in app.stores)
    actions = " ".join(
        f"(action {action.name} ({action.effect} {action.store}))" for action in app.actions
    )
    widgets = " ".join(_canonical_widget(widget) for widget in app.page.widgets)
    page = f"(page {_quoted(app.page.path)} (title {_quoted(app.page.title)}) {widgets})"
    return f"(app {app.profile} {app.name} {stores} {actions} {page})"
