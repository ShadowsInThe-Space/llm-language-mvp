"""Trusted, bounded symbolic execution over exact affine integers and Boolean paths.

No solver formulas or certificate premises enter this module. Every leaf is rebuilt
from the validated specification and candidate, including strict operand calls.
"""

from dataclasses import dataclass
from itertools import product
from typing import cast

from .model import Expr, LanguageError, Limits, Program, Value


@dataclass(frozen=True, slots=True)
class Linear:
    coefficients: tuple[int, ...]
    constant: int = 0


type SymbolicValue = Linear | bool


@dataclass(frozen=True, slots=True)
class Row:
    coefficients: tuple[int, ...]
    bound: int


@dataclass(frozen=True, slots=True)
class Path:
    rows: tuple[Row, ...]
    value: SymbolicValue


@dataclass(frozen=True, slots=True)
class Leaf:
    identifier: str
    entry: int
    kind: str
    rows: tuple[Row, ...]
    inputs: tuple[SymbolicValue, ...]


@dataclass(frozen=True, slots=True)
class Obligations:
    leaves: tuple[Leaf, ...]
    domains: tuple[tuple[Leaf, ...], ...]


DEFAULT_LIMITS = Limits()


class _Executor:
    def __init__(self, program: Program, limits: Limits) -> None:
        self.program = program
        self.limits = limits
        self.steps = 0
        self.branches = 0
        self.dimensions = 0
        self.entry = 0
        self.inputs: tuple[SymbolicValue, ...] = ()
        self.leaves: list[Leaf] = []

    def tick(self, depth: int) -> None:
        self.steps += 1
        if self.steps > self.limits.max_steps or depth > self.limits.max_depth:
            raise LanguageError("E_RESOURCE", "Symbolic execution work/depth budget exhausted")

    def branch(self, count: int = 1) -> None:
        self.branches += count
        if self.branches > self.limits.max_branches:
            raise LanguageError("E_RESOURCE", "Symbolic branch budget exhausted")

    def bounded(self, value: Linear) -> Linear:
        if any(
            abs(x).bit_length() > self.limits.max_coefficient_bits
            for x in (*value.coefficients, value.constant)
        ):
            raise LanguageError("E_RESOURCE", "Symbolic coefficient budget exhausted")
        return value

    def linear(self, value: int) -> Linear:
        return self.bounded(Linear((0,) * self.dimensions, value))

    def add(self, a: Linear, b: Linear, scale: int = 1) -> Linear:
        return self.bounded(
            Linear(
                tuple(x + scale * y for x, y in zip(a.coefficients, b.coefficients, strict=True)),
                a.constant + scale * b.constant,
            )
        )

    def multiply(self, a: Linear, constant: int) -> Linear:
        return self.bounded(
            Linear(tuple(x * constant for x in a.coefficients), a.constant * constant)
        )

    def row(self, value: Linear, bound: int = 0) -> Row:
        # value <= bound, with no floor/GCD/integrality cut.
        return Row(value.coefficients, self.bounded(self.linear(bound - value.constant)).constant)

    def record(self, kind: str, rows: tuple[Row, ...]) -> None:
        self.branch()
        self.leaves.append(
            Leaf(f"obligation:{self.entry}:{len(self.leaves)}", self.entry, kind, rows, self.inputs)
        )

    def close_simple_contradiction(self, rows: tuple[Row, ...]) -> bool:
        """Exact internal Farkas rules: a constant row or two opposite rows.

        Weights are respectively (1) and (1, 1). No new premise, split,
        division, rounding, floor, or integrality cut is introduced. In
        particular, identical nonzero coefficient vectors do NOT contradict.
        This checker-owned normalization prevents impossible Boolean paths
        from consuming the entire expansion budget before certification.
        """
        bounds: dict[tuple[int, ...], int] = {}
        for row in rows:
            self.tick(0)
            if not any(row.coefficients):
                if row.bound < 0:
                    return True
                continue
            opposite = tuple(-value for value in row.coefficients)
            previous = bounds.get(opposite)
            if previous is not None and previous + row.bound < 0:
                return True
            current = bounds.get(row.coefficients)
            if current is None or row.bound < current:
                bounds[row.coefficients] = row.bound
        return False

    def open_paths(self, paths: list[Path]) -> list[Path]:
        return [path for path in paths if not self.close_simple_contradiction(path.rows)]

    def comparison(self, name: str, a: Linear, b: Linear, rows: tuple[Row, ...]) -> list[Path]:
        delta = self.add(a, b, -1)
        reverse = self.multiply(delta, -1)
        if not any(delta.coefficients):
            match name:
                case "int.le":
                    answer = delta.constant <= 0
                case "int.lt":
                    answer = delta.constant < 0
                case _:
                    answer = delta.constant == 0
            return [Path(rows, answer)]
        if name == "int.le":
            self.branch(2)
            return self.open_paths(
                [
                    Path((*rows, self.row(delta)), True),
                    Path((*rows, self.row(reverse, -1)), False),
                ]
            )
        if name == "int.lt":
            self.branch(2)
            return self.open_paths(
                [
                    Path((*rows, self.row(delta, -1)), True),
                    Path((*rows, self.row(reverse)), False),
                ]
            )
        self.branch(3)
        return self.open_paths(
            [
                Path((*rows, self.row(delta), self.row(reverse)), True),
                Path((*rows, self.row(delta, -1)), False),
                Path((*rows, self.row(reverse, -1)), False),
            ]
        )

    def arguments(
        self,
        exprs: tuple[Expr, ...],
        env: tuple[SymbolicValue, ...],
        rows: tuple[Row, ...],
        result: SymbolicValue | None,
        depth: int,
    ) -> list[tuple[tuple[Row, ...], tuple[SymbolicValue, ...]]]:
        states: list[tuple[tuple[Row, ...], tuple[SymbolicValue, ...]]] = [(rows, ())]
        for expr in exprs:
            following = []
            for prefix_rows, values in states:
                for path in self.evaluate(expr, env, prefix_rows, result, depth + 1):
                    following.append((path.rows, (*values, path.value)))
                    if len(following) > self.limits.max_branches:
                        raise LanguageError("E_RESOURCE", "Argument expansion budget exhausted")
            states = following
        return states

    def evaluate(
        self,
        expr: Expr,
        env: tuple[SymbolicValue, ...],
        rows: tuple[Row, ...],
        result: SymbolicValue | None = None,
        depth: int = 0,
    ) -> list[Path]:
        self.tick(depth)
        match expr.op:
            case "int":
                return [Path(rows, self.linear(cast(int, expr.value)))]
            case "bool":
                return [Path(rows, cast(bool, expr.value))]
            case "var":
                return [Path(rows, env[cast(int, expr.value)])]
            case "result":
                if result is None:
                    raise LanguageError("E_RESULT", "Missing symbolic result")
                return [Path(rows, result)]
            case "let":
                paths = []
                for binding in self.evaluate(expr.args[0], env, rows, result, depth + 1):
                    paths.extend(
                        self.evaluate(
                            expr.args[1], (binding.value, *env), binding.rows, result, depth + 1
                        )
                    )
                return paths
            case "if":
                paths = []
                for condition in self.evaluate(expr.args[0], env, rows, result, depth + 1):
                    selected = expr.args[1] if condition.value is True else expr.args[2]
                    paths.extend(self.evaluate(selected, env, condition.rows, result, depth + 1))
                return paths
        paths = []
        for argument_rows, values in self.arguments(expr.args, env, rows, result, depth):
            if expr.op == "call":
                index = cast(int, expr.value)
                spec = self.program.spec.functions[index]
                call_env = tuple(reversed(values))
                for requirement in self.evaluate(
                    spec.requires, call_env, argument_rows, depth=depth + 1
                ):
                    if requirement.value is False:
                        self.record("call_precondition", requirement.rows)
                    else:
                        paths.extend(
                            self.evaluate(
                                self.program.candidate.bodies[index],
                                call_env,
                                requirement.rows,
                                depth=depth + 1,
                            )
                        )
                continue
            if expr.op in ("not", "and", "or", "bool.eq"):
                left = cast(bool, values[0])
                if expr.op == "not":
                    boolean = not left
                else:
                    right = cast(bool, values[1])
                    boolean = (
                        (left and right)
                        if expr.op == "and"
                        else ((left or right) if expr.op == "or" else left == right)
                    )
                paths.append(Path(argument_rows, boolean))
                continue
            left_int, right_int = cast(Linear, values[0]), cast(Linear, values[1])
            if expr.op in ("int.le", "int.lt", "int.eq"):
                paths.extend(self.comparison(expr.op, left_int, right_int, argument_rows))
                continue
            if expr.op == "int.add":
                integer = self.add(left_int, right_int)
            elif expr.op == "int.sub":
                integer = self.add(left_int, right_int, -1)
            elif expr.op == "int.mul":
                if expr.args[0].op == "int":
                    integer = self.multiply(right_int, left_int.constant)
                else:
                    integer = self.multiply(left_int, right_int.constant)
            else:
                raise LanguageError("E_OPERATOR", "Unsupported symbolic operation")
            paths.append(Path(argument_rows, integer))
        return paths

    def reconstruct(self) -> Obligations:
        domains: list[tuple[Leaf, ...]] = []
        for entry, spec in enumerate(self.program.spec.functions):
            self.entry = entry
            self.dimensions = spec.params.count("Int")
            bool_count = spec.params.count("Bool")
            if bool_count >= self.limits.max_branches.bit_length():
                raise LanguageError("E_RESOURCE", "Boolean input expansion budget exhausted")
            domain: list[Leaf] = []
            for booleans in product((False, True), repeat=bool_count):
                self.branch()
                inputs: list[SymbolicValue] = []
                int_index, bool_index = 0, 0
                for typ in spec.params:
                    if typ == "Int":
                        coefficients = tuple(
                            1 if i == int_index else 0 for i in range(self.dimensions)
                        )
                        inputs.append(Linear(coefficients))
                        int_index += 1
                    else:
                        inputs.append(booleans[bool_index])
                        bool_index += 1
                self.inputs = tuple(inputs)
                env = tuple(reversed(inputs))
                for requirement in self.evaluate(spec.requires, env, ()):
                    if requirement.value is False:
                        continue
                    self.branch()
                    domain.append(
                        Leaf(
                            f"domain:{entry}:{len(domain)}",
                            entry,
                            "domain",
                            requirement.rows,
                            self.inputs,
                        )
                    )
                    for body in self.evaluate(
                        self.program.candidate.bodies[entry], env, requirement.rows
                    ):
                        for post in self.evaluate(spec.ensures, env, body.rows, body.value):
                            if post.value is False:
                                self.record("postcondition", post.rows)
            domains.append(tuple(domain))
        return Obligations(tuple(self.leaves), tuple(domains))


def reconstruct(program: Program, limits: Limits = DEFAULT_LIMITS) -> Obligations:
    return _Executor(program, limits).reconstruct()


def instantiate(leaf: Leaf, integers: tuple[int, ...]) -> tuple[Value, ...]:
    values: list[Value] = []
    for value in leaf.inputs:
        if isinstance(value, bool):
            values.append(value)
        else:
            values.append(
                sum(a * b for a, b in zip(value.coefficients, integers, strict=True))
                + value.constant
            )
    return tuple(values)
