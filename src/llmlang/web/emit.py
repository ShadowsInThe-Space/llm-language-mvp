"""Compile checked w1 widgets into concrete React and Vinext modules."""

import json
import re
from importlib.resources import files
from typing import assert_never

from .model import ActionButton, ClearButton, TextInput, TextOutput, WebApp
from .parser import validate_app
from .server import emit_server


def _literal(value: str) -> str:
    """JSON strings are JS expressions; keep HTML delimiters out of generated source."""
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _template(name: str, **values: str) -> str:
    source = files("llmlang.web").joinpath("templates", name).read_text(encoding="utf-8")
    # One pass: source literals containing marker text are never substituted again.
    return re.sub(r"@@([A-Z_]+)@@", lambda match: values[match.group(1)], source)


def _input(widget: TextInput, index: int, max_bytes: int) -> str:
    name = _literal(widget.name)
    counter_id = _literal(f"w1-count-{widget.name}")
    return f'''          <div className="w1-input-group">
            <div className="w1-field-heading">
              <label htmlFor={{{name}}}>{{{_literal(widget.label)}}}</label>
              <span id={{{counter_id}}} className="w1-counter">
                {{byteLength(input{index})}} / {max_bytes} Bytes
              </span>
            </div>
            <Textarea
              id={{{name}}}
              value={{input{index}}}
              disabled={{!clientReady}}
              onChange={{(event) => setInput{index}(event.target.value)}}
              aria-describedby={{{counter_id}}}
              aria-invalid={{!validText(input{index}, {max_bytes})}}
              className="w1-textarea"
              spellCheck={{false}}
            />
          </div>'''


def _output(widget: TextOutput, index: int) -> str:
    name = _literal(widget.name)
    label_id = _literal(f"w1-label-{widget.name}")
    return f'''          <section className="w1-output-group" aria-labelledby={{{label_id}}}>
            <h2 id={{{label_id}}}>{{{_literal(widget.label)}}}</h2>
            <div className="w1-output-body" aria-live="polite" aria-atomic="true">
              <pre id={{{name}}} className="w1-output-value">
                {{output{index}?.found === true ? output{index}.value : ""}}
              </pre>
              {{output{index} === null && <p className="w1-placeholder">Noch nichts geladen.</p>}}
              {{output{index}?.found === false && (
                <p className="w1-placeholder">Noch nichts gespeichert.</p>
              )}}
              {{output{index}?.found === true && output{index}.value === "" && (
                <p className="w1-placeholder">Leerer Text gespeichert.</p>
              )}}
              {{output{index} !== null && (
                <p className="w1-receipt">{{output{index}.receipt}}</p>
              )}}
            </div>
          </section>'''


def _button(
    widget: ActionButton,
    app: WebApp,
    inputs: dict[str, int],
    outputs: dict[str, int],
) -> str:
    action = next(action for action in app.actions if action.name == widget.action)
    store = next(store for store in app.stores if store.name == action.store)
    value = "null" if widget.input is None else f"input{inputs[widget.input]}"
    invoke = (
        f"invoke({_literal(store.name)}, {_literal(action.effect)}, {value}, "
        f"{store.max_bytes}, setOutput{outputs[widget.output]})"
    )
    variant = "default" if action.effect == "write" else "outline"
    if app.profile == "w2" and action.effect == "read":
        invoke = (
            f"openPicker({_literal(store.name)}, {store.max_bytes}, "
            f"setOutput{outputs[widget.output]}, {_literal(widget.name)})"
        )
    button = f'''          <Button
            id={{{_literal(widget.name)}}}
            type="button"
            variant="{variant}"
            className="w1-action w1-{action.effect}"
            disabled={{!clientReady || busy}}
            onClick={{() => void {invoke}}}
          >
            {{{_literal(widget.label)}}}
          </Button>'''
    if app.profile == "w2" and action.effect == "read":
        return button + "\n" + _template("history-picker.tsx", BUTTON=_literal(widget.name))
    return button


def _clear(widget: ClearButton, index: int) -> str:
    return f'''          <Button
            id={{{_literal(widget.name)}}} type="button" variant="outline"
            className="w1-action w1-read" disabled={{!clientReady || busy}}
            onClick={{() => clearOutput(setOutput{index})}}
          >{{{_literal(widget.label)}}}</Button>'''


def _page(app: WebApp) -> str:
    input_widgets = [widget for widget in app.page.widgets if isinstance(widget, TextInput)]
    output_widgets = [widget for widget in app.page.widgets if isinstance(widget, TextOutput)]
    inputs = {widget.name: index for index, widget in enumerate(input_widgets)}
    outputs = {widget.name: index for index, widget in enumerate(output_widgets)}
    stores = {store.name: store for store in app.stores}
    states = [
        f"  const [input{index}, setInput{index}] = useState({_literal(widget.initial)});"
        for index, widget in enumerate(input_widgets)
    ]
    states.extend(
        f"  const [output{index}, setOutput{index}] = useState<ConfirmedValue | null>(null);"
        for index in range(len(output_widgets))
    )
    widgets: list[str] = []
    for widget in app.page.widgets:
        if isinstance(widget, TextInput):
            widgets.append(_input(widget, inputs[widget.name], stores[widget.store].max_bytes))
        elif isinstance(widget, ActionButton):
            widgets.append(_button(widget, app, inputs, outputs))
        elif isinstance(widget, TextOutput):
            widgets.append(_output(widget, outputs[widget.name]))
        elif isinstance(widget, ClearButton):
            widgets.append(_clear(widget, outputs[widget.output]))
        else:
            assert_never(widget)
    support = files("llmlang.web").joinpath("templates", "client-page.tsx").read_text()
    return _template(
        "history-page.tsx" if app.profile == "w2" else "client-page.tsx",
        TITLE=_literal(app.page.title),
        STATES="\n".join(states),
        WIDGETS="\n".join(widgets),
        SUPPORT=support.split("export default function Page()", 1)[0],
    )


def emit_app(app: WebApp) -> dict[str, str]:
    """Validate public ASTs and emit source-derived frontend plus server artifacts."""
    validate_app(app)
    frontend = {
        "app/page.tsx": _page(app),
        "app/layout.tsx": _template("layout.tsx", TITLE=_literal(app.page.title)),
        "app/globals.css": _template("style.css"),
    }
    server = emit_server(app)
    if frontend.keys() & server.keys():
        raise ValueError("Server emitter attempted to replace a frontend artifact")
    return frontend | server
