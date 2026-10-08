# ruff: noqa: E501
"""Emit a generic React client from checked, closed UI contracts only."""

from __future__ import annotations

import json

from .codecs import encode_value, type_descriptor
from .program import DetailView, FormView, ListView, WebProgram, validate_program


def emit_client(program: WebProgram) -> str:
    """Recheck the source program; never serialize the server snapshot to a browser."""
    checked = validate_program(program)
    used = {view.action for view in checked.expanded_views}
    actions = [{"name": action.name,
                "input": type_descriptor(action.input_codec) if action.input_codec else None,
                "output": type_descriptor(action.output_codec)}
               for action in checked.actions if action.name in used]
    views: list[dict[str, object]] = []
    for view in checked.expanded_views:
        descriptor: dict[str, object] = {
            "name": view.name, "action": view.action,
            "states": {"loading": view.states.loading, "error": view.states.error,
                       "empty": view.states.empty, "success": view.states.success},
        }
        if isinstance(view, FormView):
            contract = checked.action(view.action)
            types = {param.name: param.type for param in contract.params}
            descriptor.update({
                "kind": "form", "submitLabel": view.submit_label, "clearLabel": view.clear_label,
                "fields": [{"param": field.param, "label": field.label, "control": field.control,
                            "type": type_descriptor(types[field.param]),
                            "choices": [{"label": label, "wire": encode_value(types[field.param], value)}
                                        for label, value in field.choices]}
                           for field in view.fields],
            })
        else:
            descriptor.update({"kind": "list" if isinstance(view, ListView) else "detail",
                               "columns": [{"column": column.column, "label": column.label}
                                           for column in view.columns]})
            if isinstance(view, ListView):
                descriptor["selection"] = ({"detail": view.selection.detail,
                                            "param": view.selection.param,
                                            "column": view.selection.column}
                                           if view.selection else None)
            else:
                assert isinstance(view, DetailView)
        views.append(descriptor)
    metadata = json.dumps({"name": program.name, "title": program.title,
                           "actions": actions, "views": views},
                          ensure_ascii=True, separators=(",", ":"))
    return _RUNTIME.replace("__CLIENT_METADATA__", metadata) + _REACT


