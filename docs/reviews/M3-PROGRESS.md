# M3 implementation progress review

Date: 2026-10-08. Review type: independent AI specialist review by a separate
GPT-6.1-Sol worker, coordinated with bounded implementation workers.

This records reviewed implementation progress. It is not a release approval,
human academic endorsement, whole-website proof or actual D1/browser evidence.
The M3 release plan remains `ready: false`; issues #21, #22 and #32 stay open.

## Scope and verified repairs

Reviewed on the milestone work branch through `a3f88f5`:

- Immutable effect graph, closed host registry, transitive requirements and
  deterministic reachability/binding. Host authority is not minted by annotations.
- Canonical A1 source lowering, deep literal validation and defensive source/IR
  snapshots. Review found inline composite operands and mutable hash-bound data;
  both were reproduced in failing tests and corrected.
- Python/TypeScript codecs, typed SQL and runtime boundary dispatch. Cross-runtime
  JSON depth diagnostics were corrected after differential-test failure.
- Canonical general web/UI-library sources, typed model, source-bound artifacts,
  generic client/controller and server generation. Review found byte-fitting
  values that exceeded JSON node budgets and outputs larger than the wire cap.
  The model now rejects worst-case byte/node overflow before emission, including
  the complete input request envelope. Eight-row example bounds are deliberate.
- Unresolved selections in unused components are now rejected; valid sibling
  component references still work. Client output contains only used UI contracts.
- Three existing A1 regressions: canonical record key order, primitive constant
  type spellings and recursive static call-graph traversal. The reviewer compared
  iterative traversal with the former algorithm on shared-callee DAGs and cycles;
  acceptance and cycle diagnostics agree, with unchanged execution-depth limits.

For the repaired integration findings, the reviewer independently repeated the
original rejected cases, a 5,361-node result under the byte cap, and exact complete
artifact recomputation for both current examples. Twenty-three program tests and
ten codec tests passed. The three deep-graph tests also passed independently.

## Evidence boundary and remaining acceptance

Tests use actual local SQLite and Node execution of generated TypeScript. The
server boundary harness supplies a controlled D1-shaped double. It cannot establish
Cloudflare D1 behavior, restart persistence, transaction semantics or browser UX.

Remote CI executes the existing Python 3.12/3.13 pytest, Ruff and strict Mypy gates,
plus a new strict generated TypeScript check with pinned compiler/React types.
Each independent check runs even after another fails; every failure still fails
the job. There is no `continue-on-error` or release-gate bypass.

M3 still needs pinned Vinext host acceptance, actual D1 and browser runs,
built client/source-map inspection and a final package review.
See `docs/GENERAL-WEB-PREVIEW.md`.

No issue has been closed, no final M3 PR opened, no milestone merged or released.
Token usage, aggregate throughput and complete wall-time counters are unavailable.

## Exact checked implementation checkpoint

`3bc7b319565644dff577cae96b20dcc4ac971968` passed both Python 3.12/3.13
CI jobs: 638 tests plus 176 subtests, Ruff and strict Mypy. Both generated example
targets passed strict TypeScript. Evidence: GitHub Actions run
https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37800192253.
This evidence does not change the remaining M3 acceptance boundaries above.

## Executable-library continuation review

A separate read-only GPT-6.1-Sol reviewer inspected the new pure runtime,
parameter transforms, source grammar, generated server/client, build binding and
SQLite integration tests. This remains an AI implementation review, not release
approval. Review found and independently reproduced:

- Shallow wrong nominal record/variant literals admitted by the frozen core
  checker. The additive portable validator now deeply checks typed literal sites.
- Executable libraries with unsafe integer literals accepted by the web model
  but rejected by runtime emission. Both now share the same admission validator.
- Constants resembling SSA references and oversized structure work queues.
  Constants are checked as values; queues reject excess width before expansion.

The reviewer independently repeated all original counterexamples after repair,
including a list whose iterator throws if traversed before the size rejection.
Eleven portable-runtime tests and ninety general-web tests passed at that review
point, with one local React-toolchain skip. There was no open blocker in this
bounded integration slice. Subsequent CI must still validate the exact snapshot.

Checkpoint `2132f35be5de295f4addd798cd87685cb8b6697c` separately passed actual
React SSR/jsdom hydration and isolated installed-wheel tests for both examples
in CI. The same run identified Ruff formatting and one TypeScript narrowing
error; it was not a completely green checkpoint. SQLite close/reopen and stale
revision tests establish SQLite behavior only, not D1 provider acceptance.

The subsequent `f3fddd56c466ca8318a4dde5607c34ea822b348a` checkpoint passed
672 tests plus 208 subtests on both Python versions, strict Mypy, strict generated
TypeScript for both examples, all five provisioned React tests and both isolated
wheel checks. Evidence: Actions run
https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37813625006.
Two final Ruff findings were repaired by explicitly binding the per-function
inference environment and wrapping a test line; the repair receives another full
CI run. The final focused runtime suite contains fifteen passing tests. No
package release approval is inferred from these implementation checks.
