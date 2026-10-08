"""Independent wire-boundary and Python/TypeScript differential acceptance."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from llmlang.web.general.codecs import (
    MAX_NODES,
    MAX_SAFE_INTEGER,
    MAX_WIRE_BYTES,
    BoolType,
    CodecError,
    IntType,
    ListType,
    NatType,
    OptionType,
    RecordType,
    TextType,
    decode_json,
    decode_value,
    emit_typescript_runtime,
    encode_json,
    encode_value,
    max_wire_bytes,
    max_wire_nodes,
    parse_wire_json,
    type_descriptor,
)


class CodecAcceptance(unittest.TestCase):
    def test_static_json_node_bound_rejects_rows_that_fit_byte_budget(self) -> None:
        row = RecordType("R", tuple((f"f{index}", BoolType()) for index in range(31)))
        codec = ListType(row, 80)
        value = {"record": "R", "fields": {f"f{index}": False for index in range(31)}}
        wire = encode_value(codec, {"list": [value] * 80, "capacity": 80})
        raw = json.dumps(wire, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        self.assertLessEqual(max_wire_bytes(codec), MAX_WIRE_BYTES)
        self.assertLessEqual(len(raw.encode("ascii")), MAX_WIRE_BYTES)
        self.assertEqual(max_wire_nodes(row), 67)
        self.assertEqual(max_wire_nodes(codec), 5361)
        self.assertGreater(max_wire_nodes(codec), MAX_NODES)
        with self.assertRaises(CodecError) as rejected:
            encode_json(codec, {"list": [value] * 80, "capacity": 80})
        self.assertEqual(rejected.exception.code, "W_CODEC_LIMIT")
        self.assertEqual(rejected.exception.path, "json")
        smaller = ListType(row, 60)
        self.assertLessEqual(max_wire_nodes(smaller), MAX_NODES)
        self.assertEqual(
            decode_json(smaller, encode_json(smaller, {"list": [value] * 60, "capacity": 60})),
            {"list": [value] * 60, "capacity": 60},
        )
        self.assertEqual(max_wire_nodes(OptionType(TextType(0))), 5)
        self.assertEqual(max_wire_nodes(OptionType(row)), 71)
        with self.assertRaises(CodecError):
            max_wire_nodes(TextType(True))

    def test_static_wire_bound_accounts_for_escape_and_composite_overheads(self) -> None:
        self.assertEqual(max_wire_bytes(TextType(0)), 2)
        self.assertEqual(max_wire_bytes(TextType(8)), 50)
        self.assertEqual(max_wire_bytes(IntType()), 19)
        self.assertEqual(max_wire_bytes(NatType()), 18)
        self.assertEqual(max_wire_bytes(BoolType()), 5)
        self.assertEqual(max_wire_bytes(OptionType(TextType(0))), 27)
        self.assertEqual(max_wire_bytes(ListType(TextType(8), 2)), 103)
        task = RecordType(
            "tasks.browseRow",
            (("id", TextType(64)), ("title", TextType(512)), ("done", BoolType())),
        )
        self.assertGreater(max_wire_bytes(ListType(task, 50)), MAX_WIRE_BYTES)
        self.assertLessEqual(max_wire_bytes(ListType(task, 8)), MAX_WIRE_BYTES)
        with self.assertRaises(CodecError):
            max_wire_bytes(TextType(True))
        nested = TextType(1)
        for _ in range(31):
            nested = ListType(nested, 4096)
        self.assertGreater(max_wire_bytes(nested), 2**53)

    @unittest.skipUnless(shutil.which("node"), "Node TypeScript target unavailable")
    def test_wire_bound_matches_node_and_bounds_real_canonical_values(self) -> None:
        row = RecordType(
            "pkg.Row", (("text", TextType(8)), ("number", IntType()), ("flag", BoolType()))
        )
        value = {
            "record": "pkg.Row",
            "fields": {"text": "\x01" * 8, "number": -MAX_SAFE_INTEGER, "flag": False},
        }
        cases = (
            (TextType(8), "\x01" * 8),
            (TextType(8), "😀😀"),
            (IntType(), -MAX_SAFE_INTEGER),
            (NatType(), MAX_SAFE_INTEGER),
            (BoolType(), False),
            (row, value),
            (ListType(row, 2), {"list": [value, value], "capacity": 2}),
            (OptionType(row), {"tag": "Some", "value": value}),
            (OptionType(TextType(0)), {"tag": "None", "value": None}),
        )
        payload = [
            {"type": type_descriptor(codec), "value": native}
            for codec, native in cases
        ]
        expected = []
        for codec, native in cases:
            encoded = encode_json(codec, native)
            bound = max_wire_bytes(codec)
            self.assertLessEqual(len(encoded.encode("ascii")), bound)
            def count_nodes(wire: object) -> int:
                if isinstance(wire, dict):
                    return 1 + len(wire) + sum(count_nodes(child) for child in wire.values())
                if isinstance(wire, list):
                    return 1 + sum(count_nodes(child) for child in wire)
                return 1

            nodes = max_wire_nodes(codec)
            self.assertLessEqual(count_nodes(json.loads(encoded)), nodes)
            expected.append({"bound": str(bound), "nodes": str(nodes), "encoded": encoded})
        large = type_descriptor(ListType(TextType(32768), 4096))
        payload.append({"type": large})
        expected.append({
            "bound": str(max_wire_bytes(ListType(TextType(32768), 4096))),
            "nodes": str(max_wire_nodes(ListType(TextType(32768), 4096))),
        })
        nested = TextType(1)
        for _ in range(31):
            nested = ListType(nested, 4096)
        payload.append({"type": type_descriptor(nested)})
        expected.append(
            {"bound": str(max_wire_bytes(nested)), "nodes": str(max_wire_nodes(nested))}
        )
        harness = "\nconst boundCases = " + json.dumps(payload, ensure_ascii=True) + ";\n"
        harness += (
            "console.log(JSON.stringify(boundCases.map(c => Object.hasOwn(c,'value') "
            "? {bound:maxWireBytes(c.type as CodecType).toString(),"
            "nodes:maxWireNodes(c.type as CodecType).toString(),"
            "encoded:encodeJson(c.type as CodecType,c.value)} "
            ": {bound:maxWireBytes(c.type as CodecType).toString(),"
            "nodes:maxWireNodes(c.type as CodecType).toString()})));\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "bounds.ts"
            script.write_text(emit_typescript_runtime() + harness, encoding="utf-8")
            completed = subprocess.run(
                ["node", str(script)], text=True, capture_output=True, check=False, timeout=15
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), expected)

    def test_action_envelope_parser_checks_raw_json_before_type_selection(self) -> None:
        self.assertEqual(
            parse_wire_json(b'{"action":"save","input":{"record":"R","fields":{"n":"1"}}}'),
            {"action": "save", "input": {"record": "R", "fields": {"n": "1"}}},
        )
        with self.assertRaises(CodecError):
            parse_wire_json('{"action":"save","\\u0061ction":"other","input":{}}')

    def test_types_are_closed_frozen_and_capacity_checked(self) -> None:
        text = TextType(4)
        with self.assertRaises(FrozenInstanceError):
            text.capacity = 8  # type: ignore[misc]
        for invalid in (-1, True, 32769):
            with self.subTest(invalid=invalid), self.assertRaises(CodecError):
                type_descriptor(TextType(invalid))
        with self.assertRaises(CodecError):
            type_descriptor(RecordType("R", (("x", IntType()), ("x", BoolType()))))
        with self.assertRaises(CodecError):
            type_descriptor({"kind": "capability"})  # type: ignore[arg-type]

    def test_decimal_integer_wire_is_exact_and_canonical(self) -> None:
        for number in (0, -1, 1, -MAX_SAFE_INTEGER, MAX_SAFE_INTEGER):
            self.assertEqual(decode_value(IntType(), str(number)), number)
            self.assertEqual(encode_value(IntType(), number), str(number))
        for bad in ("-0", "01", "-01", "+1", "1e2", "1.0", " 1", "1 ", "1\n", "١", 1, True):
            with self.subTest(bad=bad), self.assertRaises(CodecError):
                decode_value(IntType(), bad)
        for bad in (MAX_SAFE_INTEGER + 1, -MAX_SAFE_INTEGER - 1, True, 1.0):
            with self.subTest(bad=bad), self.assertRaises(CodecError):
                encode_value(IntType(), bad)
        with self.assertRaises(CodecError):
            decode_value(NatType(), "-1")
        with self.assertRaises(CodecError):
            decode_json(IntType(), "9007199254740991.1")

    def test_unicode_is_scalar_valid_and_bounded_in_utf8_without_normalization(self) -> None:
        for text in ("", "é", "e\u0301", "😀", " \r\nالعربية", "</script>"):
            capacity = len(text.encode("utf-8"))
            self.assertEqual(decode_value(TextType(capacity), text), text)
            self.assertEqual(
                decode_json(TextType(capacity), encode_json(TextType(capacity), text)), text
            )
        for bad in ("\0", "\ud800", "\udfff", "\ud800x"):
            with self.subTest(bad=repr(bad)), self.assertRaises(CodecError):
                encode_value(TextType(32), bad)
        with self.assertRaises(CodecError):
            decode_value(TextType(3), "😀")
        self.assertEqual(decode_json(TextType(4), '"\\ud83d\\ude00"'), "😀")
        with self.assertRaises(CodecError):
            decode_json(TextType(8), b'"\xff"')

    def test_structured_values_preserve_nominal_shape_and_reconstruct_list_capacity(self) -> None:
        row = RecordType(
            "app.Task", (("title", TextType(8)), ("done", BoolType()), ("rank", NatType()))
        )
        codec = OptionType(ListType(row, 2))
        item = {"record": "app.Task", "fields": {"title": "😀", "done": False, "rank": 1}}
        runtime = {"tag": "Some", "value": {"list": [item], "capacity": 2}}
        wire = {
            "tag": "Some",
            "value": [
                {"record": "app.Task", "fields": {"title": "😀", "done": False, "rank": "1"}}
            ],
        }
        self.assertEqual(encode_value(codec, runtime), wire)
        self.assertEqual(decode_value(codec, wire), runtime)
        self.assertEqual(
            decode_value(codec, {"tag": "None", "value": None}), {"tag": "None", "value": None}
        )
        for bad in (
            {"tag": "None"},
            {"tag": "None", "value": False},
            {"tag": "Some", "value": {"list": [], "capacity": 2}},
            {"tag": "Some", "value": [item, item, item]},
        ):
            with self.subTest(bad=bad), self.assertRaises(CodecError):
                decode_value(codec, bad)
        for bad in (
            {"record": "other.Task", "fields": wire["value"][0]["fields"]},
            {"record": "app.Task", "fields": {"title": "x", "done": 0, "rank": "1"}},
            {
                "record": "app.Task",
                "fields": {"title": "x", "done": False, "rank": "1", "admin": True},
            },
        ):
            with self.subTest(bad=bad), self.assertRaises(CodecError):
                decode_value(row, bad)
        with self.assertRaises(CodecError):
            encode_value(ListType(row, 2), {"list": [item], "capacity": 3})

    def test_strict_json_rejects_duplicate_decoded_keys_unknown_fields_and_limits(self) -> None:
        row = RecordType("R", (("x", IntType()),))
        bad_sources = (
            '{"record":"R","record":"R","fields":{"x":"1"}}',
            '{"record":"R","fields":{"x":"1","\\u0078":"2"}}',
            '{"record":"R","fields":{"x":"1"},"capability":{"db":true}}',
            '{"record":"R","fields":{"x":NaN}}',
            '{"record":"R","fields":{"x":"1"}} trailing',
        )
        for source in bad_sources:
            with self.subTest(source=source), self.assertRaises(CodecError):
                decode_json(row, source)
        source = '{"record":"R","fields":{"x":"1"}}'
        self.assertEqual(
            decode_json(row, source + " " * (32768 - len(source))),
            {"record": "R", "fields": {"x": 1}},
        )
        with self.assertRaises(CodecError):
            decode_json(row, source + " " * 32768)
        with self.assertRaises(CodecError):
            decode_json(row, "[" * 1000 + "0" + "]" * 1000)

    @unittest.skipUnless(shutil.which("node"), "Node TypeScript target unavailable")
    def test_python_typescript_differential_and_portable_runtime(self) -> None:
        row = RecordType("R", (("z", TextType(8)), ("n", IntType()), ("b", BoolType())))
        cases = [
            (IntType(), '"9007199254740991"'),
            (IntType(), '"-9007199254740991"'),
            (IntType(), "9007199254740991.1"),
            (IntType(), '"9007199254740992"'),
            (IntType(), '"-0"'),
            (IntType(), '"1\\n"'),
            (NatType(), '"-1"'),
            (TextType(4), '"\\ud83d\\ude00"'),
            (TextType(3), '"😀"'),
            (TextType(8), '"\\ud800"'),
            (TextType(8), '"\\u0000"'),
            (BoolType(), "true"),
            (BoolType(), "1"),
            (BoolType(), "[" * 32 + "true" + "]" * 32),
            (ListType(BoolType(), 4096), "[" + ",".join(["true"] * 4096) + "]"),
            (row, '{"record":"R","fields":{"z":"e\\u0301","n":"2","b":false}}'),
            (row, '{"record":"R","fields":{"z":"x","n":"1","\\u006e":"2","b":false}}'),
            (OptionType(ListType(row, 0)), '{"tag":"Some","value":[]}'),
            (OptionType(ListType(row, 0)), '{"tag":"Some","value":[{}]}'),
            (
                RecordType("R", (("__proto__", TextType(8)),)),
                '{"record":"R","fields":{"__proto__":"data"}}',
            ),
        ]
        expected = []
        for codec, source in cases:
            try:
                value = decode_json(codec, source)
                expected.append({"ok": True, "encoded": encode_json(codec, value), "value": value})
            except CodecError as error:
                expected.append({"ok": False, "code": error.code})
        runtime = emit_typescript_runtime()
        self.assertNotIn("Buffer", runtime)
        self.assertNotIn("node:", runtime)
        self.assertNotIn("process.", runtime)
        payload = [{"type": type_descriptor(codec), "source": source} for codec, source in cases]
        harness = "\nconst cases = " + json.dumps(payload, ensure_ascii=True) + ";\n"
        harness += (
            "const report = cases.map(c => { try { "
            "const value = decodeJson(c.type as CodecType, c.source); "
            "return {ok:true,encoded:encodeJson(c.type as CodecType,value),value}; "
            "} catch(e) { return {ok:false,code:(e as CodecError).code}; } }); "
            "console.log(JSON.stringify(report));\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "codec.ts"
            script.write_text(runtime + harness, encoding="utf-8")
            completed = subprocess.run(
                ["node", str(script)], text=True, capture_output=True, check=False, timeout=15
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), expected)


if __name__ == "__main__":
    unittest.main()
