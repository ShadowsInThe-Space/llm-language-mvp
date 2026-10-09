"""Typed query acceptance against actual SQLite, not a D1 emulator."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from llmlang.web.general.codecs import BoolType, IntType, NatType, OptionType, TextType
from llmlang.web.general.queries import (
    Column,
    ConditionalUpdate,
    ConditionNotMet,
    Insert,
    Order,
    Param,
    QueryError,
    Schema,
    SelectList,
    SelectUnique,
    Table,
    compile_query,
    effective_order,
    execute_sqlite,
    schema_sql,
)

MAX = 9007199254740991
TABLE = Table("items", (
    Column("id", TextType(64), primary_key=True),
    Column("title", TextType(32)),
    Column("revision", NatType()),
    Column("score", IntType()),
    Column("done", BoolType()),
))
SCHEMA = Schema((TABLE,))
VALUES = (("id", "one"), ("title", "hello"), ("revision", 0), ("score", -1), ("done", False))


class QueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        for statement in schema_sql(SCHEMA):
            self.db.execute(statement)

    def tearDown(self) -> None:
        self.db.close()

    def insert(self, values: tuple = VALUES) -> None:
        execute_sqlite(self.db, SCHEMA, Insert("items", values, ("id",)))

    def test_immutable_deterministic_explicit_projection_and_positional_bindings(self) -> None:
        query = Insert("items", tuple(reversed(VALUES)), ("id", "done"))
        compiled = compile_query(SCHEMA, query)
        self.assertEqual(compiled.sql, 'INSERT INTO "items" ("id", "title", "revision", '
                         '"score", "done") VALUES (?, ?, ?, ?, ?) RETURNING "id", "done"')
        self.assertEqual(compiled.bind(), ("one", "hello", 0, -1, 0))
        self.assertEqual([column.name for column in compiled.result.columns], ["id", "done"])
        with self.assertRaises(FrozenInstanceError):
            compiled.sql = "DROP TABLE items"  # type: ignore[misc]
        self.assertEqual(compile_query(SCHEMA, query), compiled)

    def test_injection_is_bound_and_roundtrips(self) -> None:
        payload = "'); DROP TABLE items; --"
        values = tuple((name, payload if name == "title" else value) for name, value in VALUES)
        self.insert(values)
        result = execute_sqlite(self.db, SCHEMA, SelectUnique("items", "id", "one", ("title",)))
        self.assertEqual(result.rows, ((payload,),))
        self.assertNotIn(payload, compile_query(SCHEMA, Insert("items", values, ("id",))).sql)

    def test_static_parameter_descriptors_validate_runtime_values(self) -> None:
        compiled = compile_query(SCHEMA, SelectUnique(
            "items", "id", Param("item_id", TextType(64)), ("title",)))
        self.assertEqual(compiled.bind({"item_id": "one"}), ("one",))
        self.assertEqual(compiled.bindings[0].type, TextType(64))
        for params in ({}, {"item_id": 3}, {"item_id": "one", "extra": 1}):
            with self.subTest(params=params), self.assertRaises(QueryError):
                compiled.bind(params)
        with self.assertRaises(QueryError):
            compile_query(SCHEMA, SelectUnique(
                "items", "id", Param("item_id", NatType()), ("title",)))

    def test_schema_closed_identifiers_and_types(self) -> None:
        for name in ('a"; DROP TABLE items;--', "a.b", "", "x" * 65):
            with self.subTest(name=name), self.assertRaises(QueryError):
                Column(name, IntType())
        for query in (SelectUnique("other", "id", "one", ("id",)),
                      SelectUnique("items", "title", "one", ("id",)),
                      SelectUnique("items", "id", "one", ("missing",)),
                      SelectUnique("items", "id", "one", ()),
                      SelectUnique("items", "id", "one", ("id", "id")),
                      Insert("items", VALUES[:-1], ("id",))):
            with self.subTest(query=query), self.assertRaises(QueryError):
                compile_query(SCHEMA, query)

    def test_schema_rejects_case_collisions_nullability_and_mutable_collections(self) -> None:
        invalid = (
            lambda: Schema((Table("Items", TABLE.columns), Table("items", TABLE.columns))),
            lambda: Table("items", (Column("ID", IntType(), primary_key=True),
                                   Column("id", IntType()))),
            lambda: Schema((Table("sqlite_shadow", TABLE.columns),)),
            lambda: Table("items", (Column("id", IntType()),)),
            lambda: Column("nullable", OptionType(TextType(4))),
            lambda: Column("bad_capacity", TextType("1); DROP TABLE items;--")),
            lambda: Schema([TABLE]),
        )
        for create in invalid:
            with self.subTest(create=create), self.assertRaises(QueryError):
                create()

    def test_parameter_revision_overflow_rejects_before_update(self) -> None:
        self.insert()
        query = ConditionalUpdate("items", "id", Param("id", TextType(64)), "revision",
                                  Param("expected", NatType()), (("title", "new"),), ("id",))
        with self.assertRaises(QueryError):
            execute_sqlite(self.db, SCHEMA, query, {"id": "one", "expected": MAX})
        self.assertIsInstance(execute_sqlite(self.db, SCHEMA, query,
                                            {"id": "missing", "expected": 0}), ConditionNotMet)
        self.assertEqual(self.db.execute('SELECT title, revision FROM items').fetchone(),
                         ("hello", 0))

    def test_untrusted_nonunique_database_does_not_silently_pick_row(self) -> None:
        with closing(sqlite3.connect(":memory:")) as other:
            other.execute('CREATE TABLE items (id, title, revision, score, done)')
            other.executemany('INSERT INTO items VALUES (?, ?, ?, ?, ?)',
                              (("one", "a", 0, 0, 0), ("one", "b", 0, 0, 0)))
            with self.assertRaises(QueryError):
                execute_sqlite(other, SCHEMA, SelectUnique("items", "id", "one", ("title",)))

    def test_invalid_literals_fail_before_execution(self) -> None:
        bad = {"title": (None, "🌍" * 9, b"bytes", "\ud800"),
               "revision": (-1, True, MAX + 1), "score": (MAX + 1, -MAX - 1, 1.5, True),
               "done": (0, 1, None, "true")}
        for name, invalid_values in bad.items():
            for value in invalid_values:
                values = tuple((key, value if key == name else old) for key, old in VALUES)
                with self.subTest(name=name, value=repr(value)), self.assertRaises(QueryError):
                    self.insert(values)
        self.assertEqual(self.db.execute('SELECT count(*) FROM "items"').fetchone(), (0,))

    def test_database_checks_match_runtime_boundaries(self) -> None:
        for title, revision, score, done in (("🌍" * 9, 0, 0, 0),
                                             ("nul\0text", 0, 0, 0), ("ok", -1, 0, 0),
                                             ("ok", 0, MAX + 1, 0), ("ok", 0, 0, 2),
                                             ("ok", 0, 1.5, 0), (None, 0, 0, 0)):
            with self.subTest(values=(title, revision, score, done)):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.db.execute('INSERT INTO "items" VALUES (?, ?, ?, ?, ?)',
                                    ("bad", title, revision, score, done))
        values = (("id", "max"), ("title", "🌍" * 8), ("revision", MAX),
                  ("score", -MAX), ("done", True))
        self.insert(values)
        result = execute_sqlite(self.db, SCHEMA, SelectUnique(
            "items", "id", "max", ("title", "revision", "score", "done")))
        self.assertEqual(result.rows, (("🌍" * 8, MAX, -MAX, True),))

    def test_bounded_ordered_listing_has_primary_key_tiebreaker(self) -> None:
        for key in ("c", "a", "b"):
            self.insert(tuple((name, key if name == "id" else value) for name, value in VALUES))
        query = SelectList("items", ("id",), (Order("score", "desc"),), 2, offset=1)
        compiled = compile_query(SCHEMA, query)
        self.assertIn('ORDER BY "score" DESC, "id" ASC LIMIT ? OFFSET ?', compiled.sql)
        self.assertEqual(execute_sqlite(self.db, SCHEMA, query).rows, (("b",), ("c",)))
        for limit, offset in ((0, 0), (1001, 0), (True, 0), (1, -1), (1, 10001)):
            with self.subTest(limit=limit, offset=offset), self.assertRaises(QueryError):
                compile_query(SCHEMA, SelectList("items", ("id",), (Order("id"),), limit, offset))
        with self.assertRaises(QueryError):
            compile_query(SCHEMA, SelectList("items", ("id",), (), 1))

    def test_effective_order_exposes_explicit_columns_and_primary_tiebreaker(self) -> None:
        first = SelectList("items", ("id",), (Order("score", "desc"),), 2)
        self.assertEqual(effective_order(SCHEMA, first), (Order("score", "desc"), Order("id")))
        explicit_key = replace(first, order=(Order("id", "desc"), Order("score")))
        self.assertEqual(effective_order(SCHEMA, explicit_key), explicit_key.order)

    def test_keyset_mixed_order_pages_cover_ties_unicode_bool_and_nat(self) -> None:
        data = (
            ("a", False, 5, 1), ("é", False, 5, 1), ("東京", False, 5, 1),
            ("b", False, 5, 0), ("😀", True, 8, 0), ("α", True, 8, 0),
            ("z", True, 2, 1), ("e", False, 1, 0), ("界", True, 8, 1),
        )
        for key, done, score, revision in data:
            self.insert((("id", key), ("title", "value"), ("revision", revision),
                         ("score", score), ("done", done)))
        first = SelectList("items", ("id", "done", "score", "revision"),
                           (Order("done"), Order("score", "desc"), Order("revision")), 2)
        query = first
        found = []
        sizes = []
        for _ in range(10):
            result = execute_sqlite(self.db, SCHEMA, query)
            if not result.rows:
                break
            found.extend(result.rows)
            sizes.append(len(result.rows))
            last = dict(zip(result.columns, result.rows[-1], strict=True))
            cursor = tuple((order.column, last[order.column])
                           for order in effective_order(SCHEMA, query))
            query = replace(first, cursor=cursor)
        expected = sorted(data, key=lambda row: (row[1], -row[2], row[3], row[0]))
        self.assertEqual(found, expected)
        self.assertEqual(sizes, [2, 2, 2, 2, 1])
        self.assertEqual(len(set(row[0] for row in found)), len(data))

    def test_keyset_predicate_combines_where_and_repeated_positional_values(self) -> None:
        injected = 'é"; DROP TABLE items;--'
        query = SelectList("items", ("id",), (Order("revision", "desc"),), 2,
                           where=(("done", True),),
                           cursor=(("revision", 3), ("id", injected)))
        compiled = compile_query(SCHEMA, query)
        self.assertIn('WHERE "done" = ? AND ("revision" < ? OR '
                      '("revision" = ? AND "id" > ?))', compiled.sql)
        self.assertEqual(compiled.bind(), (1, 3, 3, injected, 2, 0))
        self.assertNotIn(injected, compiled.sql)
        self.assertEqual(compile_query(SCHEMA, query), compiled)

    def test_keyset_where_filter_applies_to_every_or_branch(self) -> None:
        rows = (("a", False, 9), ("b", True, 2), ("c", False, 1),
                ("é", True, 2), ("東京", True, 0), ("z", False, 2))
        for key, done, revision in rows:
            values = dict(VALUES)
            values.update(id=key, done=done, revision=revision)
            self.insert(tuple(values.items()))
        query = SelectList("items", ("id", "revision"), (Order("revision", "desc"),), 10,
                           where=(("done", True),), cursor=(("revision", 2), ("id", "b")))
        self.assertEqual(execute_sqlite(self.db, SCHEMA, query).rows, (("é", 2), ("東京", 0)))

    def test_keyset_static_parameters_bind_each_lexicographic_occurrence(self) -> None:
        query = SelectList("items", ("id",), (Order("done"), Order("revision", "desc")), 2,
                           cursor=(("done", Param("last_done", BoolType())),
                                   ("revision", Param("last_revision", NatType())),
                                   ("id", Param("last_id", TextType(64)))))
        compiled = compile_query(SCHEMA, query)
        values = compiled.bind({"last_done": False, "last_revision": 3, "last_id": "é"})
        self.assertEqual(values, (0, 0, 3, 0, 3, "é", 2, 0))
        self.assertEqual(len(compiled.bindings), compiled.sql.count("?"))
        with self.assertRaises(QueryError):
            compiled.bind({"last_done": 0, "last_revision": 3, "last_id": "é"})

    def test_keyset_rejects_partial_duplicate_reordered_untyped_or_offset_cursor(self) -> None:
        first = SelectList("items", ("id",), (Order("revision", "desc"),), 2)
        invalid = (
            (("revision", 0),), (("id", "one"), ("revision", 0)),
            (("revision", 0), ("revision", 0)), (("revision", 0), ("unknown", "one")),
            (("revision", -1), ("id", "one")), (("revision", True), ("id", "one")),
            (("revision", 0), ("id", None)),
            (("revision", Param("r", IntType())), ("id", "one")),
            (("revision", 0), ("id", Param("i", TextType(63)))),
        )
        for cursor in invalid:
            with self.subTest(cursor=cursor), self.assertRaises(QueryError):
                compile_query(SCHEMA, replace(first, cursor=cursor))
        with self.assertRaises(QueryError):
            compile_query(SCHEMA, replace(first, offset=1, cursor=(("revision", 0), ("id", "one"))))
        with self.assertRaises(QueryError):
            replace(first, cursor=[("revision", 0), ("id", "one")])

    def test_keyset_target_binding_budget_counts_repeated_cursor_and_where_values(self) -> None:
        def wide(count: int, filters: int = 0) -> tuple[Schema, SelectList]:
            names = tuple(f"column_{index}" for index in range(count))
            schema = Schema((Table("wide", tuple(
                Column(name, NatType(), primary_key=index == 0)
                for index, name in enumerate(names)
            )),))
            query = SelectList("wide", names, tuple(Order(name) for name in names), 1,
                where=tuple((names[index], Param(f"filter_{index}", NatType()))
                            for index in range(filters)),
                cursor=tuple((name, Param(f"cursor_{index}", NatType()))
                             for index, name in enumerate(names)))
            return schema, query

        schema, query = wide(13)
        compiled = compile_query(schema, query)
        self.assertEqual(len(compiled.bindings), 93)
        self.assertLessEqual(len(compiled.sql.encode("utf-8")), 100000)
        schema, query = wide(13, 7)
        compiled = compile_query(schema, query)
        params = {binding.value.name: 0 for binding in compiled.bindings
                  if isinstance(binding.value, Param)}
        self.assertEqual(len(compiled.bind(params)), 100)
        for count, filters in ((14, 0), (13, 8)):
            schema, query = wide(count, filters)
            with self.subTest(count=count, filters=filters), self.assertRaises(QueryError):
                compile_query(schema, query)

    def test_descending_primary_key_cursor_has_no_ascending_reorder(self) -> None:
        for key in ("a", "é", "東京", "😀"):
            self.insert(tuple((name, key if name == "id" else value) for name, value in VALUES))
        first = SelectList("items", ("id",), (Order("id", "desc"),), 2)
        self.assertEqual(execute_sqlite(self.db, SCHEMA, first).rows, (("😀",), ("東京",)))
        second = replace(first, cursor=(("id", "東京"),))
        self.assertEqual(execute_sqlite(self.db, SCHEMA, second).rows, (("é",), ("a",)))
        self.assertIn('WHERE ("id" < ?)', compile_query(SCHEMA, second).sql)

    def test_list_equality_predicates_are_bound(self) -> None:
        self.insert()
        query = SelectList("items", ("id",), (Order("id"),), 10, where=(("done", False),))
        self.assertEqual(execute_sqlite(self.db, SCHEMA, query).rows, (("one",),))
        self.assertEqual(compile_query(SCHEMA, query).bind(), (0, 10, 0))

    def test_atomic_conditional_update_returns_row_or_condition_not_met(self) -> None:
        self.insert()
        query = ConditionalUpdate("items", "id", "one", "revision", 0,
                                  (("title", "updated"),), ("title", "revision"))
        self.assertEqual(execute_sqlite(self.db, SCHEMA, query).rows, (("updated", 1),))
        self.assertIsInstance(execute_sqlite(self.db, SCHEMA, query), ConditionNotMet)
        self.assertEqual(self.db.execute('SELECT title, revision FROM items').fetchone(),
                         ("updated", 1))
        self.assertEqual(compile_query(SCHEMA, query).sql,
                         'UPDATE "items" SET "title" = ?, "revision" = "revision" + 1 '
                         'WHERE "id" = ? AND "revision" = ? RETURNING "title", "revision"')
        for changes in ((("revision", 3),), (("id", "new"),), ()):
            with self.assertRaises(QueryError):
                compile_query(SCHEMA, ConditionalUpdate("items", "id", "one", "revision", 0,
                                                        changes, ("id",)))

    def test_concurrent_cas_has_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "db.sqlite")
            with closing(sqlite3.connect(path)) as db, db:
                db.execute(schema_sql(SCHEMA)[0])
                execute_sqlite(db, SCHEMA, Insert("items", VALUES, ("id",)))
            def update(title: str) -> bool:
                with closing(sqlite3.connect(path, timeout=10)) as db, db:
                    query = ConditionalUpdate("items", "id", "one", "revision", 0,
                                              (("title", title),), ("revision",))
                    return not isinstance(execute_sqlite(db, SCHEMA, query), ConditionNotMet)
            with ThreadPoolExecutor(max_workers=2) as pool:
                winners = list(pool.map(update, ("first", "second")))
            self.assertEqual(sorted(winners), [False, True])
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute('SELECT revision FROM items').fetchone(), (1,))

    def test_decoder_rejects_untrusted_null_or_wrong_storage_class(self) -> None:
        other = sqlite3.connect(":memory:")
        try:
            other.execute('CREATE TABLE items (id, title, revision, score, done)')
            for value in (None, b"binary", 4):
                other.execute('DELETE FROM items')
                other.execute('INSERT INTO items VALUES (?, ?, ?, ?, ?)', ("one", value, 0, 0, 0))
                with self.subTest(value=value), self.assertRaises(QueryError):
                    execute_sqlite(other, SCHEMA, SelectUnique("items", "id", "one", ("title",)))
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
