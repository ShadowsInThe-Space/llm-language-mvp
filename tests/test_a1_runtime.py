"""Pure portable target acceptance, independent of the historical Node emitter."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from llmlang.a1.interpreter import interpret
from llmlang.a1.runtime import (
    A1RuntimeError,
    emit_typescript_runtime,
    validate_runtime_module,
)


def module(
    functions: list[dict[str, Any]], types: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "format": "a1-ir-v1", "profile": "a1", "checker": "a1-check-v1",
        "types": types or [], "functions": functions, "specializations": [],
        "entrypoints": [f["name"] for f in functions],
        "limits": {"max_steps": 10000, "max_collection_expansion": 1000, "max_call_depth": 64},
    }


def identity(name: str = "identity", type_: object = "Int") -> dict[str, Any]:
    return {
        "name": name, "params": [{"name": "input", "type": type_}],
        "result": type_, "body": [], "return": "input",
    }


def target(
    source: dict[str, Any], calls: list[dict[str, Any]], entries: tuple[str, ...] | None = None
) -> list[dict[str, Any]]:
    whitelist = tuple(source["entrypoints"]) if entries is None else entries
    emitted = emit_typescript_runtime(source, whitelist)
    # Parse test data as JSON instead of constructing JS object literals with prototype keys.
    data = json.dumps(json.dumps(calls, ensure_ascii=True), ensure_ascii=True)
    harness = (
        "\nconst calls = JSON.parse(" + data + ");\n"
        "console.log(JSON.stringify(calls.map((c: {name: string; args: unknown[]}) => {"
        "try { return {ok:true,value:invokePure(c.name,c.args)}; } "
        "catch(e) { return {ok:false,code:(e as {code:string}).code}; } })));\n"
    )
    with tempfile.TemporaryDirectory() as directory:
        script = Path(directory) / "pure.ts"
        script.write_text(emitted + harness, encoding="utf-8")
        completed = subprocess.run(
            ["node", str(script)], text=True, capture_output=True, check=False, timeout=15
        )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


@unittest.skipUnless(shutil.which("node"), "Node portable target execution unavailable")
class PortableRuntimeAcceptance(unittest.TestCase):
    def test_constants_are_values_and_structure_queue_is_bounded(self) -> None:
        source = module([{
            "name": "main", "params": [], "result": "R", "body": [
                {"op": "const", "dest": "out", "type": "R", "value": {"ref": "missing"}},
            ], "return": "out",
        }], [{"kind": "record", "name": "R", "fields": [{"name": "x", "type": "Int"}]}])
        with self.assertRaises(A1RuntimeError):
            validate_runtime_module(source, ("main",))
        oversized = module([identity()])
        oversized["untrusted"] = [None] * 20000
        with self.assertRaises(A1RuntimeError):
            validate_runtime_module(oversized, ("identity",))

    def test_collection_budget_is_shared_by_callbacks_and_fresh_for_each_call(self) -> None:
        list_type = {"kind": "list", "elem": "Int", "capacity": 2}
        source = module([
            identity("item"),
            {"name": "main", "params": [{"name": "input", "type": list_type}],
             "result": list_type, "body": [
                 {"op": "bounded_map", "dest": "out", "callback": "item",
                  "list": {"ref": "input"}},
             ], "return": "out"},
        ])
        source["limits"]["max_collection_expansion"] = 1
        calls = [
            {"name": "main", "args": [{"list": [7], "capacity": 2}]},
            {"name": "main", "args": [{"list": [7], "capacity": 2}]},
            {"name": "main", "args": [{"list": [7, 8], "capacity": 2}]},
        ]
        self.assertEqual(target(source, calls), [
            {"ok": True, "value": {"list": [7], "capacity": 2}},
            {"ok": True, "value": {"list": [7], "capacity": 2}},
            {"ok": False, "code": "E_A1_COLLECTION_LIMIT"},
        ])

    def test_composite_boundary_checks_nested_payloads_and_exact_list_capacity(self) -> None:
        list_type = {"kind": "list", "elem": "Nat", "capacity": 2}
        option = {"kind": "option", "elem": list_type}
        result = {"kind": "result", "ok": option, "error": "Failure"}
        source = module([identity("main", result)], [
            {"kind": "variant", "name": "Failure", "cases": [
                {"tag": "Reason", "type": "Bool"},
            ]},
        ])
        valid = [
            {"tag": "Ok", "value": {"tag": "Some", "value": {"list": [0, 2], "capacity": 2}}},
            {"tag": "Ok", "value": {"tag": "None", "value": None}},
            {"tag": "Err", "value": {"variant": "Failure", "tag": "Reason", "value": False}},
        ]
        invalid = []
        for replacement in (True, -1, 1.5):
            bad = deepcopy(valid[0])
            bad["value"]["value"]["list"][0] = replacement
            invalid.append(bad)
        for replacement in (True, 1, 3):
            bad = deepcopy(valid[0])
            bad["value"]["value"]["capacity"] = replacement
            invalid.append(bad)
        bad = deepcopy(valid[2])
        bad["value"]["variant"] = "Other"
        invalid.extend([bad, {"tag": "Ok", "value": {"tag": "None", "value": 1}}])
        calls = [{"name": "main", "args": [value]} for value in valid + invalid]
        report = target(source, calls)
        self.assertEqual(report[:len(valid)], [
            {"ok": True, "value": interpret(source, "main", [value])} for value in valid
        ])
        self.assertTrue(all(not item["ok"] for item in report[len(valid):]))

    def test_text_work_has_a_trusted_aggregate_ceiling_per_invocation(self) -> None:
        capacity = 524288
        source = module([{
            "name": "main", "params": [{"name": "input", "type": {
                "kind": "text", "capacity": capacity,
            }}], "result": "Nat", "body": [
                {"op": "text_utf8_bytes", "dest": f"n{i}", "value": {"ref": "input"}}
                for i in range(3)
            ], "return": "n2",
        }])
        call = {"name": "main", "args": ["x" * capacity]}
        self.assertEqual(target(source, [call, call]), [
            {"ok": True, "value": capacity}, {"ok": True, "value": capacity},
        ])
        source["functions"][0]["body"] = [
            {"op": "text_utf8_bytes", "dest": f"n{i}", "value": {"ref": "input"}}
            for i in range(8)
        ]
        source["functions"][0]["return"] = "n7"
        self.assertEqual(target(source, [call]), [
            {"ok": False, "code": "E_A1_VALUE_LIMIT"},
        ])

    def test_refinement_and_concat_follow_reference_with_capacity_fail_closed(self) -> None:
        text_type = {"kind": "text", "capacity": 4}
        source = module([
            {"name": "refine", "params": [{"name": "input", "type": "Int"}],
             "result": "Nat", "body": [
                 {"op": "refine_nat", "dest": "out", "value": {"ref": "input"},
                  "evidence": {"predicate": ">=0", "rule": "A1-C004"}},
             ], "return": "out"},
            {"name": "concat", "params": [{"name": "a", "type": text_type},
                                           {"name": "b", "type": text_type}],
             "result": text_type, "body": [
                 {"op": "text_concat", "dest": "out", "left": {"ref": "a"},
                  "right": {"ref": "b"}, "capacity": 4},
             ], "return": "out"},
        ])
        valid = [{"name": "refine", "args": [0]}, {"name": "concat", "args": ["é", "e"]}]
        self.assertEqual(target(source, valid), [
            {"ok": True, "value": interpret(source, call["name"], call["args"])}
            for call in valid
        ])
        self.assertEqual(target(source, [
            {"name": "refine", "args": [-1]}, {"name": "concat", "args": ["éé", "x"]},
        ]), [
            {"ok": False, "code": "E_A1_REFINEMENT"},
            {"ok": False, "code": "E_A1_TEXT_CAPACITY"},
        ])

    def test_inline_composite_literals_cannot_bypass_nominal_operand_checks(self) -> None:
        declarations = [
            {"kind": "record", "name": name, "fields": [{"name": "x", "type": "Int"}]}
            for name in ("R", "Other")
        ]
        source = module([{
            "name": "main", "params": [], "result": "Int", "body": [
                {"op": "record_get", "dest": "out", "record": "R", "field": "x",
                 "value": {"record": "Other", "fields": {"x": 7}}},
            ], "return": "out",
        }], declarations)
        with self.assertRaises(A1RuntimeError):
            emit_typescript_runtime(source, ("main",))
        variants = [
            {"kind": "variant", "name": name, "cases": [{"tag": "Same"}]}
            for name in ("R", "Other")
        ]
        source = module([{
            "name": "main", "params": [], "result": "Int", "body": [
                {"op": "match_value", "dest": "out", "variant": "R", "type": "Int",
                 "value": {"variant": "Other", "tag": "Same"}, "arms": {"Same": 7}},
            ], "return": "out",
        }], variants)
        with self.assertRaises(A1RuntimeError):
            emit_typescript_runtime(source, ("main",))

    def test_portable_caps_reject_huge_declared_limits_before_execution(self) -> None:
        source = module([identity()])
        ceilings = (
            ("max_steps", 100000), ("max_collection_expansion", 10000), ("max_call_depth", 64)
        )
        for key, cap in ceilings:
            modified = deepcopy(source)
            modified["limits"][key] = cap + 1
            with self.subTest(key=key), self.assertRaises(A1RuntimeError):
                emit_typescript_runtime(modified, ("identity",))

    def test_optional_zero_argument_call_and_unit_literal_follow_reference(self) -> None:
        source = module([
            {"name": "unit", "params": [], "result": "Unit", "body": [
                {"op": "const", "dest": "v", "type": "Unit"},
            ], "return": "v"},
            {"name": "main", "params": [], "result": "Unit", "body": [
                {"op": "call", "dest": "v", "callee": "unit"},
            ], "return": "v"},
        ])
        self.assertEqual(target(source, [{"name": "main", "args": []}]), [
            {"ok": True, "value": interpret(source, "main", [])},
        ])

    def test_entry_whitelist_is_checked_and_internal_names_are_not_invocable(self) -> None:
        source = module([identity("private"), identity("public")])
        source["functions"][1]["body"] = [
            {"op": "call", "dest": "out", "callee": "private", "args": [{"ref": "input"}]}
        ]
        source["functions"][1]["return"] = "out"
        with self.assertRaises(A1RuntimeError):
            emit_typescript_runtime(source, ("missing",))
        with self.assertRaises(A1RuntimeError):
            emit_typescript_runtime(source, ("public", "public"))
        source["entrypoints"] = ["public"]
        with self.assertRaises(A1RuntimeError):
            emit_typescript_runtime(source, ("private",))
        self.assertEqual(
            target(source, [
                {"name": "public", "args": [3]}, {"name": "private", "args": [3]},
                {"name": "constructor", "args": []}, {"name": "__proto__", "args": []},
            ], ("public",)),
            [{"ok": True, "value": 3}] + [{"ok": False, "code": "E_A1_ENTRY"}] * 3,
        )

    def test_scalar_host_boundary_rejects_every_invalid_argument(self) -> None:
        source = module([
            identity("integer"), identity("natural", "Nat"), identity("boolean", "Bool"),
            identity("text", {"kind": "text", "capacity": 4}), identity("unit", "Unit"),
        ])
        bad = [
            {"name": "integer", "args": [True]},
            {"name": "integer", "args": [1.5]},
            {"name": "integer", "args": [9007199254740992]},
            {"name": "integer", "args": []},
            {"name": "integer", "args": [1, 2]},
            {"name": "natural", "args": [-1]},
            {"name": "boolean", "args": [1]},
            {"name": "text", "args": ["😀x"]},
            {"name": "text", "args": ["\ud800"]},
            {"name": "text", "args": ["\0"]},
            {"name": "unit", "args": [{}]},
        ]
        report = target(source, bad + [{"name": "text", "args": ["😀"]}])
        self.assertTrue(all(not result["ok"] and result.get("code") for result in report[:-1]))
        self.assertEqual(report[-1], {"ok": True, "value": "😀"})

    def test_text_records_variants_match_and_scalar_prefix_are_differential(self) -> None:
        source = module([{
            "name": "main", "params": [{"name": "text", "type": {"kind": "text", "capacity": 16}}],
            "result": "Report", "body": [
                {"op": "text_utf8_bytes", "dest": "bytes", "value": {"ref": "text"}},
                {"op": "text_codepoint_count", "dest": "points", "value": {"ref": "text"}},
                {"op": "text_prefix_codepoints", "dest": "prefix",
                 "value": {"ref": "text"}, "count": 2},
                {"op": "variant_make", "dest": "choice", "variant": "Choice", "tag": "Use"},
                {"op": "match_value", "dest": "matched", "variant": "Choice",
                 "value": {"ref": "choice"}, "arms": {"Use": {"ref": "prefix"}, "Skip": ""},
                 "type": {"kind": "text", "capacity": 16}},
                {"op": "record_make", "dest": "row", "record": "Report", "fields": {
                    "prefix": {"ref": "matched"}, "points": {"ref": "points"},
                    "bytes": {"ref": "bytes"},
                }},
                {"op": "record_get", "dest": "projection", "record": "Report",
                 "value": {"ref": "row"}, "field": "bytes"},
            ], "return": "row",
        }], [
            {"kind": "record", "name": "Report", "fields": [
                {"name": "prefix", "type": {"kind": "text", "capacity": 16}},
                {"name": "points", "type": "Nat"}, {"name": "bytes", "type": "Nat"},
            ]},
            {"kind": "variant", "name": "Choice", "cases": [{"tag": "Use"}, {"tag": "Skip"}]},
        ])
        calls = [{"name": "main", "args": [text]} for text in ("", "😀e\u0301", "Grüße", "العربية")]
        self.assertEqual(target(source, calls), [
            {"ok": True, "value": interpret(source, call["name"], call["args"])} for call in calls
        ])

    def test_lists_map_fold_append_and_index_follow_reference_without_mutation(self) -> None:
        list_type = {"kind": "list", "elem": "Int", "capacity": 3}
        source = module([
            identity("id"),
            {"name": "sum", "params": [{"name": "a", "type": "Int"}, {"name": "b", "type": "Int"}],
             "result": "Int", "body": [{"op": "add", "dest": "c",
                                        "left": {"ref": "a"}, "right": {"ref": "b"}}],
             "return": "c"},
            {"name": "mapfold", "params": [{"name": "items", "type": list_type}],
             "result": "Int", "body": [
                {"op": "bounded_map", "dest": "mapped", "list": {"ref": "items"}, "callback": "id"},
                {"op": "bounded_fold", "dest": "folded", "list": {"ref": "mapped"},
                 "initial": 0, "callback": "sum"},
             ], "return": "folded"},
            {"name": "index", "params": [{"name": "items", "type": list_type},
                                          {"name": "n", "type": "Nat"}],
             "result": {"kind": "option", "elem": "Int"}, "body": [
                 {"op": "list_index", "dest": "out", "list": {"ref": "items"},
                  "index": {"ref": "n"}},
             ], "return": "out"},
            {"name": "append", "params": [{"name": "items", "type": list_type}],
             "result": {"kind": "result", "ok": list_type, "error": "CapacityError"}, "body": [
                 {"op": "list_append", "dest": "out", "list": {"ref": "items"}, "value": 8},
             ], "return": "out"},
            {"name": "empty", "params": [], "result": list_type,
             "body": [{"op": "list_empty", "dest": "out", "capacity": 3, "type": list_type}],
             "return": "out"},
        ], [{"kind": "variant", "name": "CapacityError", "cases": [{"tag": "CapacityError"}]}])
        calls = [
            {"name": "mapfold", "args": [{"list": [1, 2, 3], "capacity": 3}]},
            {"name": "index", "args": [{"list": [1, 2], "capacity": 3}, 1]},
            {"name": "index", "args": [{"list": [], "capacity": 3}, 0]},
            {"name": "append", "args": [{"list": [1], "capacity": 3}]},
            {"name": "append", "args": [{"list": [1, 2, 3], "capacity": 3}]},
            {"name": "empty", "args": []},
        ]
        before = deepcopy(calls)
        self.assertEqual(target(source, calls), [
            {"ok": True, "value": interpret(source, call["name"], call["args"])} for call in calls
        ])
        self.assertEqual(calls, before)

    def test_original_limits_apply_and_each_invocation_has_a_fresh_budget(self) -> None:
        source = module([{
            "name": "main", "params": [{"name": "input", "type": "Int"}], "result": "Int",
            "body": [{"op": "add", "dest": "out", "left": {"ref": "input"}, "right": 1}],
            "return": "out",
        }])
        source["limits"]["max_steps"] = 1
        self.assertEqual(target(source, [{"name": "main", "args": [1]}] * 2), [
            {"ok": True, "value": 2}, {"ok": True, "value": 2},
        ])
        source["functions"][0]["body"].append(
            {"op": "add", "dest": "again", "left": {"ref": "out"}, "right": 1}
        )
        source["functions"][0]["return"] = "again"
        self.assertEqual(target(source, [{"name": "main", "args": [1]}]), [
            {"ok": False, "code": "E_A1_STEP_LIMIT"},
        ])
        chain = [identity("leaf")]
        for name, callee in (("middle", "leaf"), ("root", "middle")):
            function = identity(name)
            function["body"] = [
                {"op": "call", "dest": "out", "callee": callee, "args": [{"ref": "input"}]}
            ]
            function["return"] = "out"
            chain.append(function)
        source = module(chain)
        source["limits"]["max_call_depth"] = 1
        self.assertEqual(target(source, [{"name": "root", "args": [1]}]), [
            {"ok": False, "code": "E_A1_CALL_DEPTH"},
        ])

    def test_hostile_function_parameter_record_and_tag_names_are_data(self) -> None:
        source = module([{
            "name": "__proto__", "params": [{"name": "constructor", "type": "__proto__"}],
            "result": "__proto__", "body": [], "return": "constructor",
        }], [{"kind": "record", "name": "__proto__", "fields": [
            {"name": "__proto__", "type": "Int"}, {"name": "constructor", "type": "Bool"},
        ]}])
        value = {"record": "__proto__", "fields": {"__proto__": 1, "constructor": False}}
        self.assertEqual(target(source, [{"name": "__proto__", "args": [value]}]), [
            {"ok": True, "value": value},
        ])
        malformed = deepcopy(value)
        malformed["fields"]["admin"] = True
        self.assertEqual(target(source, [{"name": "__proto__", "args": [malformed]}]), [
            {"ok": False, "code": "E_A1_TYPE"},
        ])

    def test_result_monitor_and_target_integer_overflow_fail_closed(self) -> None:
        source = module([{
            "name": "add", "params": [{"name": "input", "type": "Int"}], "result": "Int",
            "body": [{"op": "add", "dest": "out", "left": {"ref": "input"}, "right": 1}],
            "return": "out",
        }])
        self.assertEqual(target(source, [{"name": "add", "args": [9007199254740991]}]), [
            {"ok": False, "code": "E_A1_UNSAFE_INTEGER"},
        ])
        with self.assertRaises(ValueError):
            unsafe = deepcopy(source)
            unsafe["functions"][0]["body"][0]["right"] = 9007199254740992
            emit_typescript_runtime(unsafe, ("add",))
        emitted = emit_typescript_runtime(source, ("add",))
        for forbidden in ("Buffer", "process.", "node:", "eval("):
            self.assertNotIn(forbidden, emitted)


if __name__ == "__main__":
    unittest.main()
