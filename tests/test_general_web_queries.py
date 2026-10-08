"""Typed query acceptance against actual SQLite, not a D1 emulator."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import FrozenInstanceError
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
