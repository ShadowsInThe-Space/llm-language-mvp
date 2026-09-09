import pytest

from llmlang.core import validate
from llmlang.model import Candidate, Expr, FunctionSpec, LanguageError, Specification


def test_parameter_budget_precedes_quadratic_symbolic_allocation() -> None:
    spec = Specification(
        (FunctionSpec(("Int",) * 33, "Int", Expr("bool", value=True), Expr("bool", value=True)),)
    )
    with pytest.raises(LanguageError, match="[Pp]arameter") as error:
        validate(spec, Candidate((Expr("int", value=0),)))
    assert error.value.code == "E_LIMIT"
