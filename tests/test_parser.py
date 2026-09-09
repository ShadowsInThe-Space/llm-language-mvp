"""Observable syntax and canonical transport behavior."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from llmlang.model import LanguageError, Limits
from llmlang.parser import canonical_candidate, canonical_spec, parse_candidate, parse_spec

SPEC = (
    "(spec p0 (fn (params Int Bool) (result Int) (requires true)"
    " (ensures (int.eq result (var 1)))))"
)


def test_whitespace_roundtrip() -> None:
    assert canonical_spec(parse_spec(" \n" + SPEC.replace(" ", "\n  ") + "\n")) == SPEC


@given(st.integers(min_value=-(10**100), max_value=10**100))
def test_integer_roundtrip(value: int) -> None:
    source = f"(candidate p0 (body {value}))"
    assert canonical_candidate(parse_candidate(source)) == source


@pytest.mark.parametrize(
    "source",
    [
        "",
        "(candidate p0)",
        "(candidate p1 (body 0))",
        "(candidate p0 (body 0)) 0",
        "(candidate p0 (body 0)",
        "(candidate p0 (body 0)))",
        "(candidate p0 (body +1))",
        "(candidate p0 (body 01))",
        "(candidate p0 (body -0))",
        "(candidate p0 (body -01))",
        "(candidate p0 (body 1.0))",
        "(candidate p0 (body 1e2))",
        '(candidate p0 (body "a"))',
        "(candidate p0 (body ; hi\n0))",
        "(candidate p0 (body (int.add 1)))",
        "(candidate p0 (body (not true false)))",
        "(candidate p0 (body (and true)))",
        "(candidate p0 (body (wat 0)))",
        "(candidate p0 (body (var -1)))",
        "(candidate p0 (body (var true)))",
        "(candidate p0 (body (let 0)))",
        "(candidate p0 (body 0 1))",
        "(candidate p0 (requires true) (body 0))",
    ],
)
def test_reject_malformed_source(source: str) -> None:
    with pytest.raises(LanguageError):
        parse_candidate(source)


@pytest.mark.parametrize(
    "source",
    [
        "(spec p0)",
        "(spec p0 (fn (params Float) (result Int) (requires true) (ensures true)))",
        "(spec p0 (fn (result Int) (params) (requires true) (ensures true)))",
        "(spec p0 (fn (params) (result Int) (requires true) (ensures true) (ensures false)))",
    ],
)
def test_reject_invalid_spec_fields(source: str) -> None:
    with pytest.raises(LanguageError):
        parse_spec(source)


def test_source_and_structure_limits_apply_during_parse() -> None:
    with pytest.raises(LanguageError, match="limit"):
        parse_candidate("(candidate p0 (body 123))", Limits(max_source_bytes=4))
    with pytest.raises(LanguageError, match="limit"):
        parse_candidate("(candidate p0 (body 123))", Limits(max_int_digits=2))
    with pytest.raises(LanguageError, match="limit"):
        parse_candidate("(candidate p0 (body 123))", Limits(max_nodes=3))
    with pytest.raises(LanguageError, match="limit"):
        parse_candidate(
            "(candidate p0 (body " + "(not " * 100 + "true" + ")" * 102, Limits(max_depth=30)
        )


@given(st.text(max_size=500))
def test_untrusted_text_never_escapes_language_errors(source: str) -> None:
    try:
        candidate = parse_candidate(source)
    except LanguageError:
        return
    assert parse_candidate(canonical_candidate(candidate)) == candidate


@pytest.mark.parametrize(
    "source,offset",
    [
        (")", 0),
        (" \n)", 2),
        ("(candidate p0 (body 0)", 22),
        ("(candidate p0 (body 0)) true", 24),
        ("(candidate p0 (body +1))", 20),
        ("(candidate p0 (body -0))", 20),
        ('(candidate p0 (body "hi"))', 20),
    ],
)
def test_lexical_failures_include_character_offset(source: str, offset: int) -> None:
    with pytest.raises(LanguageError) as error:
        parse_candidate(source)
    assert error.value.path == (offset,)
    assert "character offset" in error.value.message
