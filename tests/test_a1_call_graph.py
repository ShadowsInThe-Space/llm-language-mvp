"""Static acyclic graph validation must not depend on Python recursion depth."""

import unittest

from llmlang.a1 import interpret, validate_module
from llmlang.a1.ir import A1IRError
from llmlang.a1.source import parse_source


class CallGraphTests(unittest.TestCase):
    def source(self, cycle=False):
        functions = []
        for index in range(1200):
            operation = (f"(call f{index + 1:04d})" if index < 1199
                         else "(call f0000)" if cycle else "(const 7)")
            functions.append(f"(fn f{index:04d} () Nat (let x Nat {operation}) (return x))")
        return "(a1src1 (limits 10000 1000 64) " + " ".join(functions) + " (entry f1199))"

    def test_deep_declaration_graph_with_shallow_entry_is_valid(self):
        parsed = parse_source(self.source())
        validate_module(parsed.module)
        self.assertEqual(interpret(parsed.module, "f1199", []), 7)

    def test_deep_execution_still_obeys_declared_call_budget(self):
        parsed = parse_source(self.source())
        module = parsed.module
        module["entrypoints"] = ["f0000"]
        with self.assertRaises(A1IRError) as raised:
            interpret(module, "f0000", [])
        self.assertEqual(raised.exception.code, "E_A1_CALL_DEPTH")

    def test_deep_cycle_is_rejected_with_stable_cycle_code(self):
        module = parse_source(self.source()).module
        module["functions"][-1]["body"] = [
            {"op": "call", "dest": "x", "callee": "f0000", "args": [], "type": "Nat"},
        ]
        with self.assertRaises(A1IRError) as raised:
            validate_module(module)
        self.assertEqual(raised.exception.code, "E_A1_CALL_CYCLE")


if __name__ == "__main__":
    unittest.main()
