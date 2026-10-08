"""RED/GREEN contracts for immutable general WebProgram validation."""

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from llmlang.a1.ir import canonical_bytes
from llmlang.web.general.codecs import (
    MAX_WIRE_BYTES,
    BoolType,
    ListType,
    NatType,
    RecordType,
    TextType,
    max_wire_bytes,
)
from llmlang.web.general.program import (
    ComponentDef,
    ComponentImport,
    ComponentLibrary,
    ComponentUse,
    DetailView,
    DisplayColumn,
    FormView,
    InputField,
    ListView,
    ProgramError,
    ProgramLimits,
    QueryAction,
    Selection,
    ViewStates,
    WebProgram,
    validate_program,
)
from llmlang.web.general.queries import (
    Column,
    ConditionalUpdate,
    Insert,
    Order,
    Param,
    Schema,
    SelectList,
    SelectUnique,
    Table,
)

STATES = ViewStates("Loading", "Failed", "Nothing here", "Ready")


def application(table_name: str = "entries", text_name: str = "title") -> WebProgram:
    schema = Schema((Table(table_name, (
        Column("id", TextType(64), primary_key=True),
        Column(text_name, TextType(32)), Column("done", BoolType()),
        Column("revision", NatType()),
    )),))
    params = (Param("id", TextType(64)), Param(text_name, TextType(32)),
              Param("done", BoolType()))
    actions = (
        QueryAction("save", params, Insert(table_name, (
            ("id", params[0]), (text_name, params[1]), ("done", params[2]), ("revision", 0),
        ), ("id", text_name))),
        QueryAction("list", (), SelectList(table_name, ("id", text_name, "done"),
                                            (Order(text_name),), 20)),
        QueryAction("detail", (Param("selected_id", TextType(64)),),
                    SelectUnique(table_name, "id", Param("selected_id", TextType(64)),
                                 ("id", text_name, "done", "revision"))),
    )
    views = (
        FormView("entry_form", "save", (
            InputField("id", "ID", "input"), InputField(text_name, "Text", "input"),
            InputField("done", "Done", "checkbox"),
        ), STATES),
        ListView("entry_list", "list", (DisplayColumn(text_name, "Text"),), STATES,
                 Selection("entry_detail", "selected_id", "id")),
        DetailView("entry_detail", "detail", (
            DisplayColumn(text_name, "Text"), DisplayColumn("done", "Done"),
        ), STATES),
    )
    return WebProgram("app", "Application", schema, actions, views)