_RUNTIME = r'''// Generated general web client; source checked before emission.
import React, {useEffect, useMemo, useState} from "react";
// BEGIN GENERAL CLIENT RUNTIME
import {decodeValue, encodeValue, parseWireJson} from "./codecs";
import type {CodecType} from "./codecs";

type Row = {record: string; fields: Record<string, unknown>};
type Status = "loading" | "error" | "empty" | "success";
export type ViewState = {status: Status; value: unknown; error: string | null};
type States = Record<Status, string>;
type Action = {name: string; input: CodecType | null; output: CodecType};
type Field = {param: string; label: string; control: "input" | "select" | "checkbox";
  type: CodecType; choices: {label: string; wire: unknown}[]};
type Column = {column: string; label: string};
type View = {name: string; action: string; states: States} & (
  {kind: "form"; fields: Field[]; submitLabel: string; clearLabel: string}
  | {kind: "list"; columns: Column[]; selection: {detail: string; param: string; column: string} | null}
  | {kind: "detail"; columns: Column[]});
const SPEC: {name: string; title: string; actions: Action[]; views: View[]} = __CLIENT_METADATA__;
const ACTIONS = new Map(SPEC.actions.map(action => [action.name, action]));
const VIEWS = new Map(SPEC.views.map(view => [view.name, view]));
const MAX_BYTES = 32768;
function exactObject(value: unknown, keys: string[]): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid object");
  const object = value as Record<string, unknown>;
  if (Object.keys(object).length !== keys.length || !keys.every(key => Object.hasOwn(object, key)))
    throw new Error("Invalid fields");
  return object;
}
function formInput(view: Extract<View, {kind: "form"}>, draft: Record<string, unknown>): unknown {
  exactObject(draft, view.fields.map(field => field.param));
  const fields: Record<string, unknown> = Object.create(null);
  for (const field of view.fields) {
    const raw = draft[field.param];
    fields[field.param] = decodeValue(field.type, raw);
    if (field.control === "select" && !field.choices.some(choice => choice.wire === raw))
      throw new Error("Invalid selection");
  }
  const action = ACTIONS.get(view.action)!;
  return action.input === null ? exactObject(fields, []) : {record: action.input.kind === "record" ? action.input.name : "", fields};
}
function isEmpty(value: unknown): boolean {
  if (value === null) return true;
  const item = value as {tag?: string; list?: unknown[]};
  return item.tag === "None" || (Array.isArray(item.list) && item.list.length === 0);
}
async function responseBytes(response: Response, signal: AbortSignal): Promise<Uint8Array> {
  const length = response.headers.get("content-length");
  if (length !== null && (!/^[0-9]{1,8}$/.test(length) || Number(length) > MAX_BYTES))
    throw new Error("Response too large");
  if (response.body === null) throw new Error("Missing response");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = []; let size = 0, reads = 0;
  let abort: (() => void) | undefined;
  const aborted = new Promise<never>((_, reject) => {
    abort = () => reject(new Error("Request cancelled"));
    signal.addEventListener("abort", abort, {once: true});
    if (signal.aborted) abort();
  });
  try {
    while (true) {
      const next = await Promise.race([reader.read(), aborted]);
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_BYTES || ++reads > MAX_BYTES + 1) throw new Error("Response too large");
      chunks.push(next.value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) {bytes.set(chunk, offset); offset += chunk.byteLength;}
    return bytes;
  } finally {
    if (abort) signal.removeEventListener("abort", abort);
    void reader.cancel().catch(() => undefined); reader.releaseLock();
  }
}
async function fetchResponse(endpoint: string, options: RequestInit, fetcher: typeof fetch, signal: AbortSignal): Promise<Response> {
  let abort: (() => void) | undefined;
  const aborted = new Promise<never>((_, reject) => {
    abort = () => reject(new Error("Request cancelled"));
    signal.addEventListener("abort", abort, {once: true});
    if (signal.aborted) abort();
  });
  try { return await Promise.race([fetcher(endpoint, options), aborted]); }
  finally {if (abort) signal.removeEventListener("abort", abort);}
}
export function createClientController(endpoint = "/api/general", fetcher: typeof fetch = fetch) {
  if (typeof endpoint !== "string" || !endpoint.startsWith("/") || endpoint.startsWith("//")
    || /[\\\s#]/.test(endpoint)) throw new Error("Same-origin endpoint path required");
  const states = new Map<string, ViewState>(SPEC.views.map(view => [view.name,
    {status: "empty", value: null, error: null}]));
  const requests = new Map<string, {revision: number; abort: AbortController}>();
  const revisions = new Map<string, number>();
  const listeners = new Set<() => void>();
  let disposed = false;
  function view(name: string): View {
    const found = VIEWS.get(name);
    if (!found || disposed) throw new Error("Unknown or disposed view");
    return found;
  }
  function publish(name: string, state: ViewState): void {
    states.set(name, state); for (const listener of listeners) listener();
  }
  function invalidate(name: string): number {
    requests.get(name)?.abort.abort(); requests.delete(name);
    const revision = (revisions.get(name) ?? 0) + 1; revisions.set(name, revision); return revision;
  }
  async function perform(target: View, buildInput: () => unknown): Promise<void> {
    const revision = invalidate(target.name);
    const previous = states.get(target.name)!.value;
    const abort = new AbortController(); requests.set(target.name, {revision, abort});
    const timer = setTimeout(() => abort.abort(), 10000);
    const current = () => !disposed && revisions.get(target.name) === revision;
    publish(target.name, {status: "loading", value: previous, error: null});
    try {
      const action = ACTIONS.get(target.action)!;
      const native = buildInput();
      const input = action.input === null ? exactObject(native, []) : encodeValue(action.input, native);
      const body = JSON.stringify({action: action.name, input});
      if (new TextEncoder().encode(body).length > MAX_BYTES) throw new Error("Request too large");
      const response = await fetchResponse(endpoint, {method: "POST", credentials: "same-origin", redirect: "error",
        cache: "no-store", headers: {"Content-Type": "application/json"}, body, signal: abort.signal}, fetcher, abort.signal);
      if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(response.headers.get("content-type") ?? ""))
        throw new Error("Invalid response type");
      const wire = parseWireJson(await responseBytes(response, abort.signal));
      if (!response.ok) {
        const failure = exactObject(wire, ["error"]);
        if (typeof failure.error !== "string") throw new Error("Invalid error response");
        throw new Error("Request failed");
      }
      const value = decodeValue(action.output, wire);
      if (current()) publish(target.name, {status: isEmpty(value) ? "empty" : "success", value, error: null});
    } catch {
      if (current()) publish(target.name, {status: "error", value: previous, error: target.states.error});
    } finally {
      clearTimeout(timer); if (current()) requests.delete(target.name);
    }
  }
  return {
    getState(name: string): ViewState {view(name); return structuredClone(states.get(name)!);},
    subscribe(listener: () => void): () => void {disposed = false; listeners.add(listener); return () => {listeners.delete(listener);};},
    submitForm(name: string, draft: Record<string, unknown>): Promise<void> {
      const target = view(name); if (target.kind !== "form") throw new Error("Form view required");
      return perform(target, () => formInput(target, draft));
    },
    loadList(name: string): Promise<void> {
      const target = view(name); if (target.kind !== "list") throw new Error("List view required");
      return perform(target, () => ({}));
    },
    selectRow(name: string, row: Row): Promise<void> {
      const source = view(name);
      if (source.kind !== "list" || !source.selection) throw new Error("Selectable list required");
      const selection = source.selection; const target = view(selection.detail);
      return perform(target, () => {
        const listType = ACTIONS.get(source.action)!.output;
        if (listType.kind !== "list") throw new Error("List descriptor required");
        encodeValue(listType.elem, row);
        const inputType = ACTIONS.get(target.action)!.input;
        if (inputType?.kind !== "record") throw new Error("Detail input required");
        return {record: inputType.name, fields: {[selection.param]: row.fields[selection.column]}};
      });
    },
    clear(name: string): void {
      view(name); invalidate(name); publish(name, {status: "empty", value: null, error: null});
    },
    dispose(): void {
      for (const name of states.keys()) invalidate(name);
      disposed = true; requests.clear(); listeners.clear();
    },
  };
}
export type ClientController = ReturnType<typeof createClientController>;
// END GENERAL CLIENT RUNTIME
'''

