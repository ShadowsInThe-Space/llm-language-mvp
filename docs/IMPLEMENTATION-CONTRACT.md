# P0 implementation contract, 2026-09-08

This is the frozen interface for the implementation swarm. See the reviewed source specs in
the project review and `docs/P0.md`.
This document records the frozen swarm implementation interfaces; the completed implementation is covered by the acceptance evidence.

## Definition of Done

- Real parser, canonical serializer, type checker, interpreter; no host eval/exec.
- Int and Bool, let/if, linear arithmetic, first-order backward calls; strict Boolean operators.
- Trusted immutable specification separate from candidate bodies.
- Verification reconstructs every postcondition AND reachable call-precondition obligation.
- Independent exact cert-v0 checker; solver UNSAT is never itself acceptance.
- Ten golden tasks, valid/invalid/tampered cases, properties/fuzzing, pytest/Ruff/mypy pass.
- Bounded generate/verify/repair loop and a working model adapter.
- A real session agent writes a new Hello World candidate in our language; own checker proves it;
  own interpreter evaluates precisely that candidate; host emits `Hello World\n` from returned codes.
- A deliberately wrong grant candidate receives validated feedback and is repaired by an agent
  at unchanged specification, then independently checked and executed.
- Deliver installable source, runnable demo, evidence, dependency versions and honest TCB documentation.

## Source grammar

```
(spec p0 (fn (params Int Int) (result Int) (requires (and (int.le 0 (var 1)) (int.le 0 (var 0)))) (ensures (int.eq result (if (int.le (var 1) (var 0)) (var 1) (var 0))))) (fn (params Int Int) (result Int) (requires (and (int.le 0 (var 1)) (int.le 0 (var 0)))) (ensures (int.eq result (if (int.le (var 1) (var 0)) (var 1) (var 0))))))
(candidate p0 (body (if (int.lt (var 0) (var 1)) (var 0) (var 1))) (body (call 0 (var 1) (var 0))))
```

The example indentation is explanatory; the parser must check complete balanced input and fixed fields.
Source files use `.llspec` and `.ll`. One ordered fn/body pair per declaration. At least one fn.
Entry index defaults to last declaration. Every fn is a public entry with its own contract.
No names, import, hash self-field, multiplicities or effects in p0 transport: all values unrestricted/pure.

Expr literals are canonical bare decimal integers or `true`/`false`.
`(var n)` = de Bruijn index, final parameter at zero. `result` only in ensures, separate slot.
`(let value body)` extends only body's context; `(if c t f)` evaluates only selected branch.
`(call n arg...)` calls fn n, arguments in original parameter order, only n less than current fn.
`int.add`, `int.sub`, `int.mul` (one syntactic int literal), `int.le`, `int.lt`, `int.eq`
are binary. `not` unary, `and`, `or`, `bool.eq` binary. No user calls inside contracts.
No string literals/comments/extra input/implicit coercions. Signed zero and leading zero rejected.
Canonical printing is a single line with one space between children and no trailing newline.

## Shared model and APIs

`model.py` is owned by Root, notify Root before changing it.
`Expr(op,args,value)`: op int/bool carry literal in value; var/call carry index in value;
result has neither; remaining operators hold args. Frozen dataclasses, tuples throughout.
Types/limits/errors live in model.py.

Core agent owns parser.py, core.py and its tests:
- parse_spec(source: str, limits: Limits=Limits()) -> Specification
- parse_candidate(source: str, limits: Limits=Limits()) -> Candidate
- canonical_spec(spec) -> str, canonical_candidate(candidate) -> str, canonical_expr(expr) -> str
- validate(spec, candidate, limits=Limits()) -> Program (raises LanguageError)
- evaluate(program, inputs: tuple[Value,...], entry: int|None=None, limits=Limits()) -> Value
  validates exact host value types, requires, every actual call precondition and resource limits;
  entry default last. Runtime postcondition is not used to manufacture proof acceptance.
- evaluate_contract(expr, inputs, result=None, limits=Limits()) -> Value (call-free evaluator)

Proof agent owns symbolic.py, proof.py, solver.py and its tests. It may add internal files.
- verify(spec, candidate, limits=Limits()) -> VerificationReport
- check_certificate(spec,candidate, certificate: dict[str,object], limits=Limits()) -> bool
  must reconstruct obligations, validate all binding/weights/coverage, no solver trust/calls.
- report.status: invalid/unverified/counterexample/proved
- report.domains: tuple[DomainResult,...], each .status + .witness (tuple values or None)
- report.certificate: dict[str,object]|None; .counterexample: dict[str,object]|None
- report.to_dict() -> dict[str,object] (tagged exact values)
- Use SHA256 domain-separated length-framed canonical bytes for baseline, candidate, checker version.
  Include complete spec and candidate identity in cert; include deterministic obligation and leaf IDs.
- Exact Farkas leaf: integer rows a*x<=b, rational nonnegative weights, summed a=0, summed b<0.
  Counterexamples must satisfy entry requires and violate post or actual call-pre obligation.
  cert-v0 must not silently add GCD/floor cuts or free split atoms. `2*x=1` domain unknown.
  Domain empty only with certificate, nonempty only with concretely validated witness.
  May use Z3 to search exact rational weights and concrete integer witnesses, but only as untrusted search.
  Generate Boolean paths with guard conditions (DNF/branch expansion) and enforce limits during expansion.

Factory agent owns factory.py, adapters.py and its tests:
- CandidateProvider Protocol generate(request: dict[str,object])->str returns candidate source only.
- FileCandidates implements iterable candidate-source provider (session-agent bridge/replay).
- OpenAICompatibleProvider uses configured explicit endpoint/model/API key from host configuration,
  strict response validation, bounded HTTP response and timeout; no shell execution and no secret logging.
  Test with loopback HTTP fixture. No paid/external live call is needed in this session.
- run_factory(spec: Specification, provider: CandidateProvider, limits=Limits()) -> FactoryResult
- result.candidate: Candidate|None, .verification: VerificationReport|None, .to_dict() -> dict
- Each request includes frozen canonical spec, attempt, prior structured feedback. At most 3 attempts.
  Validate generated source, verify, re-check acceptance certificate independently, stop only if proved.
  Bad syntax, tampering, exceptions and budget exhaustion must never create a success.
- Log actual attempts and bound hash; candidates cannot edit spec/checker. Request/response are data.

Root owns CLI, packaging, integration tests, release documentation and evidence.
Fixtures agent owns examples and golden tests; gets precise instructions separately.
Write tests first and capture an actual failing run before implementation for your component.
No commits while others edit; Root commits integrated result. Use .venv/bin/python -m pytest etc.