class ProgramTests(unittest.TestCase):
    def rejected(self, program: WebProgram, code: str, **kwargs: object) -> None:
        with self.assertRaises(ProgramError) as raised:
            validate_program(program, **kwargs)  # type: ignore[arg-type]
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(raised.exception.to_dict()["schema"], "diagnostic-v1")

    def test_two_data_models_use_the_same_typed_composition(self) -> None:
        for table, text in (("entries", "title"), ("customers", "name")):
            checked = validate_program(application(table, text))
            self.assertEqual(checked.action("list").compiled.result.cardinality, "bounded")
            self.assertEqual(len(checked.expanded_views), 3)
            self.assertEqual(checked.snapshot()["format"], "web-program-v1")
            self.assertNotIn("sql", checked.snapshot()["actions"][0]["query"])

    def test_effect_graph_is_derived_from_actual_query_nodes_and_transport(self) -> None:
        checked = validate_program(application())
        self.assertEqual(checked.effects.summary("server:save").transitive_effects,
                         frozenset({"db.write"}))
        self.assertEqual(checked.effects.summary("server:list").transitive_effects,
                         frozenset({"db.read"}))
        self.assertTrue(all(not name.startswith("server:")
                            for name in checked.effects.client_reachable))
        self.assertEqual(checked.effects.summary("ui:entry_form").transitive_capabilities,
                         frozenset({"network.call"}))

    def test_action_parameters_are_exact_and_types_match_query_uses(self) -> None:
        original = application()
        save = original.actions[0]
        self.rejected(replace(original, actions=(replace(save, params=save.params[:-1]),
                                                *original.actions[1:])), "W_PROGRAM_ACTION")
        bad = replace(save, params=(Param("id", NatType()), *save.params[1:]))
        self.rejected(replace(original, actions=(bad, *original.actions[1:])), "W_PROGRAM_ACTION")
        bad = replace(save, params=(*save.params, save.params[0]))
        self.rejected(replace(original, actions=(bad, *original.actions[1:])), "W_PROGRAM_ACTION")

    def test_query_params_with_same_name_and_different_types_fail(self) -> None:
        original = application()
        bad = replace(original.actions[0], query=Insert("entries", (
            ("id", Param("same", TextType(64))), ("title", Param("same", TextType(32))),
            ("done", False), ("revision", 0),
        ), ("id",)))
        self.rejected(replace(original, actions=(bad, *original.actions[1:])), "W_PROGRAM_ACTION")

    def test_input_codec_checks_wire_identity_extra_fields_and_exact_integers(self) -> None:
        contract = validate_program(application()).action("save")
        wire = {"record": "saveInput", "fields": {"id": "one", "title": "Hello", "done": False}}
        self.assertEqual(contract.decode_input(wire), wire["fields"])
        for bad in ({**wire, "record": "admin"},
                    {**wire, "fields": {**wire["fields"], "identity.admin": True}},
                    {**wire, "fields": {**wire["fields"], "done": 1}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                contract.decode_input(bad)
        listing = validate_program(application()).action("list")
        self.assertEqual(listing.decode_input({}), {})
        with self.assertRaises(ValueError):
            listing.decode_input({"admin": True})

    def test_output_cardinality_and_projected_types_are_validated(self) -> None:
        checked = validate_program(application())
        row = {"record": "saveRow", "fields": {"id": "one", "title": "Hello"}}
        self.assertEqual(checked.action("save").encode_output(row), row)
        with self.assertRaises(ValueError):
            checked.action("save").encode_output({**row, "fields": {"id": "one"}})
        self.assertEqual(checked.action("detail").encode_output({"tag": "None", "value": None}),
                         {"tag": "None", "value": None})
        with self.assertRaises(ValueError):
            checked.action("list").encode_output({"list": [row] * 21, "capacity": 20})

    def test_forms_bind_every_input_and_controls_follow_scalar_types(self) -> None:
        original = application()
        form = original.views[0]
        for fields in (form.fields[:-1], (*form.fields, form.fields[0]),
                       (*form.fields[:-1], InputField("done", "Done", "input"))):
            self.rejected(replace(original, views=(replace(form, fields=fields),
                                                  *original.views[1:])), "W_PROGRAM_VIEW")
        select = replace(form.fields[1], control="select", choices=(("A", "alpha"),))
        self.assertEqual(len(validate_program(replace(original, views=(
            replace(form, fields=(form.fields[0], select, form.fields[2])), *original.views[1:]
        ))).expanded_views), 3)
        bad = replace(select, choices=(("Wrong", True),))
        self.rejected(replace(original, views=(replace(form, fields=(form.fields[0], bad,
                           form.fields[2])), *original.views[1:])), "W_PROGRAM_VIEW")

    def test_list_and_detail_columns_are_explicit_projected_fields(self) -> None:
        original = application()
        for columns in ((), (DisplayColumn("missing", "Missing"),),
                        (DisplayColumn("title", "Text"), DisplayColumn("title", "Again"))):
            self.rejected(replace(original, views=(original.views[0],
                           replace(original.views[1], columns=columns), original.views[2])),
                          "W_PROGRAM_VIEW")

    def test_selection_requires_unique_action_exact_param_and_matching_table_key(self) -> None:
        original = application()
        for selection in (Selection("missing", "selected_id", "id"),
                          Selection("entry_detail", "wrong", "id"),
                          Selection("entry_detail", "selected_id", "title")):
            self.rejected(replace(original, views=(original.views[0],
                           replace(original.views[1], selection=selection), original.views[2])),
                          "W_PROGRAM_VIEW")
        self.rejected(replace(original, views=(original.views[0],
                       replace(original.views[1], action="detail"), original.views[2])),
                      "W_PROGRAM_VIEW")

    def test_nonempty_identifiers_labels_states_and_auth_policies(self) -> None:
        original = application()
        self.rejected(replace(original, name="x'; DROP TABLE entries;--"), "W_PROGRAM_BINDING")
        self.rejected(replace(original, title=""), "W_PROGRAM_VIEW")
        self.rejected(replace(original, views=(replace(original.views[0], states=
                      replace(STATES, error="")), *original.views[1:])), "W_PROGRAM_VIEW")
        bad = replace(original.actions[0], authorization="browser_admin")
        self.rejected(replace(original, actions=(bad, *original.actions[1:])), "W_PROGRAM_ACTION")

    def test_admin_declaration_requires_server_authority_and_cannot_leak_into_ui(self) -> None:
        original = application()
        protected = replace(original.actions[0], authorization="admin")
        checked = validate_program(replace(original, actions=(protected, *original.actions[1:])))
        self.assertIn(
            "identity.admin", checked.effects.summary("server:save").transitive_capabilities
        )
        self.assertNotIn("identity.admin", json.dumps(checked.snapshot()["expanded_views"]))

    def test_components_require_explicit_imports_and_expand_generically(self) -> None:
        original = application()
        library = ComponentLibrary("widgets", (ComponentDef("edit", (original.views[0],)),))
        program = replace(original, views=(ComponentUse("editor"), *original.views[1:]),
                          libraries=(library,), imports=(ComponentImport(
                              "widgets", "edit", "editor"),))
        self.assertEqual(validate_program(program).expanded_views, original.views)
        self.rejected(replace(program, imports=()), "W_PROGRAM_BINDING")
        self.rejected(replace(program, imports=(ComponentImport("widgets", "missing", "editor"),)),
                      "W_PROGRAM_BINDING")

    def test_component_cycles_and_expansion_budget_are_rejected(self) -> None:
        original = application()
        cyclic = replace(original, components=(ComponentDef("a", (ComponentUse("b"),)),
                                                ComponentDef("b", (ComponentUse("a"),))))
        self.rejected(cyclic, "W_PROGRAM_COMPONENT")
        self.rejected(original, "W_PROGRAM_LIMIT", limits=ProgramLimits(max_nodes=2))

    def test_deep_immutability_and_canonical_snapshot_hash(self) -> None:
        original = application()
        checked = validate_program(original)
        with self.assertRaises(FrozenInstanceError):
            checked.semantic_hash = "fake"  # type: ignore[misc]
        copy = checked.snapshot()
        copy["title"] = "Tampered"
        self.assertEqual(checked.snapshot()["title"], "Application")
        self.assertEqual(checked.semantic_hash, validate_program(original).semantic_hash)
        self.assertNotEqual(
            checked.semantic_hash, validate_program(replace(original, title="New")).semantic_hash
        )
        self.rejected(replace(original, actions=list(original.actions)), "W_PROGRAM_BINDING")
        self.rejected(checked, "W_PROGRAM_BINDING")  # type: ignore[arg-type]

    def test_validated_pure_library_is_bound_as_provenance_without_claiming_calls(self) -> None:
        original = application()
        pure = {"format": "a1-ir-v1", "profile": "a1", "checker": "a1-check-v1", "types": [],
                "functions": [{"name": "identity", "params": [{"name": "x", "type": "Int"}],
                               "result": "Int", "body": [], "return": "x"}],
                "specializations": [], "entrypoints": ["identity"],
                "limits": {"max_steps": 100, "max_collection_expansion": 10, "max_call_depth": 8}}
        checked = validate_program(replace(original, pure_library=canonical_bytes(pure)))
        self.assertIn("ir_hash", checked.snapshot()["pure_library"])
        self.assertNotEqual(checked.semantic_hash, validate_program(original).semantic_hash)
        self.assertNotIn("proved", json.dumps(checked.snapshot()))
        self.rejected(replace(original, pure_library=b'{"format":"fake"}'), "W_PROGRAM_PURE")
        self.rejected(replace(original, pure_library=json.dumps(pure).encode()), "W_PROGRAM_PURE")

    def test_conditional_update_contract_preserves_revision_checks(self) -> None:
        original = application()
        action = QueryAction("update", (Param("id", TextType(64)), Param("expected", NatType()),
                                         Param("title", TextType(32))),
                             ConditionalUpdate("entries", "id", Param("id", TextType(64)),
                                               "revision", Param("expected", NatType()),
                                               (("title", Param("title", TextType(32))),), ("id",)))
        contract = validate_program(
            replace(original, actions=(*original.actions, action))
        ).action("update")
        self.assertEqual(contract.compiled.result.cardinality, "conditional")
        with self.assertRaises(ValueError):
            contract.validate_inputs({"id": "one", "title": "Hello", "expected": 9007199254740991})

    def test_malformed_nested_view_fields_have_structured_diagnostics(self) -> None:
        original = application()
        malformed = DisplayColumn(["title"], "Text")  # type: ignore[arg-type]
        self.rejected(replace(original, views=(original.views[0],
                      replace(original.views[1], columns=(malformed,)), original.views[2])),
                      "W_PROGRAM_BINDING")

    def test_empty_component_library_cannot_advertise_a_definition(self) -> None:
        self.rejected(replace(application(), libraries=(ComponentLibrary("empty", ()),)),
                      "W_PROGRAM_COMPONENT")

    def test_legal_query_results_must_fit_worst_case_wire_response(self) -> None:
        original = application()
        action = replace(original.actions[1], query=replace(original.actions[1].query, limit=100))
        bad = replace(original, actions=(original.actions[0], action, original.actions[2]))
        with self.assertRaises(ProgramError) as raised:
            validate_program(bad)
        self.assertEqual(raised.exception.code, "W_PROGRAM_LIMIT")
        self.assertEqual(raised.exception.path, "actions.list.output")

    def test_closed_action_input_envelope_is_part_of_the_transport_budget(self) -> None:
        name, param_name, type_ = "a" * 64, "p" * 64, TextType(5420)
        input_codec = RecordType(name + "Input", ((param_name, type_),))
        self.assertLessEqual(max_wire_bytes(input_codec), MAX_WIRE_BYTES)
        overhead = len(json.dumps({"action": name, "input": None}, separators=(",", ":"))) - 4
        self.assertGreater(max_wire_bytes(input_codec) + overhead, MAX_WIRE_BYTES)
        schema = Schema((Table("entries", (Column("id", type_, primary_key=True),)),))
        action = QueryAction(name, (Param(param_name, type_),),
                             Insert("entries", (("id", Param(param_name, type_)),), ("id",)))
        form = FormView("form", name, (InputField(param_name, "ID"),), STATES)
        with self.assertRaises(ProgramError) as raised:
            validate_program(WebProgram("app", "Application", schema, (action,), (form,)))
        self.assertEqual(raised.exception.code, "W_PROGRAM_LIMIT")
        self.assertEqual(raised.exception.path, "actions." + name + ".input")

    def test_unused_component_selection_must_resolve_in_declared_view_namespace(self) -> None:
        original = application()
        bad = replace(original.views[1], name="unused_list",
                      selection=Selection("nonexistent_detail", "selected_id", "id"))
        self.rejected(replace(original, components=(ComponentDef("unused", (bad,)),)),
                      "W_PROGRAM_VIEW")

    def test_unused_component_can_select_a_detail_declared_in_a_sibling(self) -> None:
        original = application()
        browser = ComponentDef("browser", (original.views[1],))
        detail = ComponentDef("details", (original.views[2],))
        program = replace(original, components=(browser, detail),
                          views=(original.views[0], ComponentUse("browser"),
                                 ComponentUse("details")))
        self.assertEqual(validate_program(program).expanded_views, original.views)

    def test_wide_result_fits_bytes_but_exceeds_wire_json_node_budget(self) -> None:
        columns = tuple(Column("f" + str(index), BoolType()) for index in range(31))
        schema = Schema((Table("items", (Column("id", NatType(), primary_key=True),
                                         *columns)),))
        query = SelectList("items", tuple(column.name for column in columns), (Order("id"),), 80)
        action = QueryAction("list", (), query)
        view = ListView("items", "list", (DisplayColumn("f0", "Flag"),), STATES)
        program = WebProgram("app", "Application", schema, (action,), (view,))
        # The legal maximum response is 31,521 ASCII bytes, below the 32 KiB cap.
        output = ListType(RecordType("listRow", tuple((column.name, column.type)
                                                     for column in columns)), 80)
        self.assertLessEqual(max_wire_bytes(output), MAX_WIRE_BYTES)
        with self.assertRaises(ProgramError) as raised:
            validate_program(program)
        self.assertEqual(raised.exception.code, "W_PROGRAM_LIMIT")
        self.assertEqual(raised.exception.path, "actions.list.output")


if __name__ == "__main__":
    unittest.main()
