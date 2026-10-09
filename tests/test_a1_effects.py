"""Behavioral RED/GREEN contracts for the additive M3 effects boundary (#21)."""

import unittest
from dataclasses import FrozenInstanceError, replace

from llmlang.a1.effects import (
    EffectError,
    EffectFunction,
    EffectLimits,
    check_effect_graph,
)


def function(
    name: str,
    location: str = "server",
    effects: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    calls: tuple[str, ...] = (),
    host_calls: tuple[str, ...] = (),
) -> EffectFunction:
    return EffectFunction(name, location, frozenset(effects), frozenset(capabilities),
                          calls, host_calls)  # type: ignore[arg-type]


class EffectTests(unittest.TestCase):
    def rejected(
        self, functions: list[EffectFunction], code: str, path: tuple[str, ...],
        **kwargs: object,
    ) -> None:
        with self.assertRaises(EffectError) as raised:
            check_effect_graph(functions, **kwargs)  # type: ignore[arg-type]
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(raised.exception.path, path)
        self.assertEqual(raised.exception.to_diagnostic()["schema"], "diagnostic-v1")
        self.assertEqual(raised.exception.to_diagnostic()["phase"], "validate")

    def test_pure_function_cannot_perform_host_effect(self) -> None:
        self.rejected([function("pure", host_calls=("db.write",))], "E_A1_EFFECT",
                      ("functions", "pure", "host_calls", "0"))

    def test_client_cannot_write_even_with_declared_permission(self) -> None:
        self.rejected([function("write", "client", ("db.write",), ("db.write",),
                                host_calls=("db.write",))], "E_A1_LOCATION",
                      ("functions", "write", "host_calls", "0"))

    def test_client_cannot_hold_trusted_identity_without_using_it(self) -> None:
        for capability in ("identity.authenticated", "identity.admin", "db.read", "db.write"):
            with self.subTest(capability=capability):
                self.rejected([function("client", "client", capabilities=(capability,))],
                              "E_A1_CAPABILITY", ("functions", "client", "capabilities"))

    def test_missing_host_capability_is_rejected(self) -> None:
        self.rejected([function("read", effects=("db.read",), host_calls=("db.read",))],
                      "E_A1_CAPABILITY", ("functions", "read", "host_calls", "0"))

    def test_transitive_calls_cannot_hide_effects(self) -> None:
        read = function("read", effects=("db.read",), capabilities=("db.read",),
                        host_calls=("db.read",))
        middle = function("middle", effects=("db.read",), capabilities=("db.read",),
                          calls=("read",))
        self.rejected([function("outer", calls=("middle",)), middle, read],
                      "E_A1_EFFECT", ("functions", "outer", "calls", "0"))

    def test_capability_subset_is_transitive_and_distinct_from_effects(self) -> None:
        leaf = function("leaf", capabilities=("identity.admin",))
        middle = function("middle", capabilities=("identity.admin",), calls=("leaf",))
        self.rejected([function("outer", calls=("middle",)), middle, leaf],
                      "E_A1_CAPABILITY", ("functions", "outer", "calls", "0"))

    def test_shared_must_be_pure_and_only_call_shared(self) -> None:
        self.rejected([function("shared", "shared", effects=("clock.read",))],
                      "E_A1_LOCATION", ("functions", "shared", "location"))
        self.rejected([function("shared", "shared", calls=("server",)), function("server")],
                      "E_A1_LOCATION", ("functions", "shared", "calls", "0"))

    def test_cross_location_calls_rejected(self) -> None:
        for source, target in (("client", "server"), ("server", "client")):
            with self.subTest(source=source):
                self.rejected([function("source", source, calls=("target",)),
                               function("target", target)], "E_A1_LOCATION",
                              ("functions", "source", "calls", "0"))

    def test_closed_registry_and_names(self) -> None:
        cases = [
            (function("bad", effects=("pure",)), "E_A1_EFFECT", "effects"),
            (function("bad", effects=("filesystem.read",)), "E_A1_EFFECT", "effects"),
            (function("bad", capabilities=("root",)), "E_A1_CAPABILITY", "capabilities"),
            (function("bad", host_calls=("custom.db",)), "E_A1_EFFECT", "host_calls", "0"),
            (function("bad", "browser"), "E_A1_LOCATION", "location"),
            (function("bad", calls=("missing",)), "E_A1_BINDING", "calls", "0"),
        ]
        for item, code, *tail in cases:
            with self.subTest(code=code, tail=tail):
                self.rejected([item], code, ("functions", "bad", *tail))

    def test_cycles_and_duplicate_functions_fail_closed(self) -> None:
        self.rejected([function("a", calls=("b",)), function("b", calls=("a",))],
                      "E_A1_CONTROL", ("functions", "a", "calls"))
        self.rejected([function("a"), function("a")], "E_A1_BINDING",
                      ("functions", "a", "name"))

    def test_diagnostics_do_not_depend_on_set_iteration(self) -> None:
        bad = function("bad", effects=("zzz", "aaa"))
        messages = []
        for _ in range(5):
            with self.assertRaises(EffectError) as raised:
                check_effect_graph([bad])
            messages.append(str(raised.exception))
        self.assertEqual(len(set(messages)), 1)
        self.assertIn("aaa", messages[0])

    def test_valid_graph_has_immutable_summaries_and_partition(self) -> None:
        functions = [
            function("helper", "shared"),
            function("ui", "client", ("network.call",), ("network.call",),
                     calls=("helper",), host_calls=("network.call",)),
            function("write", effects=("db.write",),
                     capabilities=("db.write", "identity.admin"), calls=("helper",),
                     host_calls=("db.write",)),
        ]
        report = check_effect_graph(functions, client_entries=("ui",), server_entries=("write",))
        self.assertEqual(report.client_reachable, frozenset(("ui", "helper")))
        self.assertEqual(report.server_reachable, frozenset(("write", "helper")))
        self.assertEqual(report.summary("write").transitive_effects, frozenset(("db.write",)))
        self.assertEqual(report.summary("write").transitive_capabilities,
                         frozenset(("db.write", "identity.admin")))
        self.assertEqual(report.to_dict()["status"], "checked")
        with self.assertRaises(FrozenInstanceError):
            report.semantic_hash = "fake"  # type: ignore[misc]

    def test_hash_canonicalizes_sets_but_binds_graph_and_entries(self) -> None:
        original = function("f", effects=("clock.read", "network.call"),
                            capabilities=("clock.read", "network.call"))
        first = check_effect_graph([original]).semantic_hash
        reordered = replace(original, effects=frozenset(("network.call", "clock.read")))
        self.assertEqual(first, check_effect_graph([reordered]).semantic_hash)
        for changed in (replace(original, location="client"),
                        replace(original, effects=frozenset(("clock.read",))),
                        replace(original, capabilities=original.capabilities | {"identity.admin"}),
                        replace(original, host_calls=("clock.read",))):
            self.assertNotEqual(first, check_effect_graph([changed]).semantic_hash)
        self.assertNotEqual(
            first, check_effect_graph([original], server_entries=("f",)).semantic_hash
        )

    def test_entries_are_validated_against_location(self) -> None:
        self.rejected([function("server")], "E_A1_LOCATION", ("client_entries", "0"),
                      client_entries=("server",))
        self.rejected([function("server")], "E_A1_BINDING", ("server_entries", "0"),
                      server_entries=("missing",))

    def test_explicit_structural_budgets_and_invalid_mutable_fields(self) -> None:
        self.rejected([function("a"), function("b")], "E_A1_LIMIT", ("functions",),
                      limits=EffectLimits(max_functions=1))
        self.rejected([function("a", calls=("b",)), function("b")], "E_A1_LIMIT",
                      ("functions",), limits=EffectLimits(max_edges=0))
        self.rejected([function("a", calls=("b",)), function("b", calls=("c",)),
                       function("c")], "E_A1_LIMIT", ("functions", "a", "calls"),
                      limits=EffectLimits(max_call_depth=2))
        bad = replace(function("a"), effects=["db.write"])  # type: ignore[arg-type]
        self.rejected([bad], "E_A1_EFFECT", ("functions", "a", "effects"))


if __name__ == "__main__":
    unittest.main()