_REACT = r'''
function display(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined) return "";
  return String(value);
}
function initialDraft(view: Extract<View, {kind: "form"}>): Record<string, unknown> {
  return Object.fromEntries(view.fields.map(field => [field.param,
    field.control === "select" ? field.choices[0].wire : field.type.kind === "bool" ? false : ""]));
}
function FormPanel({view, controller, state, ready}: {view: Extract<View, {kind: "form"}>; controller: ClientController; state: ViewState; ready: boolean}) {
  const [draft, setDraft] = useState<Record<string, unknown>>(() => initialDraft(view));
  const change = (name: string, value: unknown) => setDraft(previous => ({...previous, [name]: value}));
  const outcome = state.value as (Row & {tag?: string; value?: Row}) | null;
  const confirmed = outcome?.tag === "Some" ? outcome.value : outcome?.tag === "None" ? null : outcome;
  return <form onSubmit={event => {event.preventDefault(); if (ready) void controller.submitForm(view.name, draft);}}>
    <fieldset disabled={!ready}>
    {view.fields.map(field => {
      const id = `${SPEC.name}-${view.name}-${field.param}`;
      return <div key={field.param}><label htmlFor={id}>{field.label}</label>
        {field.control === "checkbox" ? <input id={id} name={field.param} type="checkbox"
          checked={draft[field.param] === true} onChange={event => change(field.param, event.target.checked)} />
        : field.control === "select" ? <select id={id} name={field.param}
          value={String(field.choices.findIndex(choice => choice.wire === draft[field.param]))}
          onChange={event => change(field.param, field.choices[Number(event.target.value)].wire)}>
          {field.choices.map((choice, index) => <option key={index} value={String(index)}>{choice.label}</option>)}
        </select> : field.type.kind === "text" ? <input id={id} name={field.param} type="text"
          value={String(draft[field.param])} onChange={event => change(field.param, event.target.value)} />
        : <input id={id} name={field.param} type="text" inputMode="numeric"
          value={String(draft[field.param])} onChange={event => change(field.param, event.target.value)} />}
      </div>;
    })}
    <button type="submit" disabled={!ready || state.status === "loading"}>{view.submitLabel}</button>
    <button type="button" disabled={!ready} onClick={() => controller.clear(view.name)}>{view.clearLabel}</button>
    {confirmed && <dl aria-label="Saved values">{Object.entries(confirmed.fields).map(([name, value]) =>
      <React.Fragment key={name}><dt>{view.fields.find(field => field.param === name)?.label ?? name}</dt>
        <dd>{display(value)}</dd></React.Fragment>)}</dl>}
    </fieldset>
  </form>;
}
function DataPanel({view, controller, state, ready}: {view: Exclude<View, {kind: "form"}>; controller: ClientController; state: ViewState; ready: boolean}) {
  const value = state.value as {list?: Row[]; tag?: string; value?: Row} | null;
  const rows = view.kind === "list" ? value?.list ?? [] : value?.tag === "Some" && value.value ? [value.value] : [];
  return <div>
    {view.kind === "list" && <button type="button" disabled={!ready || state.status === "loading"}
      onClick={() => {void controller.loadList(view.name);}}>Load</button>}
    <button type="button" disabled={!ready} onClick={() => controller.clear(view.name)}>Clear</button>
    {rows.length > 0 && <table><thead><tr>{view.columns.map(column => <th key={column.column} scope="col">{column.label}</th>)}
      {view.kind === "list" && view.selection && <th scope="col">Details</th>}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{view.columns.map(column =>
        <td key={column.column}>{display(row.fields[column.column])}</td>)}
        {view.kind === "list" && view.selection && <td><button type="button" disabled={!ready}
          onClick={() => {void controller.selectRow(view.name, row);}}>Select {index + 1}</button></td>}
      </tr>)}</tbody></table>}
  </div>;
}
export default function GeneralApp({endpoint = "/api/general"}: {endpoint?: string}) {
  const controller = useMemo(() => createClientController(endpoint), [endpoint]);
  const [, redraw] = useState(0);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const unsubscribe = controller.subscribe(() => redraw(value => value + 1));
    setReady(true);
    return () => {unsubscribe(); controller.dispose();};
  }, [controller]);
  return <main><h1>{SPEC.title}</h1>{SPEC.views.map(view => {
    const state = controller.getState(view.name);
    return <section key={view.name} aria-label={view.name} aria-busy={state.status === "loading"}>
      <p role={state.status === "error" ? "alert" : "status"}>{view.states[state.status]}</p>
      {view.kind === "form" ? <FormPanel view={view} controller={controller} state={state} ready={ready} />
        : <DataPanel view={view} controller={controller} state={state} ready={ready} />}
    </section>;
  })}</main>;
}
'''
