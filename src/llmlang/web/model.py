"""Immutable source-language data and bounded compiler diagnostics for w1."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Span:
    start: int = 0
    end: int = 0


UNKNOWN_SPAN = Span()


class WebError(Exception):
    def __init__(self, code: str, message: str, span: Span = UNKNOWN_SPAN) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.span = span

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "span": {"start": self.span.start, "end": self.span.end},
        }


@dataclass(frozen=True)
class WebLimits:
    max_source_bytes: int = 131072
    max_nodes: int = 4096
    max_depth: int = 32
    max_stores: int = 8
    max_actions: int = 16
    max_widgets: int = 64
    max_text_bytes: int = 4096
    max_label_bytes: int = 256
    max_name_chars: int = 64


DEFAULT_LIMITS = WebLimits()


@dataclass(frozen=True)
class TextStore:
    name: str
    max_bytes: int
    span: Span = field(default=Span(), compare=False, repr=False)


@dataclass(frozen=True)
class WebAction:
    name: str
    effect: Literal["read", "write"]
    store: str
    span: Span = field(default=Span(), compare=False, repr=False)


@dataclass(frozen=True)
class TextInput:
    name: str
    label: str
    store: str
    initial: str
    span: Span = field(default=Span(), compare=False, repr=False)


@dataclass(frozen=True)
class ActionButton:
    name: str
    label: str
    action: str
    input: str | None
    output: str
    span: Span = field(default=Span(), compare=False, repr=False)


@dataclass(frozen=True)
class TextOutput:
    name: str
    label: str
    span: Span = field(default=Span(), compare=False, repr=False)


@dataclass(frozen=True)
class ClearButton:
    name: str
    label: str
    output: str
    span: Span = field(default=Span(), compare=False, repr=False)


type Widget = TextInput | ActionButton | TextOutput | ClearButton


@dataclass(frozen=True)
class WebPage:
    path: str
    title: str
    widgets: tuple[Widget, ...]
    span: Span = field(default=Span(), compare=False, repr=False)


@dataclass(frozen=True)
class WebApp:
    profile: Literal["w1", "w2"]
    name: str
    stores: tuple[TextStore, ...]
    actions: tuple[WebAction, ...]
    page: WebPage
    span: Span = field(default=Span(), compare=False, repr=False)
