"""Behavioral tests for the frozen w1 language and its trust boundary."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from llmlang.web.model import (
    DEFAULT_LIMITS,
    ActionButton,
    TextInput,
    TextStore,
    WebError,
    WebLimits,
)
from llmlang.web.parser import canonical_app, parse_app, validate_app

HELLO = """(app w1 hello_demo
  (store greeting (Text 4096))
  (action save_greeting (write greeting))
  (action load_greeting (read greeting))
  (page "/" (title "AI-Demo")
    (input message "Neuer Text" (for greeting) (initial "Hello new AI World"))
    (button save "Speichern" (invoke save_greeting (input message)) (into result))
    (button show "Anzeigen" (invoke load_greeting) (into result))
    (output result "Gespeicherter Text")))"""


def assert_error(source: str, code: str, limits: WebLimits = DEFAULT_LIMITS) -> WebError:
    with pytest.raises(WebError) as raised:
        parse_app(source, limits)
    assert raised.value.code == code
    assert 0 <= raised.value.span.start <= raised.value.span.end <= len(source)
    diagnostic = raised.value.to_dict()
    assert diagnostic["code"] == code
    assert isinstance(diagnostic["message"], str)
    return raised.value


def test_complete_agent_style_app_has_typed_bindings_and_ui_initial_only() -> None:
    app = parse_app(HELLO)
    assert app.name == "hello_demo"
    assert app.stores == (TextStore("greeting", 4096),)
    assert not hasattr(app.stores[0], "default")
    text_input = app.page.widgets[0]
    assert isinstance(text_input, TextInput)
    assert text_input.initial == "Hello new AI World"
    button = app.page.widgets[1]
    assert isinstance(button, ActionButton)
    assert button.input == "message"
    assert button.action == "save_greeting"
    assert button.output == "result"
    assert validate_app(app) is app
    with pytest.raises(FrozenInstanceError):
        app.name = "changed"  # type: ignore[misc]


def test_canonical_source_preserves_order_but_ignores_whitespace_and_escape_spelling() -> None:
    app = parse_app(HELLO)
    canonical = canonical_app(app)
    assert "\n" not in canonical
    assert not canonical.endswith(" ")
    assert parse_app(canonical) == app
    escaped = HELLO.replace("AI-Demo", r"\u0041I-Demo")
    assert canonical_app(parse_app(escaped)) == canonical
    assert canonical.index("(button save ") < canonical.index("(output result ")


def test_surrogate_pair_escape_decodes_to_one_scalar() -> None:
    escaped = HELLO.replace("Hello new AI World", r"\ud83d\ude80")
    app = parse_app(escaped)
    assert isinstance(app.page.widgets[0], TextInput)
    assert app.page.widgets[0].initial == "🚀"
    assert "🚀" in canonical_app(app)


@pytest.mark.parametrize("text", ["", "  ", "🚀", "a\r\nb\nc\rd", "</script><img src=x>", '"\\'])
def test_text_is_exact_data(text: str) -> None:
    source = HELLO.replace('"Hello new AI World"', json.dumps(text))
    app = parse_app(source)
    assert isinstance(app.page.widgets[0], TextInput)
    assert app.page.widgets[0].initial == text
    assert parse_app(canonical_app(app)) == app


@given(st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\0"), max_size=64))
@settings(max_examples=60, deadline=None)
def test_arbitrary_scalar_text_roundtrips(text: str) -> None:
    app = parse_app(HELLO.replace('"Hello new AI World"', json.dumps(text)))
    reparsed = parse_app(canonical_app(app))
    assert reparsed == app
    assert isinstance(reparsed.page.widgets[0], TextInput)
    assert reparsed.page.widgets[0].initial == text


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ("w1", "w9", "W_PROFILE"),
        ("hello_demo", "Hello", "W_NAME"),
        ("hello_demo", "app", "W_NAME"),
        ("hello_demo", "a" * 65, "W_NAME"),
        ("Text 4096", "Text 0", "W_LIMIT"),
        ("Text 4096", "Text 4097", "W_LIMIT"),
        ("Text 4096", "Text 004", "W_PARSE"),
        ("Text 4096", "Bool 4096", "W_PARSE"),
        ("(for greeting)", "(for missing)", "W_UNBOUND"),
        ("(write greeting)", "(write missing)", "W_UNBOUND"),
        ("(invoke load_greeting)", "(invoke absent)", "W_UNBOUND"),
        ("(into result)", "(into missing)", "W_UNBOUND"),
        ("(into result)", "(into message)", "W_TYPE"),
        ("(input message))", "(input result))", "W_TYPE"),
        ("(invoke load_greeting)", "(invoke load_greeting (input message))", "W_TYPE"),
        ("(invoke save_greeting (input message))", "(invoke save_greeting)", "W_TYPE"),
        ("(write greeting)", "(delete greeting)", "W_PARSE"),
        ('(page "/"', '(page "/other"', "W_TARGET"),
        ('(title "AI-Demo")', '(title "' + "x" * 257 + '")', "W_LIMIT"),
        ('(initial "Hello new AI World")', '(default "Hello new AI World")', "W_PARSE"),
    ],
)
def test_bad_programs_are_rejected(old: str, new: str, code: str) -> None:
    assert old in HELLO
    assert_error(HELLO.replace(old, new), code)


@pytest.mark.parametrize(
    "source",
    ["", "()", "(app)", HELLO + " ()", HELLO[:-1], HELLO + ")", HELLO + ";comment"],
)
def test_malformed_grammar_is_rejected(source: str) -> None:
    with pytest.raises(WebError) as raised:
        parse_app(source)
    assert raised.value.code in {"W_PARSE", "W_LEX"}


@pytest.mark.parametrize("bad", [r"\ud800", r"\udfff", r"\u0000", r"\q", "\x00", "\ud800"])
def test_invalid_string_scalars_and_escapes_are_lexical_errors(bad: str) -> None:
    assert_error(HELLO.replace("Hello new AI World", bad), "W_LEX")


def test_utf8_limit_is_bytes_and_empty_string_is_valid() -> None:
    base = HELLO.replace("Text 4096", "Text 4")
    parse_app(base.replace("Hello new AI World", "🚀"))
    parse_app(base.replace("Hello new AI World", ""))
    assert_error(base.replace("Hello new AI World", "🚀a"), "W_INITIAL")


@pytest.mark.parametrize("kind", ["store", "action", "widget"])
def test_duplicate_names_are_rejected_per_namespace(kind: str) -> None:
    if kind == "store":
        source = HELLO.replace("(store greeting (Text 4096))", "(store greeting (Text 4096))" * 2)
    elif kind == "action":
        source = HELLO.replace("load_greeting", "save_greeting")
    else:
        source = HELLO.replace("(output result ", "(output message ")
    assert_error(source, "W_DUPLICATE")


def test_multiple_stores_actions_and_outputs_are_resolved_independently() -> None:
    source = (
        HELLO.replace(
            "(store greeting (Text 4096))",
            """(store greeting (Text 4096))
        (store note (Text 32))""",
        )
        .replace(
            "(action save_greeting",
            """(action save_note (write note))
        (action read_note (read note)) (action save_greeting""",
        )
        .replace(
            '(output result "Gespeicherter Text")',
            """(output result "Gespeicherter Text")
        (input note_editor "Notiz" (for note) (initial ""))
        (button note_save "Notiz speichern" (invoke save_note (input note_editor)) (into note_view))
        (button note_load "Notiz laden" (invoke read_note) (into note_view))
        (output note_view "Notiz")""",
        )
    )
    app = parse_app(source)
    assert [store.name for store in app.stores] == ["greeting", "note"]
    assert len(app.actions) == 4
    assert len(app.page.widgets) == 8
    assert parse_app(canonical_app(app)) == app
    assert_error(
        source.replace(
            "(invoke save_note (input note_editor))", "(invoke save_note (input message))"
        ),
        "W_TYPE",
    )


def test_declaration_order_is_checked_but_widget_forward_references_are_allowed() -> None:
    parse_app(HELLO)
    store = "(store greeting (Text 4096))"
    assert_error(HELLO.replace(store, "").replace('(page "/"', store + '(page "/"'), "W_PARSE")


@pytest.mark.parametrize(
    "limits",
    [WebLimits(max_source_bytes=10), WebLimits(max_nodes=5), WebLimits(max_depth=2)],
)
def test_structural_budgets_fail_with_diagnostics(limits: WebLimits) -> None:
    assert_error(HELLO, "W_LIMIT", limits)


def test_deep_untrusted_source_fails_before_python_recursion_limit() -> None:
    assert_error("(" * 2000 + ")" * 2000, "W_LIMIT")


@given(st.text(max_size=256))
@settings(max_examples=100, deadline=None)
def test_arbitrary_malformed_sources_have_structured_errors(source: str) -> None:
    try:
        app = parse_app(source)
    except WebError as error:
        assert 0 <= error.span.start <= error.span.end <= len(source)
        assert error.code.startswith("W_")
    else:
        assert parse_app(canonical_app(app)) == app


@pytest.mark.parametrize("count", [65, 80])
def test_excess_widgets_are_resource_errors(count: int) -> None:
    widgets = " ".join(f'(output value_{index} "Text")' for index in range(count))
    source = (
        "(app w1 notes (store memo (Text 32)) (action read_memo (read memo)) "
        f'(page "/" (title "Notes") {widgets}))'
    )
    assert_error(source, "W_LIMIT")


def test_eight_stores_allowed_ninth_rejected() -> None:
    stores = " ".join(f"(store note_{index} (Text 32))" for index in range(8))
    source = (
        f"(app w1 notes {stores} (action read_note (read note_0)) "
        '(page "/" (title "Notes") (output value "Text")))'
    )
    assert len(parse_app(source).stores) == 8
    assert_error(source.replace(stores, stores + " (store note_8 (Text 32))"), "W_LIMIT")


def test_direct_ast_cannot_bypass_typing_or_text_checks() -> None:
    app = parse_app(HELLO)
    with pytest.raises(WebError) as bad_limit:
        validate_app(replace(app, stores=(TextStore("greeting", True),)))
    assert bad_limit.value.code == "W_TYPE"
    bad_input = replace(app.page.widgets[0], initial="\ud800")
    with pytest.raises(WebError) as invalid_scalar:
        validate_app(
            replace(app, page=replace(app.page, widgets=(bad_input, *app.page.widgets[1:])))
        )
    assert invalid_scalar.value.code == "W_LEX"
    with pytest.raises(WebError):
        canonical_app(replace(app, name="../outside"))
