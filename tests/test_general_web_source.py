"""Source, shared-library and query behavior contracts for general web programs."""

import sqlite3
import unittest
from copy import deepcopy
from dataclasses import replace

from llmlang.web.general.queries import Rows, execute_sqlite, schema_sql
from llmlang.web.general.source import (
    WebSourceError,
    WebSourceLimits,
    canonicalize_web_source,
    check_web_source_binding,
    lower_web_source,
    parse_component_library,
    parse_web_source,
)

UI = '''(webuilib1 common
  (component editor
    (form edit save (fields (id "ID" input) (title "Text" input))
      (states "Loading" "Failed" "Empty" "Saved") (buttons "Save" "Clear")))
  (component browser
    (list listing browse (columns (title "Text"))
      (states "Loading" "Failed" "Empty" "Ready")
      (select detail selected_id id))
    (detail detail fetch (columns (title "Text"))
      (states "Loading" "Failed" "Empty" "Ready"))))'''


def application(table="entries", title="History", extra="", values=""):
    return f'''(websrc1 app "{title}"
      (schema (table {table} (id (Text 64) primary) (title (Text 32))
        (revision Nat) {extra}))
      (action save ((id (Text 64)) (title (Text 32))) public
        (insert {table} (values (id id) (title title) (revision 0) {values})
          (project id title)))
      (action browse () public
        (select_list {table} (project id title) (order (title asc))
          (limit 20) (offset 0) (where)))
      (action fetch ((selected_id (Text 64))) public
        (select_unique {table} id selected_id (project id title revision)))
      (library common)
      (import common editor editor)
      (import common browser browser)
      (use editor) (use browser))'''


