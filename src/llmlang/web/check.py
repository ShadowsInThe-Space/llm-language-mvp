"""Static validation for both parsed and directly constructed web ASTs."""

import re
from typing import cast

from .model import (
    DEFAULT_LIMITS,
    UNKNOWN_SPAN,
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

RESERVED = frozenset(
    {
        "app",
        "w1",
        "store",
        "action",
        "page",
        "title",
        "input",
        "button",
        "output",
        "invoke",
        "into",
        "initial",
        "for",
        "read",
        "write",
        "Text",
    }
)
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*\Z", re.ASCII)


def _name(value: object, span: Span, limits: WebLimits) -> str:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER.fullmatch(value)
        or len(value) > min(limits.max_name_chars, 64)
        or value in RESERVED
    ):
        raise WebError("W_NAME", "Expected a non-reserved lowercase ASCII identifier.", span)
    return value


def text_size(value: object, span: Span = UNKNOWN_SPAN) -> int:
    """Validate Unicode scalar text without transforming any accepted value."""
    if not isinstance(value, str):
        raise WebError("W_TYPE", "Expected Text.", span)
    if "\0" in value:
        raise WebError("W_LEX", "Text cannot contain NUL.", span)
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as error:
        raise WebError("W_LEX", "Text must contain only Unicode scalars.", span) from error


def _text(value: object, maximum: int, code: str, span: Span) -> None:
    if text_size(value, span) > maximum:
        raise WebError(code, "Text exceeds its UTF-8 byte limit.", span)


def _tuple_of[T](value: object, kind: type[T], maximum: int, span: Span) -> tuple[T, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, kind) for item in value):
        raise WebError("W_TYPE", "Expected an immutable tuple of declared AST nodes.", span)
    if not 1 <= len(value) <= maximum:
        raise WebError("W_LIMIT", "Declaration count is outside the profile limit.", span)
    return cast(tuple[T, ...], value)


def _insert[T](mapping: dict[str, T], name: str, item: T, span: Span) -> None:
    if name in mapping:
        raise WebError("W_DUPLICATE", "Duplicate declaration in its namespace.", span)
    mapping[name] = item


def _lookup[T](mapping: dict[str, T], name: str, span: Span) -> T:
    if name not in mapping:
        raise WebError("W_UNBOUND", "Reference does not resolve to a declaration.", span)
    return mapping[name]


def _validate_input(
    node: TextInput,
    stores: dict[str, TextStore],
    limits: WebLimits,
) -> None:
    _name(node.store, node.span, limits)
    store = _lookup(stores, node.store, node.span)
    _text(node.initial, store.max_bytes, "W_INITIAL", node.span)


def _validate_button(
    node: ActionButton,
    actions: dict[str, WebAction],
    stores: dict[str, TextStore],
    widgets: dict[str, Widget],
    limits: WebLimits,
) -> None:
    _name(node.action, node.span, limits)
    _name(node.output, node.span, limits)
    action = _lookup(actions, node.action, node.span)
    output = _lookup(widgets, node.output, node.span)
    if not isinstance(output, TextOutput):
        raise WebError("W_TYPE", "Action results must target an output widget.", node.span)
    if action.effect == "read":
        if node.input is not None:
            raise WebError("W_TYPE", "A read action accepts no input argument.", node.span)
        return
    if node.input is None:
        raise WebError("W_TYPE", "A write action requires one input widget.", node.span)
    _name(node.input, node.span, limits)
    source = _lookup(widgets, node.input, node.span)
    if not isinstance(source, TextInput):
        raise WebError("W_TYPE", "Write arguments must reference an input widget.", node.span)
    if stores[source.store].max_bytes > stores[action.store].max_bytes:
        raise WebError("W_TYPE", "Input type exceeds the write action text capacity.", node.span)


def validate_app(app: WebApp, limits: WebLimits = DEFAULT_LIMITS) -> WebApp:
    """Return the unchanged app only after all w1 shape, type and binding checks."""
    if not isinstance(app, WebApp):
        raise WebError("W_TYPE", "Expected a WebApp AST.")
    if app.profile not in ("w1", "w2"):
        raise WebError("W_PROFILE", "Unsupported web language profile.", app.span)
    _name(app.name, app.span, limits)
    stores: dict[str, TextStore] = {}
    for store in _tuple_of(app.stores, TextStore, min(limits.max_stores, 8), app.span):
        _name(store.name, store.span, limits)
        if type(store.max_bytes) is not int:
            raise WebError("W_TYPE", "Text capacity must be an integer.", store.span)
        if not 1 <= store.max_bytes <= min(limits.max_text_bytes, 4096):
            raise WebError("W_LIMIT", "Text capacity is outside the profile limit.", store.span)
        _insert(stores, store.name, store, store.span)

    actions: dict[str, WebAction] = {}
    for action in _tuple_of(app.actions, WebAction, min(limits.max_actions, 16), app.span):
        _name(action.name, action.span, limits)
        _name(action.store, action.span, limits)
        if action.effect not in ("read", "write"):
            raise WebError("W_TYPE", "Unsupported action effect.", action.span)
        _lookup(stores, action.store, action.span)
        _insert(actions, action.name, action, action.span)

    if not isinstance(app.page, WebPage):
        raise WebError("W_TYPE", "Expected one WebPage AST.", app.span)
    if app.page.path != "/":
        raise WebError("W_TARGET", "w1 supports only the root page route.", app.page.span)
    _text(app.page.title, min(limits.max_label_bytes, 256), "W_LIMIT", app.page.span)
    raw_widgets = app.page.widgets
    if not isinstance(raw_widgets, tuple) or any(
        not isinstance(widget, TextInput | ActionButton | TextOutput | ClearButton)
        for widget in raw_widgets
    ):
        raise WebError("W_TYPE", "Expected an immutable tuple of widgets.", app.page.span)
    if not 1 <= len(raw_widgets) <= min(limits.max_widgets, 64):
        raise WebError("W_LIMIT", "Widget count is outside the profile limit.", app.page.span)
    widgets: dict[str, Widget] = {}
    for widget in raw_widgets:
        _name(widget.name, widget.span, limits)
        _text(widget.label, min(limits.max_label_bytes, 256), "W_LIMIT", widget.span)
        _insert(widgets, widget.name, widget, widget.span)
    for widget in raw_widgets:
        if isinstance(widget, TextInput):
            _validate_input(widget, stores, limits)
    for widget in raw_widgets:
        if isinstance(widget, ActionButton):
            _validate_button(widget, actions, stores, widgets, limits)
        elif isinstance(widget, ClearButton):
            if app.profile != "w2":
                raise WebError("W_PROFILE", "Clear requires profile w2.", widget.span)
            _name(widget.output, widget.span, limits)
            if not isinstance(_lookup(widgets, widget.output, widget.span), TextOutput):
                raise WebError("W_TYPE", "Clear must target an output widget.", widget.span)
    return app
