"""Emit a capability-injected D1 dispatcher for validated general web programs."""

from __future__ import annotations

import json

from .codecs import type_descriptor
from .program import WebProgram, validate_program
from .queries import Param


def emit_server(program: WebProgram) -> str:
    """Validate every program before emitting static SQL and closed action metadata."""
    checked = validate_program(program)
    actions: list[dict[str, object]] = []
    uses_pure = False
    for action in checked.actions:
        compiled = action.compiled
        uses_pure = uses_pure or bool(action.transforms)
        bindings: list[dict[str, object]] = []
        for binding in compiled.bindings:
            value: dict[str, object] = (
                {"param": binding.value.name}
                if isinstance(binding.value, Param)
                else {"value": binding.value}
            )
            bindings.append({
                **value, "type": type_descriptor(binding.type),
                "incrementable": binding.incrementable,
            })
        actions.append({
            "name": action.name,
            "authorization": action.authorization,
            "sql": compiled.sql,
            "bindings": bindings,
            "transforms": [{"param": transform.param, "function": transform.function,
                            "args": list(transform.args)} for transform in action.transforms],
            "input": type_descriptor(action.input_codec) if action.input_codec else None,
            "output": type_descriptor(action.output_codec),
            "columns": [{"name": column.name, "type": type_descriptor(column.type)}
                        for column in compiled.result.columns],
            "cardinality": compiled.result.cardinality,
            "maxRows": compiled.result.max_rows,
        })
    serialized = json.dumps(actions, ensure_ascii=True, separators=(",", ":"))
    pure_import = 'import {invokePure} from "./a1-pure";' if uses_pure else ""
    transform_function = _PURE_TRANSFORMS if uses_pure else _NO_TRANSFORMS
    return (_RUNTIME.replace("__PURE_IMPORT__", pure_import)
            .replace("__TRANSFORM_FUNCTION__", transform_function)
            .replace("__ACTION_METADATA__", serialized))


_NO_TRANSFORMS = r'''function transformParams(
  _action: Action, original: Record<string, unknown>,
): Record<string, unknown> { return original; }'''

_PURE_TRANSFORMS = r'''function transformParams(
  action: Action, fields: Record<string, unknown>,
): Record<string, unknown> {
  const original: Record<string, unknown> = Object.freeze(
    Object.assign(Object.create(null), fields),
  );
  const replacements = action.transforms.map(transform => ({
    param: transform.param,
    value: invokePure(transform.function, transform.args.map(name => original[name])),
  }));
  const result: Record<string, unknown> = Object.assign(Object.create(null), original);
  for (const replacement of replacements) result[replacement.param] = replacement.value;
  return result;
}'''


