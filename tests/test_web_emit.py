"""Behavioral boundaries of the w1 React/Vinext emitter."""

import re
from dataclasses import replace
from unittest.mock import patch

import pytest

from llmlang.web.emit import emit_app
from llmlang.web.model import WebError
from llmlang.web.parser import parse_app

SOURCE = '''(app w1 hello_demo
  (store greeting (Text 4096))
  (action save_greeting (write greeting))
  (action load_greeting (read greeting))
  (page "/" (title "Unsere erste AI-Webanwendung")
    (input message "Neuer Text" (for greeting) (initial "Hello new AI World"))
    (button save "Speichern" (invoke save_greeting (input message)) (into result))
    (button show "Anzeigen" (invoke load_greeting) (into result))
    (output result "Gespeicherter Text")))'''


def test_emits_source_defined_page_metadata_and_server_files() -> None:
    app = parse_app(SOURCE)
    with patch("llmlang.web.emit.emit_server", return_value={"db/schema.ts": "schema"}):
        files = emit_app(app)
    assert set(files) == {"app/page.tsx", "app/layout.tsx", "app/globals.css", "db/schema.ts"}
    assert files["db/schema.ts"] == "schema"
    assert '"Unsere erste AI-Webanwendung"' in files["app/page.tsx"]
    assert 'title: "Unsere erste AI-Webanwendung"' in files["app/layout.tsx"]
    assert "Hello new AI World" in files["app/page.tsx"]
    assert "@/components/ui/button" in files["app/page.tsx"]
    assert "@/components/ui/textarea" in files["app/page.tsx"]


def test_widget_order_and_action_targets_follow_source() -> None:
    files = emit_app(parse_app(SOURCE))
    page = files["app/page.tsx"]
    assert page.index('id={"message"}') < page.index('id={"save"}')
    assert page.index('id={"save"}') < page.index('id={"show"}')
    assert page.index('id={"show"}') < page.index('id={"result"}')
    assert 'invoke("greeting", "write", input0, 4096, setOutput0)' in page
    assert 'invoke("greeting", "read", null, 4096, setOutput0)' in page


def test_compilation_is_deterministic_across_equivalent_whitespace() -> None:
    assert emit_app(parse_app(SOURCE)) == emit_app(parse_app(SOURCE.replace("\n", " ")))


def test_second_store_generates_independent_input_output_and_bindings() -> None:
    source = SOURCE.replace(
        '(action save_greeting',
        '(store note (Text 80)) (action save_note (write note)) (action save_greeting',
    ).replace(
        '(output result "Gespeicherter Text")',
        '(output result "Gespeicherter Text")'
        ' (input note_input "Notiz" (for note) (initial "Zweiter Text"))'
        ' (button note_save "Notiz speichern"'
        ' (invoke save_note (input note_input)) (into note_output))'
        ' (output note_output "Gespeicherte Notiz")',
    )
    page = emit_app(parse_app(source))["app/page.tsx"]
    assert 'invoke("note", "write", input1, 80, setOutput1)' in page
    assert 'id={"note_input"}' in page
    assert 'id={"note_output"}' in page
    assert 'useState("Zweiter Text")' in page


def test_hostile_source_text_is_data_in_generated_tsx() -> None:
    text = '</script><img src=x onerror=alert(1)>'
    page = emit_app(parse_app(SOURCE.replace("Hello new AI World", text)))["app/page.tsx"]
    assert text not in page
    assert "\\u003c/script\\u003e" in page
    assert "dangerouslySetInnerHTML" not in page
    assert ".innerHTML" not in page
    assert "localStorage" not in page
    assert "sessionStorage" not in page


def test_emitter_rejects_unvalidated_public_ast() -> None:
    app = parse_app(SOURCE)
    malformed = replace(app, stores=(replace(app.stores[0], max_bytes=0),))
    with pytest.raises(WebError):
        emit_app(malformed)


def test_source_marker_text_is_preserved_without_recursive_expansion() -> None:
    page = emit_app(parse_app(SOURCE.replace("Hello new AI World", "@@TITLE@@")))[
        "app/page.tsx"
    ]
    assert 'useState("@@TITLE@@")' in page


def test_server_cannot_silently_replace_compiled_frontend() -> None:
    with patch("llmlang.web.emit.emit_server", return_value={"app/page.tsx": "replacement"}):
        with pytest.raises(ValueError, match="frontend artifact"):
            emit_app(parse_app(SOURCE))


def test_ssr_controls_remain_disabled_until_client_hydration() -> None:
    page = emit_app(parse_app(SOURCE))["app/page.tsx"]
    textareas = re.findall(r"<Textarea\b[\s\S]*?/>", page)
    buttons = re.findall(r"<Button\b[\s\S]*?</Button>", page)
    assert textareas and buttons
    assert all("disabled={!clientReady}" in textarea for textarea in textareas)
    assert all("disabled={!clientReady || busy}" in button for button in buttons)
    assert "useSyncExternalStore" in page
    assert "const serverSnapshot = () => false;" in page
    assert "const clientSnapshot = () => true;" in page
