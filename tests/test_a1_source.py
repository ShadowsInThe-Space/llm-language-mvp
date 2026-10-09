"""Behavioral contracts for the additive, bounded A1 source frontend."""

import unittest
from copy import deepcopy

from llmlang.a1 import interpret, module_hash
from llmlang.a1.source import (
    A1SourceError,
    SourceLimits,
    canonicalize_source,
    check_source_binding,
    lower_source,
    parse_source,
)

SAMPLE = '''(a1src1
  (limits 10000 1000 64)
  (record Task (title (Text 32)) (done Bool))
  (fn title ((task Task)) (Text 32)
    (let text (Text 32) (record_get Task task title))
    (return text))
  (fn main () Nat
    (let title (Text 32) (const "Grüße"))
    (let done Bool (const false))
    (let task Task (record_make Task (title title) (done done)))
    (let text (Text 32) (call title task))
    (let size Nat (text_utf8_bytes text))
    (return size))
  (entry main))'''


class SourceTests(unittest.TestCase):
    def test_real_lowering_interpretation_and_canonical_roundtrip(self):
        parsed = parse_source(SAMPLE)
        self.assertEqual(interpret(parsed.module, "main", []), 7)
        self.assertEqual(parsed.semantic_hash, module_hash(parsed.module))
        again = parse_source(parsed.canonical_source)
        self.assertEqual(again.module, parsed.module)
        self.assertEqual(again.canonical_source, parsed.canonical_source)
        self.assertEqual(canonicalize_source(SAMPLE), parsed.canonical_source)
        self.assertEqual(parsed.module["functions"][1]["body"][2]["dest"], "task")
        self.assertEqual(parsed.source_map["functions[1].body[2]"].line, 10)

    def test_binding_recomputes_ir_and_rejects_each_semantic_tamper(self):
        module = lower_source(SAMPLE)
        self.assertTrue(check_source_binding(SAMPLE, module))
        for mutate in (
            lambda m: m["functions"][1]["body"][0].update(value="other"),
            lambda m: m["limits"].update(max_steps=9),
            lambda m: m.update(entrypoints=[]),
            lambda m: m["types"][0]["fields"][0].update(type="Int"),
            lambda m: m.update(source_hash=module_hash(m)),
        ):
            changed = deepcopy(module)
            mutate(changed)
            self.assertFalse(check_source_binding(SAMPLE, changed))
        self.assertFalse(check_source_binding("(a1src9)", module))

    def test_whitespace_and_escape_spelling_do_not_change_semantic_hash(self):
        escaped = SAMPLE.replace("Grüße", r"Gr\u00fc\u00dfe")
        self.assertEqual(parse_source(SAMPLE).semantic_hash, parse_source(escaped).semantic_hash)
        self.assertEqual(canonicalize_source(SAMPLE), canonicalize_source(escaped))

    def test_closed_grammar_and_ssa_fail_closed(self):
        bad_sources = [
            SAMPLE.replace("a1src1", "a1src2"),
            SAMPLE + " (entry main)",
            SAMPLE.replace("(const false)", "(const false extra)"),
            SAMPLE.replace("(const false)", "(fetch false)"),
            SAMPLE.replace("(const false)", "(const missing)"),
            SAMPLE.replace("(let done Bool", "(let title Bool"),
            SAMPLE.replace("(call title task)", "(call title unknown)"),
            SAMPLE.replace("(return size)", "(return missing)"),
            SAMPLE.replace("(let size Nat", "(let size Bool"),
            SAMPLE.replace("(entry main)", "(effect HTTP)"),
            SAMPLE.replace("(done Bool)", "(done Bool) (done Bool)"),
            SAMPLE.replace("(limits 10000 1000 64)", "(limits 0 1000 64)"),
            SAMPLE.replace("(title (Text 32))", "(title (Text 32 extra))"),
        ]
        for source in bad_sources:
            with self.subTest(source=source):
                with self.assertRaises(A1SourceError) as caught:
                    parse_source(source)
                self.assertTrue(caught.exception.code.startswith("E_A1_SOURCE"))
                self.assertIn("location", caught.exception.to_dict())

    def test_limits_and_text_encoding_are_bounded(self):
        for source, limits in (
            (SAMPLE, SourceLimits(max_bytes=10)),
            (SAMPLE, SourceLimits(max_nodes=5)),
            ("(" * 65 + ")" * 65, SourceLimits()),
            (SAMPLE.replace("Grüße", "\x00"), SourceLimits()),
            (SAMPLE.replace("Grüße", r"\u0000"), SourceLimits()),
            (SAMPLE.replace("Grüße", r"\ud800"), SourceLimits()),
            (SAMPLE.replace("Grüße", r"\x41"), SourceLimits()),
            (SAMPLE.replace("10000", "9" * 1025), SourceLimits()),
        ):
            with self.subTest(source=source):
                with self.assertRaises(A1SourceError):
                    parse_source(source, limits=limits)
        with self.assertRaises(A1SourceError):
            SourceLimits(max_depth=10000)

    def test_list_map_fold_index_and_text_prefix(self):
        source = '''(a1src1 (limits 1000 100 20)
          (fn identity ((x Int)) Int (return x))
          (fn sum ((acc Int) (x Int)) Int (let n Int (add acc x)) (return n))
          (fn main ((items (List Int 3))) Int
            (let mapped (List Int 3) (bounded_map items identity))
            (let total Int (bounded_fold mapped 0 sum)) (return total))
          (entry main))'''
        self.assertEqual(
            interpret(lower_source(source), "main", [{"capacity": 3, "list": [1, 2]}]), 3
        )
        source = '''(a1src1 (limits 1000 100 20)
          (fn main () (Text 16)
            (let text (Text 16) (const "😀éx"))
            (let count Nat (const 2))
            (let prefix (Text 16) (text_prefix_codepoints text count))
            (return prefix)) (entry main))'''
        self.assertEqual(interpret(lower_source(source), "main", []), "😀é")

    def test_variants_match_refinement_and_structured_literals(self):
        source = '''(a1src1 (limits 1000 100 20)
          (variant Choice (Yes Int) (No))
          (fn main () Nat
            (let choice Choice (variant_make Choice Yes 4))
            (let n Int (match_value Choice choice (Yes 4) (No 0)))
            (let result Nat (refine_nat n (evidence >=0 A1-C004)))
            (return result)) (entry main))'''
        self.assertEqual(interpret(lower_source(source), "main", []), 4)
        source = '''(a1src1 (limits 1000 100 20)
          (fn main () (Option Int)
            (let items (List Int 3) (const (list 3 7 8)))
            (let index Nat (const 1))
            (let item (Option Int) (list_index items index))
            (return item)) (entry main))'''
        self.assertEqual(interpret(lower_source(source), "main", []), {"tag": "Some", "value": 8})
        with self.assertRaises(A1SourceError):
            parse_source(source.replace("(list 3 7 8)", '(list 3 "wrong")'))


    def test_remaining_pure_ops_and_immutable_list_append(self):
        source = '''(a1src1 (limits 1000 100 20)
          (variant CapacityError (CapacityError))
          (fn main () (Result (List Nat 1) CapacityError)
            (let left (Text 4) (const "é"))
            (let right (Text 4) (const "x"))
            (let text (Text 8) (text_concat left right 8))
            (let size Nat (text_codepoint_count text))
            (let empty (List Nat 1) (list_empty))
            (let appended (Result (List Nat 1) CapacityError) (list_append empty size))
            (return appended)) (entry main))'''
        self.assertEqual(interpret(lower_source(source), "main", []),
                         {"tag": "Ok", "value": {"capacity": 1, "list": [2]}})

    def test_all_structured_constant_forms_are_real_tagged_values(self):
        literals = [
            ("Task", '(record Task (title "a") (done true))',
             {"record": "Task", "fields": {"title": "a", "done": True}}),
            ("Choice", "(variant Choice No)", {"variant": "Choice", "tag": "No"}),
            ("Choice", "(variant Choice Yes 3)",
             {"variant": "Choice", "tag": "Yes", "value": 3}),
            ("(Option Int)", "(none)", {"tag": "None"}),
            ("(Option Int)", "(some 3)", {"tag": "Some", "value": 3}),
            ("(Result Int Bool)", "(ok 3)", {"tag": "Ok", "value": 3}),
            ("(Result Int Bool)", "(err false)", {"tag": "Err", "value": False}),
            ("Unit", "unit", None),
        ]
        for declared, literal, expected in literals:
            with self.subTest(literal=literal):
                source = f'''(a1src1 (limits 1000 100 20)
                  (record Task (title (Text 4)) (done Bool))
                  (variant Choice (Yes Int) (No))
                  (fn main () {declared}
                    (let result {declared} (const {literal})) (return result))
                  (entry main))'''
                self.assertEqual(interpret(lower_source(source), "main", []), expected)

    def test_structured_literals_and_untrusted_offers_fail_closed(self):
        template = '''(a1src1 (limits 1000 100 20)
          (record Task (title (Text 4)) (done Bool))
          (variant Choice (Yes Int) (No))
          (fn main () TYPE (let result TYPE (const VALUE)) (return result))
          (entry main))'''
        for declared, literal in (
            ("Task", '(record Other (title "a") (done true))'),
            ("Task", '(record Task (title "large") (done true))'),
            ("Choice", "(variant Choice Maybe)"),
            ("Choice", "(variant Choice No 3)"),
            ("Choice", "(variant Choice Yes)"),
            ("(List Nat 1)", "(list 1 -1)"),
            ("(List Int 1)", "(list 1 1 2)"),
            ("(Option Nat)", "(some -1)"),
            ("(Result Int Bool)", "(err 7)"),
        ):
            with self.subTest(literal=literal):
                with self.assertRaises(A1SourceError):
                    parse_source(template.replace("TYPE", declared).replace("VALUE", literal))
        for offered in (None, [], {"functions": [{}]}, {"functions": [None]},
                        {"types": [{"name": []}]}, {"hash": float("nan")}, object()):
            self.assertFalse(check_source_binding(SAMPLE, offered))

    def test_rejection_diagnostics_are_deterministic_and_have_source_positions(self):
        source = SAMPLE.replace("(call title task)", "(call title missing)")
        diagnostics = []
        for _ in range(2):
            with self.assertRaises(A1SourceError) as caught:
                parse_source(source)
            diagnostics.append(caught.exception.to_dict())
        self.assertEqual(diagnostics[0], diagnostics[1])
        self.assertEqual(diagnostics[0]["location"], "functions[1].body[3]")
        self.assertEqual(diagnostics[0]["line"], 11)
        self.assertEqual(diagnostics[0]["column"], 5)

    def test_canonical_source_also_obeys_configured_byte_budget(self):
        canonical = canonicalize_source(SAMPLE)
        parsed = parse_source(
            canonical, limits=SourceLimits(max_bytes=len(canonical.encode("utf-8")))
        )
        self.assertEqual(parsed.canonical_source, canonical)
        compact = canonical.replace(") (", ")(")
        with self.assertRaises(A1SourceError) as caught:
            parse_source(compact, limits=SourceLimits(max_bytes=len(compact.encode("utf-8"))))
        self.assertEqual(caught.exception.code, "E_A1_SOURCE_LIMIT")


    def test_inline_composite_operands_require_a_typed_constant(self):
        source = '''(a1src1 (limits 1000 100 20)
          (record Task (title (Text 4)))
          (fn take ((x (List Int 2))) (List Int 2) (return x))
          (fn main () (List Int 2)
            (let result (List Int 2) (call take (list 2 "wrong")))
            (return result)) (entry main))'''
        with self.assertRaises(A1SourceError):
            parse_source(source)
        with self.assertRaises(A1SourceError):
            parse_source(source.replace('(list 2 "wrong")', '(list 2 1)'))
        source = '''(a1src1 (limits 1000 100 20)
          (record Task (title (Text 4)))
          (fn take ((x Task)) Task (return x))
          (fn main () Task (let result Task (call take "scalar"))
            (return result)) (entry main))'''
        with self.assertRaises(A1SourceError):
            parse_source(source)

    def test_parsed_result_protects_semantic_binding_and_source_map(self):
        parsed = parse_source(SAMPLE)
        offered = parsed.module
        offered["functions"][1]["body"][0]["value"] = "tampered"
        self.assertEqual(module_hash(parsed.module), parsed.semantic_hash)
        self.assertTrue(check_source_binding(SAMPLE, parsed.module))
        self.assertFalse(check_source_binding(SAMPLE, offered))
        with self.assertRaises(TypeError):
            parsed.source_map["module"] = parsed.source_map["limits"]


if __name__ == "__main__":
    unittest.main()