_RUNTIME = r'''// General web server: generated only after validate_program succeeds.
import {decodeValue, encodeJson, encodeValue, parseWireJson} from "./codecs";
import type {CodecType} from "./codecs";
__PURE_IMPORT__

type Requirement = "public" | "authenticated" | "admin";
type Binding = {type: CodecType; param?: string; value?: unknown; incrementable: boolean};
type Column = {name: string; type: CodecType};
type Transform = {param: string; function: string; args: string[]};
type Action = {
  name: string; authorization: Requirement; sql: string; bindings: Binding[];
  input: CodecType | null; output: CodecType; columns: Column[]; transforms: Transform[];
  cardinality: "one" | "optional" | "bounded" | "conditional"; maxRows: number;
};
export interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  all(): Promise<{success: boolean; results: unknown[]}>;
}
export interface D1Database { prepare(sql: string): D1Statement; }
export interface HostOptions {
  allowedOrigin: string;
  authorize?: (action: string, request: Request, requirement: Requirement)
    => boolean | Promise<boolean>;
  maxRequestBytes?: number;
  bodyTimeoutMs?: number;
}
const ACTIONS: readonly Action[] = __ACTION_METADATA__;
const MAX_SAFE = 9007199254740991;
const ACTION_MAP = new Map(ACTIONS.map(action => [action.name, action]));
class BoundaryError extends Error {
  status: number;
  label: string;
  constructor(status: number, label: string) {
    super(label); this.status = status; this.label = label;
  }
}
function object(value: unknown, names: string[]): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid object");
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== names.length || !names.every(name => Object.hasOwn(row, name)))
    throw new Error("Invalid fields");
  return row;
}
async function readBounded(
  request: Request, limit: number, timeoutMs: number,
): Promise<Uint8Array> {
  const length = request.headers.get("content-length");
  if (length !== null) {
    if (!/^[0-9]{1,8}$/.test(length)) throw new BoundaryError(400, "InvalidRequest");
    if (Number(length) > limit) throw new BoundaryError(413, "RequestTooLarge");
  }
  if (request.body === null) throw new BoundaryError(400, "InvalidRequest");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0, reads = 0, timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new BoundaryError(408, "RequestTimeout")), timeoutMs);
  });
  try {
    while (true) {
      const next = await Promise.race([reader.read(), timeout]);
      if (next.done) break;
      if (!(next.value instanceof Uint8Array)) throw new BoundaryError(400, "InvalidRequest");
      total += next.value.byteLength;
      if (total > limit || ++reads > limit + 1) throw new BoundaryError(413, "RequestTooLarge");
      chunks.push(new Uint8Array(next.value));
    }
    const body = new Uint8Array(total); let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    return body;
  } finally {
    clearTimeout(timer);
    // Cancellation may be hostile or never settle: do not await it at this boundary.
    void reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
__TRANSFORM_FUNCTION__
function bindings(action: Action, fields: Record<string, unknown>): unknown[] {
  return action.bindings.map(binding => {
    const value = Object.hasOwn(binding, "param") ? fields[binding.param!] : binding.value;
    encodeValue(binding.type, value);
    if (binding.incrementable && value === MAX_SAFE) throw new Error("Revision overflow");
    return binding.type.kind === "bool" ? (value ? 1 : 0) : value;
  });
}
function rowValue(action: Action, raw: unknown): unknown {
  const row = object(raw, action.columns.map(column => column.name));
  const fields: Record<string, unknown> = Object.create(null);
  for (const column of action.columns) {
    let value = row[column.name];
    if (column.type.kind === "bool") {
      if (value !== 0 && value !== 1) throw new Error("Invalid database Bool");
      value = value === 1;
    }
    encodeValue(column.type, value);
    fields[column.name] = value;
  }
  let rowType = action.output;
  if (rowType.kind === "option" || rowType.kind === "list") rowType = rowType.elem;
  if (rowType.kind !== "record") throw new Error("Invalid row descriptor");
  return {record: rowType.name, fields};
}
function resultValue(action: Action, rows: unknown[]): unknown {
  if (rows.length > action.maxRows) throw new Error("Invalid database cardinality");
  if (action.cardinality === "bounded")
    return {list: rows.map(row => rowValue(action, row)), capacity: action.maxRows};
  if (rows.length === 0) {
    if (action.cardinality === "conditional") throw new BoundaryError(409, "ConditionNotMet");
    if (action.cardinality === "optional") return {tag: "None", value: null};
    throw new Error("Missing inserted row");
  }
  const row = rowValue(action, rows[0]);
  return action.cardinality === "one" ? row : {tag: "Some", value: row};
}
export function createDispatcher(
  db: D1Database, hostOptions: HostOptions,
): (request: Request) => Promise<Response> {
  if (typeof hostOptions?.allowedOrigin !== "string")
    throw new Error("Explicit allowedOrigin required");
  const origin = hostOptions.allowedOrigin;
  let parsedOrigin: URL;
  try { parsedOrigin = new URL(origin); } catch { throw new Error("Invalid allowedOrigin"); }
  if (!/^https?:$/.test(parsedOrigin.protocol) || parsedOrigin.origin !== origin)
    throw new Error("Invalid allowedOrigin");
  const maxBytes = hostOptions.maxRequestBytes ?? 32768;
  const timeoutMs = hostOptions.bodyTimeoutMs ?? 5000;
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 32768
    || !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000)
    throw new Error("Invalid request limits");
  // Capture trusted configuration once, preventing later option mutation from changing policy.
  const authorize = hostOptions.authorize;
  function response(body: string, status: number): Response {
    return new Response(body, {status, headers: {
      "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": origin, "Vary": "Origin", "X-Content-Type-Options": "nosniff",
      ...(status === 405 ? {"Allow": "POST"} : {}),
    }});
  }
  function error(status: number, label: string): Response {
    return response(JSON.stringify({error: label}), status);
  }
  return async (request: Request): Promise<Response> => {
    if (request.headers.get("origin") !== origin) return error(403, "Forbidden");
    if (request.method !== "POST") return error(405, "MethodNotAllowed");
    const contentType = request.headers.get("content-type") ?? "";
    if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(contentType)
      || ![null, "identity"].includes(request.headers.get("content-encoding")))
      return error(415, "UnsupportedMediaType");
    let envelope: Record<string, unknown>, action: Action, native: Record<string, unknown>;
    try {
      const raw = await readBounded(request, maxBytes, timeoutMs);
      envelope = object(parseWireJson(raw), ["action", "input"]);
      if (typeof envelope.action !== "string" || !ACTION_MAP.has(envelope.action))
        return error(400, "InvalidRequest");
      action = ACTION_MAP.get(envelope.action)!;
    } catch (failure) {
      return failure instanceof BoundaryError
        ? error(failure.status, failure.label) : error(400, "InvalidRequest");
    }
    try {
      native = action.input === null ? object(envelope.input, [])
        : (decodeValue(action.input, envelope.input) as {fields: Record<string, unknown>}).fields;
    } catch { return error(422, "InvalidInput"); }
    if (action.authorization !== "public") {
      try {
        if (authorize === undefined
          || await authorize(action.name, request, action.authorization) !== true)
          return error(403, "Forbidden");
      } catch { return error(403, "Forbidden"); }
    }
    let values: unknown[];
    try { values = bindings(action, transformParams(action, native)); }
    catch { return error(422, "InvalidInput"); }
    try {
      const outcome = await db.prepare(action.sql).bind(...values).all();
      if (outcome?.success !== true || !Array.isArray(outcome.results))
        throw new Error("Database failure");
      return response(encodeJson(action.output, resultValue(action, outcome.results)), 200);
    } catch (failure) {
      return failure instanceof BoundaryError
        ? error(failure.status, failure.label) : error(500, "ServiceUnavailable");
    }
  };
}
'''
