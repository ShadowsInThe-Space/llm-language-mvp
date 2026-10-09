"""Every normative primitive type spelling must execute its checked constants."""

import unittest

from llmlang.a1 import interpret, validate_module
from llmlang.a1.ir import A1IRError


def constant_module(type_name, value):
    return {
        "format": "a1-ir-v1", "profile": "a1", "checker": "a1-check-v1",
        "types": [], "specializations": [], "entrypoints": ["constant"],
        "limits": {"max_steps": 10, "max_collection_expansion": 10, "max_call_depth": 4},
        "functions": [{"name": "constant", "params": [], "result": type_name,
                       "body": [{"op": "const", "dest": "value", "type": type_name,
                                 "value": value}], "return": "value"}],
    }


class PrimitiveConstantTests(unittest.TestCase):
    def test_string_and_object_type_spellings_have_identical_behavior(self):
        for name, value in (("Unit", None), ("Bool", False), ("Int", -4), ("Nat", 4)):
            for type_name in (name, {"kind": name.lower()}):
                with self.subTest(type_name=type_name):
                    module = constant_module(type_name, value)
                    validate_module(module)
                    self.assertEqual(interpret(module, "constant", []), value)

    def test_invalid_primitive_literals_still_fail_before_execution(self):
        for name, value in (("Bool", 1), ("Nat", -1), ("Int", True), ("Unit", 0)):
            with self.subTest(name=name), self.assertRaises(A1IRError):
                interpret(constant_module(name, value), "constant", [])


if __name__ == "__main__":
    unittest.main()
