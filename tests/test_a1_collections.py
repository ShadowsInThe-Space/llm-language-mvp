"""Executable A1 contract tests for bounded collections and text values."""

import unicodedata

import pytest

from llmlang.a1.collections import (
    A1CollectionBudget,
    A1CollectionError,
    BoundedList,
    BoundedText,
    CapacityError,
    option_none,
    option_some,
    result_err,
    result_ok,
)


def test_empty_and_full_bounded_lists_preserve_capacity_and_order() -> None:
    empty = BoundedList.empty(0)
    assert empty.capacity == 0
    assert empty.length == 0
    assert empty.to_tuple() == ()
    full = BoundedList.from_values(["a", "b"], capacity=2)
    assert full.length == 2
    assert tuple(full) == ("a", "b")
    assert full.canonical() == {
        "kind": "list",
        "capacity": 2,
        "values": ["a", "b"],
    }


def test_list_rejects_invalid_capacity_and_overflow_without_truncating() -> None:
    with pytest.raises(A1CollectionError) as negative:
        BoundedList.empty(-1)
    assert negative.value.code == "A1_TYPE_CAPACITY"
    with pytest.raises(A1CollectionError) as overflow:
        BoundedList.from_values([1, 2, 3], capacity=2)
    assert overflow.value.code == "A1_LIST_BOUNDS"
    full = BoundedList.from_values([1], capacity=1)
    assert full.append(2) == result_err(CapacityError.CapacityExceeded)
    assert full.to_tuple() == (1,)


def test_index_is_option_and_does_not_read_capacity_slots() -> None:
    values = BoundedList.from_values(["x"], capacity=4)
    assert values.index(0) == option_some("x")
    assert values.index(1) == option_none()
    assert values.index(100) == option_none()
    assert values.index(1).canonical() == {"tag": "None"}
    with pytest.raises(A1CollectionError, match="Nat"):
        values.index(-1)


def test_map_and_fold_are_left_to_right_and_budgeted() -> None:
    seen: list[int] = []
    values = BoundedList.from_values([1, 2, 3], capacity=5)
    mapped = values.map(lambda value: seen.append(value) or value * 2)
    assert mapped.to_tuple() == (2, 4, 6)
    assert seen == [1, 2, 3]
    folded = values.fold(0, lambda accumulator, value: accumulator * 10 + value)
    assert folded == 123
    assert BoundedList.empty(5).fold("init", lambda *_: pytest.fail("called")) == "init"
    with pytest.raises(A1CollectionError) as budget:
        values.map(lambda value: value, budget=A1CollectionBudget(max_collection_steps=2))
    assert budget.value.code == "A1_BUDGET"
    assert budget.value.phase == "resource"


def test_collection_budget_checks_capacity_before_work() -> None:
    with pytest.raises(A1CollectionError) as error:
        BoundedList.empty(3).map(lambda item: item, budget=A1CollectionBudget(max_list_capacity=2))
    assert error.value.code == "A1_BUDGET"


def test_text_uses_utf8_bytes_and_keeps_unicode_without_normalization() -> None:
    value = BoundedText("e\u0301😀", max_bytes=7)
    assert value.utf8_bytes == len("e\u0301😀".encode("utf-8")) == 7
    assert value.codepoint_count == 3
    assert value.value == "e\u0301😀"
    assert value.canonical() == {
        "kind": "text",
        "max_bytes": 7,
        "utf8_hex": "65cc81f09f9880",
    }
    assert value.value != unicodedata.normalize("NFC", value.value)
    assert value.prefix_codepoints(2).value == "e\u0301"
    assert value.prefix_codepoints(99).value == value.value


@pytest.mark.parametrize(
    ("value", "capacity", "code"),
    [
        ("😀", 3, "A1_TEXT_CAPACITY"),
        ("a\x00b", 3, "A1_TEXT_NUL"),
        ("\ud800", 3, "A1_TEXT_ENCODING"),
    ],
)
def test_text_rejects_nul_surrogates_and_byte_overflow(
    value: str, capacity: int, code: str
) -> None:
    with pytest.raises(A1CollectionError) as error:
        BoundedText(value, max_bytes=capacity)
    assert error.value.code == code


def test_text_from_utf8_is_strict_and_reports_invalid_sequences() -> None:
    with pytest.raises(A1CollectionError) as error:
        BoundedText.from_utf8(b"\xc0\xaf", max_bytes=2)
    assert error.value.code == "A1_TEXT_ENCODING"
    with pytest.raises(A1CollectionError) as error:
        BoundedText.from_utf8(b"a\x00", max_bytes=2)
    assert error.value.code == "A1_TEXT_NUL"
    assert BoundedText.from_utf8("é".encode(), max_bytes=2).raw_bytes == b"\xc3\xa9"


def test_text_prefix_is_scalar_safe_and_concat_keeps_raw_bytes() -> None:
    value = BoundedText("A😀B", max_bytes=6)
    assert value.prefix_codepoints(2).raw_bytes == b"A\xf0\x9f\x98\x80"
    assert value.prefix_codepoints(0).value == ""
    left = BoundedText("é", max_bytes=2)
    right = BoundedText("😀", max_bytes=4)
    joined = left.concat(right)
    assert joined.value == "é😀"
    assert joined.max_bytes == 6
    assert joined.raw_bytes == b"\xc3\xa9\xf0\x9f\x98\x80"
    with pytest.raises(A1CollectionError) as error:
        left.concat(right, max_bytes=5)
    assert error.value.code == "A1_TEXT_CAPACITY"


def test_option_and_result_are_plain_tagged_canonical_values() -> None:
    assert option_some({"id": 1}).canonical() == {"tag": "Some", "value": {"id": 1}}
    assert result_ok([1, 2]).canonical() == {"tag": "Ok", "value": [1, 2]}
    assert result_err(CapacityError.CapacityExceeded).canonical() == {
        "tag": "Err",
        "error": "CapacityExceeded",
    }
