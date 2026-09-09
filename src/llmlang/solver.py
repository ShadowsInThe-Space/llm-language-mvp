"""Untrusted Z3 search only. All outputs are checked independently by proof.py."""

from dataclasses import dataclass
from fractions import Fraction
from time import monotonic

import z3

from .model import Limits
from .symbolic import Leaf


@dataclass(slots=True)
class SearchBudget:
    deadline: float

    @classmethod
    def start(cls, limits: Limits) -> "SearchBudget":
        return cls(monotonic() + limits.solver_timeout_ms / 1000)

    def remaining_ms(self) -> int:
        return max(0, int((self.deadline - monotonic()) * 1000))


def _solver(limits: Limits, budget: SearchBudget) -> z3.Solver | None:
    timeout = budget.remaining_ms()
    if timeout < 1:
        return None
    solver = z3.Solver()
    solver.set(timeout=timeout, rlimit=max(1, limits.max_steps * 10))
    return solver


def find_weights(leaf: Leaf, limits: Limits, budget: SearchBudget) -> tuple[Fraction, ...] | None:
    # Trivial contradiction also avoids bootstrapping an SMT context per constant leaf.
    for index, row in enumerate(leaf.rows):
        if not any(row.coefficients) and row.bound < 0:
            return tuple(Fraction(int(i == index)) for i in range(len(leaf.rows)))
    if not leaf.rows:
        return None
    solver = _solver(limits, budget)
    if solver is None:
        return None
    weights = [z3.Real(f"weight_{i}") for i in range(len(leaf.rows))]
    solver.add(*(weight >= 0 for weight in weights))
    for column in range(len(leaf.rows[0].coefficients)):
        solver.add(
            z3.Sum(
                [
                    weight * row.coefficients[column]
                    for weight, row in zip(weights, leaf.rows, strict=True)
                ]
            )
            == 0
        )
    # Any negative RHS may be scaled to -1 with positive rational scaling.
    solver.add(
        z3.Sum([weight * row.bound for weight, row in zip(weights, leaf.rows, strict=True)]) == -1
    )
    if solver.check() != z3.sat:
        return None
    model = solver.model()
    result = []
    for weight in weights:
        rational = model.eval(weight, model_completion=True)
        if not z3.is_rational_value(rational):
            return None
        result.append(Fraction(rational.numerator_as_long(), rational.denominator_as_long()))
    return tuple(result)


def find_integers(leaf: Leaf, limits: Limits, budget: SearchBudget) -> tuple[int, ...] | None:
    solver = _solver(limits, budget)
    if solver is None:
        return None
    dimensions = sum(type(value) is not bool for value in leaf.inputs)
    variables = [z3.Int(f"input_{i}") for i in range(dimensions)]
    for row in leaf.rows:
        solver.add(
            z3.Sum([a * variable for a, variable in zip(row.coefficients, variables, strict=True)])
            <= row.bound
        )
    if solver.check() != z3.sat:
        return None
    model = solver.model()
    values = tuple(model.eval(variable, model_completion=True).as_long() for variable in variables)
    if any(type(value) is not int or abs(value).bit_length() > limits.max_bits for value in values):
        return None
    return values
