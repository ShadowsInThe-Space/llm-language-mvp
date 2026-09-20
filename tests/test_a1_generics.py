from dataclasses import replace

import pytest

from llmlang.a1.generics import (
    Call,
    Function,
    GenericError,
    Limits,
    Program,
    Type,
    map_values,
    monomorphize,
    refine_nat,
)


def fn(name, *, types=(), caps=(), params=(), result=None, calls=()):
    result = result or Type.int()
    return Function(name, tuple(types), tuple(caps), tuple(params), result, tuple(calls))


def generic_map():
    return fn(
        "lib/map",
        types=("t", "u"),
        caps=("n",),
        params=(Type.var("t"),),
        result=Type.var("u"),
    )


def test_used_only_specialization_is_stable_and_keeps_nominal_types_distinct():
    program = Program(
        functions=(
            generic_map(),
            fn(
                "crm/consumer",
                calls=(Call("lib/map", (Type.record("Customer"), Type.record("Label")), (2,)),),
            ),
            fn(
                "orders/consumer",
                calls=(Call("lib/map", (Type.record("Order"), Type.record("Summary")), (4,)),),
            ),
            generic_map().with_name("unused/map"),
        ),
        entrypoints=("crm/consumer", "orders/consumer"),
    )
    first = monomorphize(program)
    second = monomorphize(replace(program, functions=tuple(reversed(program.functions))))
    assert [item.instance_id for item in first] == [item.instance_id for item in second]
    assert len(first) == 4
    assert all("unused/map" not in item.instance_id for item in first)
    assert len({item.instance_id for item in first if item.generic == "lib/map"}) == 2


def test_cycles_fail_closed_before_specialization():
    program = Program(
        functions=(fn("a", calls=(Call("b"),)), fn("b", calls=(Call("a"),))),
        entrypoints=("a",),
    )
    with pytest.raises(GenericError) as error:
        monomorphize(program)
    assert error.value.code == "E_A1_CALL_CYCLE"


@pytest.mark.parametrize("call", [Call("lib/map"), Call("lib/map", (Type.int(),), (1,))])
def test_type_and_capacity_arity_are_explicit(call):
    with pytest.raises(GenericError) as error:
        monomorphize(
            Program(functions=(generic_map(), fn("main", calls=(call,))), entrypoints=("main",))
        )
    assert error.value.code in {"E_A1_TYPE_ARGUMENT", "E_A1_CAPACITY_ARGUMENT"}


def test_negative_nat_requires_reconstructed_evidence():
    with pytest.raises(GenericError) as error:
        refine_nat(-1, evidence=True)
    assert error.value.code == "E_A1_REFINEMENT"
    assert refine_nat(3, evidence=True) == 3


def test_wrong_static_callback_is_rejected():
    helper = fn(
        "lib/map",
        types=("t", "u"),
        caps=("n",),
        params=(Type.var("t"),),
        result=Type.var("u"),
    )
    callback = fn("bad", params=(Type.int(),), result=Type.int())
    call = Call("lib/map", (Type.record("Customer"), Type.record("Label")), (2,), callback="bad")
    with pytest.raises(GenericError) as error:
        monomorphize(
            Program(functions=(helper, callback, fn("main", calls=(call,))), entrypoints=("main",))
        )
    assert error.value.code == "E_A1_CALLBACK_TYPE"


def test_instance_and_iteration_budgets_are_enforced():
    program = Program(
        functions=(
            generic_map(),
            fn(
                "main",
                calls=(
                    Call("lib/map", (Type.record("A"), Type.record("B")), (1,)),
                    Call("lib/map", (Type.record("C"), Type.record("D")), (2,)),
                ),
            ),
        ),
        entrypoints=("main",),
    )
    with pytest.raises(GenericError) as error:
        monomorphize(program, Limits(max_instances=2))
    assert error.value.code == "E_A1_SPECIALIZATION_LIMIT"


def test_map_preserves_order_capacity_and_does_not_mutate_input():
    source = ["a", "b"]
    result = map_values(source, 2, lambda value: value.upper())
    assert result == ["A", "B"]
    assert source == ["a", "b"]
    with pytest.raises(GenericError) as error:
        map_values(["a", "b", "c"], 2, str)
    assert error.value.code == "E_A1_CAPACITY_ARGUMENT"