class WebSourceTests(unittest.TestCase):
    def test_two_programs_share_one_real_library_and_execute_typed_queries(self):
        sources = [application(), application("tasks", "Planner", "(done Bool)", "(done false)")]
        for source in sources:
            with self.subTest(source=source):
                parsed = parse_web_source(source, library_sources={"common": UI})
                self.assertEqual(len(parsed.checked.expanded_views), 3)
                connection = sqlite3.connect(":memory:")
                try:
                    for ddl in schema_sql(parsed.program.schema):
                        connection.execute(ddl)
                    row = execute_sqlite(connection, parsed.program.schema,
                                         parsed.program.actions[0].query,
                                         {"id": "one", "title": "é"})
                    self.assertEqual(row, Rows(("id", "title"), (("one", "é"),)))
                    rows = execute_sqlite(connection, parsed.program.schema,
                                          parsed.program.actions[1].query)
                    self.assertEqual(rows.rows, (("one", "é"),))
                finally:
                    connection.close()
        first = parse_web_source(sources[0], library_sources={"common": UI})
        second = parse_web_source(sources[1], library_sources={"common": UI})
        self.assertEqual(first.program.libraries, second.program.libraries)

    def test_canonical_roundtrip_and_bound_snapshot_are_independent(self):
        source = application()
        parsed = parse_web_source(source, library_sources={"common": UI})
        canonical = canonicalize_web_source(source, library_sources={"common": UI})
        repeated = parse_web_source(canonical, library_sources={"common": UI})
        self.assertEqual(parsed.program, repeated.program)
        self.assertEqual(parsed.semantic_hash, repeated.semantic_hash)
        self.assertEqual(parsed.source_hash, repeated.source_hash)
        self.assertTrue(check_web_source_binding(
            source, parsed.program, library_sources={"common": UI}
        ))
        self.assertTrue(check_web_source_binding(source, parsed.checked.snapshot(),
                                                library_sources={"common": UI}))
        self.assertFalse(check_web_source_binding(source, replace(parsed.program, title="Tampered"),
                                                 library_sources={"common": UI}))
        offered = deepcopy(parsed.checked.snapshot())
        offered["source_hash"] = parsed.source_hash
        self.assertFalse(check_web_source_binding(source, offered, library_sources={"common": UI}))
        changed_ui = UI.replace('"Saved"', '"Changed"')
        self.assertFalse(check_web_source_binding(source, parsed.program,
                                                 library_sources={"common": changed_ui}))

    def test_library_source_snapshot_and_original_positions(self):
        library = parse_component_library(UI)
        repeated = parse_component_library(library.canonical_source)
        self.assertEqual(library.library, repeated.library)
        self.assertEqual(library.source_hash, repeated.source_hash)
        self.assertEqual(library.source_map["definitions[0]"].line, 2)
        parsed = parse_web_source(application(), library_sources={"common": UI})
        self.assertEqual(parsed.source_map["actions[0]"].line, 4)
        self.assertEqual(parsed.source_map["libraries.common.definitions[0]"].line, 2)
        with self.assertRaises(TypeError):
            parsed.source_map["actions[0]"] = parsed.source_map["module"]

    def test_closed_forms_types_parameters_and_libraries_fail_closed(self):
        base = application()
        invalid = [
            base.replace("websrc1", "websrc2"), base + " (use editor)",
            base.replace("(title title)", '(title "too long for capacity" extra)'),
            base.replace("(Text 32)", "(Text 32 extra)"),
            base.replace("(revision Nat)", "(revision Float)"),
            base.replace("(revision 0)", "(revision missing)"),
            base.replace("public", "browser_admin"),
            base.replace("(use editor)", '(python "print(1)")'),
            base.replace("(use editor)", '(sql "DELETE FROM entries")'),
            base.replace("(use editor)", '(typescript "fetch(1)")'),
            base.replace("(import common editor editor)", "(import common nope editor)"),
            base.replace("(library common)", "(library common) (library common)"),
        ]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(WebSourceError) as raised:
                parse_web_source(source, library_sources={"common": UI})
            self.assertTrue(raised.exception.code.startswith("W_SOURCE_"))
        for libraries in ({}, {"common": UI.replace("webuilib1 common", "webuilib1 other")},
                          {"common": UI, "unused": UI}):
            with self.assertRaises(WebSourceError):
                parse_web_source(base, library_sources=libraries)

    def test_conditional_update_select_controls_and_local_components(self):
        source = '''(websrc1 local "Local"
          (schema (table entries (id (Text 64) primary) (title (Text 32)) (revision Nat)))
          (action edit ((id (Text 64)) (expected Nat) (title (Text 32))) authenticated
            (conditional_update entries id id revision expected
              (values (title title)) (project id title revision)))
          (component editor
            (form edit_form edit
              (fields (id "ID" input) (expected "Revision" input)
                (title "Title" select (choice "First" "one") (choice "Second" "two")))
              (states "Loading" "Failed" "Empty" "Saved") (buttons "Update" "Reset")))
          (use editor))'''
        parsed = parse_web_source(source)
        self.assertEqual(parsed.checked.action("edit").compiled.result.cardinality, "conditional")
        self.assertEqual(parsed.checked.expanded_views[0].fields[-1].choices,
                         (("First", "one"), ("Second", "two")))
        self.assertEqual(lower_web_source(source), parsed.program)

    def test_reader_budgets_unicode_and_expansion_fail_closed(self):
        base = application()
        for source, limits in (
            (base, WebSourceLimits(max_bytes=10)),
            (base, WebSourceLimits(max_nodes=5)),
            ("(" * 33 + ")" * 33, WebSourceLimits()),
            (base.replace("History", r"\ud800"), WebSourceLimits()),
            (base.replace("History", r"\u0000"), WebSourceLimits()),
            (base.replace("History", "\x00"), WebSourceLimits()),
            (base.replace("20", "9" * 17), WebSourceLimits()),
        ):
            with self.subTest(source=source), self.assertRaises(WebSourceError):
                parse_web_source(source, limits=limits, library_sources={"common": UI})
        with self.assertRaises(WebSourceError):
            parse_web_source(base.replace("(use editor)", "(use editor) (use editor)"),
                             library_sources={"common": UI})


    def test_library_cycles_are_rejected_before_application_linking(self):
        with self.assertRaises(WebSourceError):
            parse_component_library("(webuilib1 ui (component a (use b)) (component b (use a)))")

    def test_pure_source_library_binding_and_combined_resource_limits(self):
        pure = '''(a1src1 (limits 100 10 8)
          (fn identity ((x Int)) Int (return x)) (entry identity))'''
        source = application().replace(
            "(library common)", "(pure_library helpers) (library common)"
        )
        parsed = parse_web_source(
            source, library_sources={"common": UI}, pure_sources={"helpers": pure}
        )
        self.assertEqual(parsed.checked.snapshot()["pure_library"]["role"], "provenance_only")
        self.assertFalse(check_web_source_binding(
            source, parsed.program, library_sources={"common": UI},
            pure_sources={"helpers": pure.replace("100", "101")}
        ))
        with self.assertRaises(WebSourceError):
            parse_web_source(source, library_sources={"common": UI}, pure_sources={"helpers": pure},
                             limits=WebSourceLimits(max_bytes=len(source.encode("utf-8")) + 1))
        with self.assertRaises(WebSourceError):
            parse_web_source(source, library_sources={"common": UI}, pure_sources={"helpers": pure},
                             limits=WebSourceLimits(max_nodes=200))


    def test_explicit_action_transforms_roundtrip_and_bind_pure_library(self):
        pure = '''(a1src1 (limits 100 10 8)
          (fn preview ((text (Text 32))) (Text 32)
            (let count Nat (const 2))
            (let result (Text 32) (text_prefix_codepoints text count)) (return result))
          (fn identity ((text (Text 32))) (Text 32) (return text))
          (entry preview) (entry identity))'''
        source = application().replace(
            "(project id title)))",
            "(project id title)) (transform title preview (title)))", 1,
        ).replace("(library common)", "(pure_library helpers) (library common)")
        options = {"library_sources": {"common": UI}, "pure_sources": {"helpers": pure}}
        parsed = parse_web_source(source, **options)
        transform = parsed.program.actions[0].transforms[0]
        self.assertEqual((transform.param, transform.function, transform.args),
                         ("title", "preview", ("title",)))
        self.assertEqual(parsed.checked.snapshot()["pure_library"]["role"], "executable")
        self.assertEqual(parsed.checked.snapshot()["actions"][0]["transforms"],
                         [{"param": "title", "function": "preview", "args": ["title"]}])
        repeated = parse_web_source(parsed.canonical_source, **options)
        self.assertEqual(repeated.program, parsed.program)
        self.assertEqual(repeated.source_hash, parsed.source_hash)
        self.assertTrue(check_web_source_binding(source, parsed.program, **options))
        offered = parsed.checked.snapshot()
        offered["actions"][0]["transforms"][0]["function"] = "identity"
        self.assertFalse(check_web_source_binding(source, offered, **options))
        alternate = source.replace("(transform title preview", "(transform title identity")
        self.assertFalse(check_web_source_binding(alternate, parsed.program, **options))
        self.assertNotEqual(parse_web_source(alternate, **options).source_hash, parsed.source_hash)
        self.assertEqual(parsed.source_map["actions[0].transforms[0]"].line, 6)

    def test_transform_syntax_and_semantics_fail_closed(self):
        pure = '''(a1src1 (limits 100 10 8)
          (fn preview ((text (Text 32))) (Text 32) (return text)) (entry preview))'''
        source = application().replace(
            "(project id title)))",
            "(project id title)) (transform title preview (title)))", 1,
        ).replace("(library common)", "(pure_library helpers) (library common)")
        bad_forms = (
            "(transform title preview title)",
            "(transform title preview (title) extra)",
            "(javascript title preview (title))",
            "(transform title preview (\"title\"))",
            "(transform missing preview (title))",
            "(transform title missing (title))",
            "(transform title preview (missing))",
            "(transform title preview ())",
            "(transform title preview (title title))",
            "(transform title preview (id))",
            "(transform title preview (title)) (transform title preview (title))",
        )
        for form in bad_forms:
            invalid = source.replace("(transform title preview (title))", form)
            with self.subTest(form=form), self.assertRaises(WebSourceError):
                parse_web_source(invalid, library_sources={"common": UI},
                                 pure_sources={"helpers": pure})
        with self.assertRaises(WebSourceError):
            parse_web_source(source.replace("(pure_library helpers)", ""),
                             library_sources={"common": UI})
        with self.assertRaises(WebSourceError):
            parse_web_source(source, library_sources={"common": UI},
                             pure_sources={"helpers": pure.replace("(entry preview)", "")})


if __name__ == "__main__":
    unittest.main()
