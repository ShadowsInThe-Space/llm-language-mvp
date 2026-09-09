"""Bounded exact transport at the host boundary."""

import json
import re
from pathlib import Path

from llmlang.model import LanguageError, Limits, Value

_INTEGER = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")
DEFAULT_LIMITS = Limits()


def read_text(path: Path, max_bytes: int) -> str:
    with path.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise LanguageError("E_LIMIT", "Input file exceeds byte budget")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LanguageError("E_ENCODING", "Input is not UTF-8") from exc


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LanguageError("E_JSON", "Duplicate JSON field")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise LanguageError("E_JSON", "Non-finite JSON number")


def load_json(text: str, max_bytes: int = 131072) -> object:
    if len(text.encode("utf-8")) > max_bytes:
        raise LanguageError("E_LIMIT", "JSON exceeds byte budget")
    try:
        result: object = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
        return result
    except (ValueError, RecursionError) as exc:
        raise LanguageError("E_JSON", "Invalid or excessively nested JSON") from exc


def decode_value(value: object, limits: Limits = DEFAULT_LIMITS) -> Value:
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        raise LanguageError("E_VALUE", "Expected a typed value object")
    tag, data = value["type"], value["value"]
    if tag == "Bool" and type(data) is bool:
        return bool(data)
    if tag == "Int" and isinstance(data, str):
        if len(data.lstrip("-")) > limits.max_int_digits:
            raise LanguageError("E_LIMIT", "Integer exceeds digit budget")
        if not _INTEGER.fullmatch(data):
            raise LanguageError("E_VALUE", "Int requires a canonical decimal string")
        result = int(data)
        if result.bit_length() > limits.max_bits:
            raise LanguageError("E_LIMIT", "Integer exceeds bit budget")
        return result
    raise LanguageError("E_VALUE", "Expected exact Int string or Bool")


def decode_inputs(text: str, limits: Limits = DEFAULT_LIMITS) -> tuple[Value, ...]:
    data = load_json(text, limits.max_source_bytes)
    if not isinstance(data, list):
        raise LanguageError("E_VALUE", "Inputs must be an array of typed values")
    if len(data) > limits.max_nodes:
        raise LanguageError("E_LIMIT", "Too many inputs")
    return tuple(decode_value(item, limits) for item in data)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
