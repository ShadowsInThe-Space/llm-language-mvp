"""Canonical serialization must preserve nominal record behavior."""

import json
import unittest
from copy import deepcopy

from llmlang.a1 import canonical_bytes, interpret, module_hash, validate_module
from llmlang.a1.ir import A1IRError


def record_module():
    return {
        "format": "a1-ir-v1", "profile": "a1", "checker": "a1-check-v1",
        "specializations": [], "entrypoints": ["make"],
        "limits": {"max_steps": 100, "max_collection_expansion": 10, "max_call_depth": 4},
        "types": [{"kind": "record", "name": "Task", "fields": [
            {"name": "title", "type": {"kind": "text", "capacity": 32}},
            {"name": "done", "type": "Bool"},
            {"name": "priority", "type": "Nat"},
        ]}],
        "functions": [{"name": "make", "params": [], "result": "Task", "body": [
            {"op": "record_make", "dest": "task", "record": "Task", "fields": {
                "title": "Grüße 🌍", "done": False, "priority": 2,
            }},
        ], "return": "task"}],
    }


class CanonicalRecordTests(unittest.TestCase):
    def test_canonical_roundtrip_preserves_execution_and_binding(self):
        module = record_module()
        validate_module(module)
        restored = json.loads(canonical_bytes(module))
        validate_module(restored)
        self.assertEqual(module_hash(module), module_hash(restored))
        self.assertEqual(interpret(module, "make", []), interpret(restored, "make", []))

    def test_missing_extra_and_wrongly_typed_fields_remain_rejected(self):
        for mutation in ("missing", "extra", "wrong-type"):
            with self.subTest(mutation=mutation):
                module = deepcopy(record_module())
                fields = module["functions"][0]["body"][0]["fields"]
                if mutation == "missing":
                    del fields["title"]
                elif mutation == "extra":
                    fields["admin"] = True
                else:
                    fields["done"] = 1
                with self.assertRaises(A1IRError):
                    validate_module(module)

    def test_declaration_order_remains_part_of_semantic_binding(self):
        module = record_module()
        reordered = deepcopy(module)
        reordered["types"][0]["fields"].reverse()
        self.assertNotEqual(module_hash(module), module_hash(reordered))


if __name__ == "__main__":
    unittest.main()
