"""Strict P0 typing and deterministic, resource-bounded reference evaluation.

Diagnostic paths are zero-based: (0, function, field, *children) for specifications
(fields: params=0, result type=1, requires=2, ensures=3); (1, function, *children)
for bodies; (2, entry, argument) for host inputs; (3, *children) for standalone
contract expressions. Children index Expr.args. Signature parameter paths append
the parameter index. A shorter path denotes its containing structure.
"""

from dataclasses import dataclass
from typing import cast

from .model import (
    Candidate,
    Expr,
    FunctionSpec,
    LanguageError,
    Limits,
    Program,
    Specification,
    Type,
    Value,
)
from .parser import ARITIES

DEFAULT_LIMITS = Limits()


def _value_type(value: Value, limits: Limits, path: tuple[int, ...]) -> Type:
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        if value.bit_length() > limits.max_bits:
            raise LanguageError("E_LIMIT", "Integer bit limit exceeded", path)
        return "Int"
    raise LanguageError("E_VALUE", "Expected exact host Int or Bool", path)


@dataclass
class _TypeChecker:
    spec: Specification
    limits: Limits
    nodes: int = 0

    def infer(
        self,
        expr: Expr,
        context: tuple[Type, ...],
        current: int,
        result: Type | None = None,
        contract: bool = False,
        depth: int = 1,
        path: tuple[int, ...] = (3,),
    ) -> Type:
        self.nodes += 1
        if self.nodes > self.limits.max_nodes or depth > min(self.limits.max_depth, 256):
            raise LanguageError("E_LIMIT", "AST structure limit exceeded", path)
        if type(expr) is not Expr or type(expr.args) is not tuple or type(expr.op) is not str:
            raise LanguageError("E_TYPE", "Malformed immutable expression", path)
        op = expr.op
        if op in ("int", "bool"):
            expected = "Int" if op == "int" else "Bool"
            if expr.args or _value_type(cast(Value, expr.value), self.limits, path) != expected:
                raise LanguageError("E_TYPE", "Malformed literal", path)
            if op == "int":
                # Bit bound above keeps this conversion within the host's ordinary range.
                value = cast(int, expr.value)
                if abs(value) >= 10**self.limits.max_int_digits:
                    raise LanguageError("E_LIMIT", "Integer digit limit exceeded", path)
            return expected
        if op in ("var", "call"):
            if type(expr.value) is not int or expr.value < 0:
                raise LanguageError("E_BINDING", "Expected nonnegative exact index", path)
        elif expr.value is not None:
            raise LanguageError("E_TYPE", "Unexpected expression payload", path)
        if op == "var":
            index = cast(int, expr.value)
            if expr.args or index >= len(context):
                raise LanguageError("E_BINDING", "Variable outside its binding context", path)
            return context[-index - 1]
        if op == "result":
            if expr.args or result is None:
                raise LanguageError("E_BINDING", "Result is only available in postconditions", path)
            return result
        if op == "call":
            index = cast(int, expr.value)
            if contract or index >= current:
                raise LanguageError("E_CALL", "Calls must be backward and outside contracts", path)
            fn = self.spec.functions[index]
            if len(expr.args) != len(fn.params):
                raise LanguageError("E_CALL", "Wrong number of call arguments", path)
            for child, (arg, expected) in enumerate(zip(expr.args, fn.params, strict=True)):
                child_path = (*path, child)
                actual = self.infer(arg, context, current, result, contract, depth + 1, child_path)
                self.require(actual, expected, child_path)
            return fn.returns
        if op not in ARITIES or len(expr.args) != ARITIES[op]:
            raise LanguageError("E_TYPE", "Unknown operator or incorrect arity", path)
        if op == "let":
            bound = self.infer(
                expr.args[0], context, current, result, contract, depth + 1, (*path, 0)
            )
            return self.infer(
                expr.args[1], (*context, bound), current, result, contract, depth + 1, (*path, 1)
            )
        types = tuple(
            self.infer(arg, context, current, result, contract, depth + 1, (*path, child))
            for child, arg in enumerate(expr.args)
        )
        if op == "if":
            self.require(types[0], "Bool", (*path, 0))
            self.require(types[2], types[1], (*path, 2))
            return types[1]
        expected = "Int" if op.startswith("int.") else "Bool"
        for child, actual in enumerate(types):
            self.require(actual, cast(Type, expected), (*path, child))
        if op == "int.mul" and all(arg.op != "int" for arg in expr.args):
            raise LanguageError(
                "E_TYPE", "Multiplication requires one syntactic integer literal", path
            )
        return "Int" if op in ("int.add", "int.sub", "int.mul") else "Bool"

    @staticmethod
    def require(actual: Type, expected: Type, path: tuple[int, ...]) -> None:
        if actual != expected:
            raise LanguageError("E_TYPE", f"Expected {expected}, got {actual}", path)


def validate(spec: Specification, candidate: Candidate, limits: Limits = DEFAULT_LIMITS) -> Program:
    if type(spec) is not Specification:
        raise LanguageError("E_TYPE", "Expected immutable specification", (0,))
    if type(candidate) is not Candidate:
        raise LanguageError("E_TYPE", "Expected immutable candidate", (1,))
    if spec.profile != "p0" or type(spec.functions) is not tuple or not spec.functions:
        raise LanguageError("E_TYPE", "Invalid specification profile or declarations", (0,))
    if (
        candidate.profile != "p0"
        or type(candidate.bodies) is not tuple
        or len(spec.functions) != len(candidate.bodies)
    ):
        raise LanguageError("E_TYPE", "Candidate profile or declaration count mismatch", (1,))
    if len(spec.functions) > limits.max_nodes:
        raise LanguageError("E_LIMIT", "Function count limit exceeded", (0,))
    checker = _TypeChecker(spec, limits)
    for index, (fn, body) in enumerate(zip(spec.functions, candidate.bodies, strict=True)):
        if type(fn) is not FunctionSpec:
            raise LanguageError("E_TYPE", "Invalid function signature", (0, index))
        if type(fn.params) is not tuple:
            raise LanguageError("E_TYPE", "Invalid parameter container", (0, index, 0))
        if fn.returns not in ("Int", "Bool"):
            raise LanguageError("E_TYPE", "Invalid result type", (0, index, 1))
        for parameter, parameter_type in enumerate(fn.params):
            if parameter_type not in ("Int", "Bool"):
                raise LanguageError("E_TYPE", "Invalid parameter type", (0, index, 0, parameter))
        if len(fn.params) > limits.max_parameters:
            raise LanguageError("E_LIMIT", "Parameter count limit exceeded", (0, index, 0))
        checker.nodes += len(fn.params) + 1
        requires_path = (0, index, 2)
        ensures_path = (0, index, 3)
        body_path = (1, index)
        checker.require(
            checker.infer(fn.requires, fn.params, index, contract=True, path=requires_path),
            "Bool",
            requires_path,
        )
        checker.require(
            checker.infer(fn.ensures, fn.params, index, fn.returns, True, path=ensures_path),
            "Bool",
            ensures_path,
        )
        checker.require(
            checker.infer(body, fn.params, index, path=body_path), fn.returns, body_path
        )
    return Program(spec, candidate)


@dataclass
class _Evaluator:
    limits: Limits
    program: Program | None = None
    steps: int = 0

    def expression(
        self,
        expr: Expr,
        context: tuple[Value, ...],
        result: Value | None = None,
        depth: int = 1,
        path: tuple[int, ...] = (3,),
    ) -> Value:
        self.steps += 1
        if self.steps > self.limits.max_steps or depth > min(self.limits.max_depth, 256):
            raise LanguageError("E_LIMIT", "Execution resource limit exceeded", path)
        op = expr.op
        if op in ("int", "bool"):
            return cast(Value, expr.value)
        if op == "var":
            return context[-cast(int, expr.value) - 1]
        if op == "result":
            return cast(Value, result)
        if op == "let":
            bound = self.expression(expr.args[0], context, result, depth + 1, (*path, 0))
            return self.expression(expr.args[1], (*context, bound), result, depth + 1, (*path, 1))
        if op == "if":
            condition = self.expression(expr.args[0], context, result, depth + 1, (*path, 0))
            child = 1 if condition else 2
            return self.expression(expr.args[child], context, result, depth + 1, (*path, child))
        args = tuple(
            self.expression(arg, context, result, depth + 1, (*path, child))
            for child, arg in enumerate(expr.args)
        )
        if op == "call":
            return self.call(cast(int, expr.value), args, depth + 1)
        if op == "not":
            return not args[0]
        left, right = args
        if op == "and":
            return bool(left and right)
        if op == "or":
            return bool(left or right)
        if op in ("bool.eq", "int.eq"):
            return left == right
        if op == "int.le":
            return left <= right
        if op == "int.lt":
            return left < right
        if op == "int.add":
            output = left + right
        elif op == "int.sub":
            output = left - right
        elif op == "int.mul":
            output = left * right
        else:
            raise LanguageError("E_TYPE", "Unknown runtime operator", path)
        _value_type(output, self.limits, path)
        return output

    def call(self, entry: int, inputs: tuple[Value, ...], depth: int = 1) -> Value:
        if self.program is None:
            raise LanguageError("E_CALL", "Contracts cannot call functions", (3,))
        fn = self.program.spec.functions[entry]
        if self.expression(fn.requires, inputs, depth=depth + 1, path=(0, entry, 2)) is not True:
            raise LanguageError(
                "E_PRECONDITION", f"Function {entry} precondition rejected inputs", (0, entry, 2)
            )
        return self.expression(
            self.program.candidate.bodies[entry], inputs, depth=depth + 1, path=(1, entry)
        )


def evaluate(
    program: Program,
    inputs: tuple[Value, ...],
    entry: int | None = None,
    limits: Limits = DEFAULT_LIMITS,
) -> Value:
    if type(program) is not Program:
        raise LanguageError("E_TYPE", "Expected immutable program", (1,))
    validate(program.spec, program.candidate, limits)
    chosen = len(program.spec.functions) - 1 if entry is None else entry
    if type(chosen) is not int or chosen < 0 or chosen >= len(program.spec.functions):
        raise LanguageError("E_CALL", "Invalid public entry index", (2,))
    if type(inputs) is not tuple or len(inputs) != len(program.spec.functions[chosen].params):
        raise LanguageError("E_VALUE", "Wrong input count or mutable input container", (2, chosen))
    for argument, (value, expected) in enumerate(
        zip(inputs, program.spec.functions[chosen].params, strict=True)
    ):
        path = (2, chosen, argument)
        _TypeChecker.require(_value_type(value, limits, path), expected, path)
    return _Evaluator(limits, program).call(chosen, inputs)


def evaluate_contract(
    expr: Expr,
    inputs: tuple[Value, ...],
    result: Value | None = None,
    limits: Limits = DEFAULT_LIMITS,
) -> Value:
    if type(inputs) is not tuple:
        raise LanguageError("E_VALUE", "Expected immutable input tuple", (2,))
    context = tuple(
        _value_type(value, limits, (2, 0, argument)) for argument, value in enumerate(inputs)
    )
    result_type = _value_type(result, limits, (3,)) if result is not None else None
    _TypeChecker(Specification(()), limits).infer(expr, context, 0, result_type, True)
    return _Evaluator(limits).expression(expr, inputs, result)
