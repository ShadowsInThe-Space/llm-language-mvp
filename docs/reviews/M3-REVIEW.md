# M3 independent AI package review

Date: 2026-10-09. Reviewer: separate Codex AI reviewer (`/root/m3_review`).
This is an independent implementation review, not an academic endorsement or a
formal proof of the compiler, website, authentication adapter or database.

Release-Review: approved

Reviewed implementation: `milestone/m3` through
`6b8d4a09f03001f09cea9c4bdf3f0de928a849c3`, with complete green
[CI run 37980399274](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37980399274).
The reviewer also read the subsequent documentation-only README, CHANGELOG,
v0.7.0 notes, quickstart, general/host guides and release-workflow updates.
Approval covers this complete M3 implementation and reviewed release material.
It does not assert issue closure, candidate-gate completion, final merge or
publication. The maintainer must complete those steps and revalidate the final
package commit and exact main SHA under the release workflow.

## Scope and method

The reviewer read the live acceptance criteria for issues
[#21](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/21),
[#22](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/22) and
[#32](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/32),
`release-plan.json`, `AGENTS.md` and `docs/RELEASE-WORKFLOW.md`.
The scope remains the complete three-issue M3 package; no unfinished scoped issue
has been removed or treated as completed by a limitation statement.

Review covered the effect checker, A1 source frontend and portable runtime,
general program/source model, codecs, queries, server/client emitters, build and
CLI, both example applications, generated-target/wheel checks, bundle audit,
pinned host and browser fixtures. The reviewer did not implement their repairs;
confirmed counterexamples were returned to their owners and independently
repeated after correction. The only reviewer-owned change is this document.

Local verification used Python 3.13 stdlib unittest and Node 26 execution of the
actual emitted controller/runtime. Pytest, Ruff, Mypy and the pinned host/browser
dependencies were unavailable locally. Their CI evidence was read directly from
GitHub job steps and logs, with the checked-out commit verified.

## Acceptance mapping

"Covered" below identifies concrete implementation and tests. Acceptance uses
the complete successful run at the reviewed checkpoint, rather than combining
earlier partial failures into a passing result.

| Issue and criterion | Concrete implementation/evidence | Current assessment |
| --- | --- | --- |
| #21: pure functions cannot perform effects | Closed operation registry; shared functions require empty effects/capabilities; actual query/callback/call edges are derived; portable A1 runtime has no host operations | Covered by checker and runtime negative tests |
| #21: client DB writes rejected | Client locations reject DB requirements, including unused declarations; emitted clients contain only checked public UI/codec contracts | Covered by negative graph/emission tests and built-asset audit |
| #21: transitive capability subsets | Iterative acyclic dependency checking reconstructs complete callee requirements, including callbacks and pure helper calls | Covered by transitive negative tests |
| #21: stable diagnostics | Closed shapes, deterministic ordering, graph/resource limits and dedicated location/effect diagnostic tests | Covered within the versioned structural contract |
| #21: browser values cannot mint identity/admin | Closed action/input envelopes, exact nominal fields; protected actions require a trusted host callback; authorization precedes pure execution and database access | Covered by protected-action boundary tests and passing real public-host injection tests |
| #22: existing history/demo behavior through composition | General source stores complete admitted Text4096, including empty/multiline Unicode; typed forms, list/detail selection, keyset pages, local clear and observable successful-request counters | All actual browser flow tests passed; additive-profile differences are stated below |
| #22: second data model, same toolchain | Tasks adds Bool completion, Nat priority/revision and conditional update; both applications reuse the same UI editor and A1 helper sources | Both strict target checks, installed-wheel checks and actual browser flows passed |
| #22: no manual target patches | Host preparation compares complete outputs with compiler builds and refuses existing destinations; host imports generated modules unchanged | Covered by preparation tests and successful pinned target build |
| #22: DB/server capabilities absent client | Client emitter excludes SQL, schema, policies, pure IR and unused actions; audit scans actual built JS and decoded external maps, rejects private paths and inline maps | 10 JS files and 7 maps audited successfully at the recorded checkpoint |
| #22: provenance recorded | Canonical source/library snapshots, source positions, semantic/effect hashes, compiler/codec/runtime identities and hashes for every generated file; check_build recompiles and compares all artifacts | Covered by complete recomputation, tamper and installed-wheel tests |
| #32: both apps entirely from language/libraries | Explicit websrc1/webuilib1/a1src1 inputs lower through the same general model; no domain-specific emitter branches | Covered by both source examples and unrelated-schema tests |
| #32: same compiler/runtime without handpatches | Source-bound builds, same generated client/dispatcher/codecs/runtime and unchanged host imports | Covered by preparation, strict TypeScript and wheel checks |
| #32: save/load/select/clear, Unicode, errors, reload/restart | Actual click/keyboard, multiline textContent and computed styling, paging, local clear, error preservation, stale genuine detail response and delayed hydration tests on three engines; actual host stopped/restarted against the same D1 state | All 24 browser flow tests and D1 persistence checks passed in the complete 33-test target suite |
| #32: client separation and manipulated values | Actual bundle/maps audit; real-host origin, envelope/field injection rejection and no-write checks; protected host-policy tests remain separate | Covered by the successful complete target job |
| #32: provenance and exact codecs | Closed nominal records; decimal-string safe integers; Unicode/UTF-8, bytes/nodes/depth limits; Python/TS differential tests and full build recomputation | Covered by regressions, generated execution and wheel checks |
| #32: early atomic conditional query on real target | Actual local D1 concurrent revision UPDATE gives one winner and one conflict; bounded INSERT SELECT probe checks policy, capacity and RETURNING in the mutation statement | Both CAS and strengthened spare-capacity replay probe passed in the complete final target run |
| #32: independent review, full regression and release docs green | This independent AI review; two Python CI matrices, Ruff/Mypy, strict TypeScript, real React SSR/hydration and wheel checks; complete release-doc delta reviewed | Covered at the approved code checkpoint; final package gate, merge and publication remain maintainer steps |

The history mapping covers the user flows explicitly named by #32 and the
roadmap's persistent values, selection and local clear. It is an additive general
application, not a wire-compatible replacement for frozen W2. Identifiers are
entered explicitly; confirmation counters are local per-view UI state, without
a server clock receipt. General replay/idempotency and unknown-commit resolution
are not implemented by these examples. W1/W2 and their existing guarantees remain
available unchanged. This review does not claim that these distinct protocols
are equivalent or that the entire W2 implementation was migrated.

## Documentation and absorbed README work

The reviewer fetched [PR #39](https://github.com/ShadowsInThe-Space/llm-language-mvp/pull/39)
at head `923273a8d776eb442d13b4008138d2901a6edfab` and compared its proposal
and review feedback with the milestone README. Its landing-page structure is
retained: purpose and the Python question, working historical demo, quickstart,
implemented-versus-planned capabilities, assurance, architecture and licensing.
It is absorbed into this complete milestone package rather than separately
merged into main.

The original broad independent-acceptance headline is corrected. Independent
certificate reconstruction is explicitly scoped to supported calculation
profiles; web generation, structural validation, tests and artifact integrity
are described separately. The hosted screenshot and walkthrough identify the
historical W2 application, while M3 has separate source and acceptance evidence.
The README/release notes distinguish v0.7.0 source preparation from authoritative
GitHub publication status and distinguish local D1 from cloud deployment.

The frozen ASSURANCE document retains its historical bytes. Current QUICKSTART
instructions and an additive clarification in GENERAL-WEB-PREVIEW distinguish
P0 statements from structured A1 support and M3 web checks. Known target limits, public-data
examples, trusted host authorization and the absence of a whole-website proof
are stated without treating testing as a formal theorem. The final documentation
uses the complete green run and makes v0.7.0 tag instructions conditional on
publication. No fresh internet installation or Windows verification is claimed.

## Confirmed findings and independently verified repairs

- Canonical record key sorting incorrectly affected field identity; exact field
  sets now remain valid without discarding nominal types or declaration order.
  Primitive const type handling and recursive call-graph traversal regressions
  also received focused fixes without relaxing execution-depth limits.
- Source operands allowed insufficiently checked literals and mutable paired
  source/IR snapshots. Literal validation is deep and expected-type aware;
  canonical bytes and defensive/immutable views preserve the accepted binding.
- Python/TypeScript parser depth diagnostics diverged. Differential regressions
  now cover the exact depth boundary and wide primitive/string collections.
- Legal output descriptors could exceed byte or JSON-node transport budgets.
  Static admission now checks worst-case output and the full request envelope;
  the original oversized examples and a 5,361-node byte-fitting case reject.
- Unused component selections could reference missing details. The complete
  declared view namespace is checked, preserving valid sibling references while
  rejecting ambiguous or missing IDs.
- The portable runtime admitted wrong nominal composite literals, unsafe integer
  literals and const values resembling SSA references; executable admission now
  shares its deep validator. Oversized work queues reject before traversal.
- SSR controls were usable before hydration. Disabled readiness gates and actual
  React SSR/hydration plus delayed-browser-script checks cover this boundary.
- Original examples discarded text after 120 code points and hid later rows.
  They now preserve full Text4096 through textarea, checked keyset paging and
  exact stored/displayed Unicode values. One-row pages retain the wire limits.
- A 14-column cursor generated 107 SQL bindings despite D1's 100-binding limit.
  Static compilation now checks binding count and SQL-byte limits, including
  repeated lexicographic cursor bindings and WHERE inputs.
- Previous-page cursor history grew without bound. The client now retains at
  most 32 cursors and 262144 serialized UTF-8 bytes per list. The reviewer
  repeated 1,200 forward pages; previous navigation was bounded and further
  forward navigation and Clear continued to work. A large escaped-cursor
  regression separately exercises the byte ceiling.
- The bundle audit missed base64 inline maps and the actual websrc1 marker.
  Both original counterexamples now reject; actual external maps remain checked
  as data without opening their source paths.
- Restart evidence could reach a surviving old worker after its launcher exited.
  Shutdown now requires a closed listening port, including the missing-process-
  group case. The original fail-open counterexample now fails the acceptance
  harness instead of falsely reporting persistence after restart.
- Real-target POST requests received a non-JSON HTTP 503 after early transport
  rejection. The provider's restart wording and startup custom-build messages
  did not establish that the worker actually reloaded. The speculative custom
  watcher was removed. Early 403/405/415 responses now dispose small bodies to
  EOF with the existing byte/read/time limits, without decoding or invoking
  authorization, pure helpers or database operations. Oversized, stalled or
  failed streams preserve their original rejection status; cancellation is not
  awaited. The reviewer independently passed all 17 server tests. The unchanged
  real-target rejection-followed-by-read sequence now passes without retries.
- Editing the frozen assurance guide broke the historical raw-file digest gate.
  Its owner restored the exact baseline bytes, kept the frozen test expectations
  unchanged and placed profile clarification in an additive guide. All 55 frozen
  raw-file digests match; the full compatibility suite passed again.

No unresolved implementation or documentation blocker remains in the reviewed
M3 scope. The earlier red target and frozen-file regressions are closed by their
unchanged assertions passing in the complete green run. This approval does not
waive final package CI, live issue/milestone gates or main revalidation.

## Directly verified final evidence

The reviewer independently fetched all three job step reports and logs for
[run 37980399274](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37980399274),
verified checkout `6b8d4a09f03001f09cea9c4bdf3f0de928a849c3`, and confirmed all
three jobs completed successfully:

- Python 3.12 and 3.13 each passed 706 pytest tests and 260 subtests, with one
  optional React-toolchain skip. Ruff passed; strict Mypy passed 51 source files.
- The provisioned Python 3.13 job passed all six actual React SSR/hydration checks,
  both strict generated TypeScript checks and both isolated installed-wheel
  compilation/binding checks. The optional baseline case was therefore exercised.
- The pinned Vinext build and two host settings checks passed; the actual client
  audit inspected ten JavaScript files and seven external source maps.
- Actual local D1 executed the conditional INSERT SELECT probe with changes
  `[1,0,0,0,1,0]`, including replay rejection with one remaining slot. The
  generated API seed sequence passed 26 requests, including a single CAS winner
  A and invalid-write rejection. After shutdown closed the old listening port,
  the new host passed five persistence reads with the same winner and text.
- All 33 Chromium/Firefox/WebKit browser and API tests passed in 47.0 seconds,
  without retries or weakened assertions. They include the previously failing
  rejection-followed-by-valid-read sequence, multiline computed styling,
  stale-response checks and delayed hydration.
- The committed npm lockfile gate passed. These results use the same exact
  implementation checkpoint; production/cloud deployment is not asserted.

The reviewed final documentation delta changes no implementation or frozen
compatibility bytes. A complete CI run on the assembled final package remains
required before merge, as does exact main validation before publication.

## Earlier checkpoints and regression closure

GitHub Actions run
[37977221372](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37977221372)
checked out `3c740ebb8a231255aa6afb0cb4b8931e0980a09e`.

- Python 3.12 and 3.13 each passed 703 pytest tests and 260 subtests, with one
  optional React-toolchain skip. Ruff passed; strict Mypy passed 51 source files.
- The provisioned Python 3.13 job passed all six actual React SSR/hydration tests,
  both strict generated TypeScript checks and both isolated installed-wheel
  compilation/binding checks. The baseline skip was therefore exercised.
- Pinned Vinext built successfully. The client audit inspected 10 JavaScript
  files and seven source maps.
- Actual local D1 seed checks made 26 requests, established one CAS winner and
  rejected invalid writes. The restarted host made five reads confirming the
  same stored Unicode values and actual winner after the old listener closed.
- Playwright passed 32 of 33 tests: all 24 actual browser flow tests and eight
  API cases passed. The Firefox history injection test received HTTP 503 from
  a subsequent valid absence-fetch instead of 200. The host job failed. No
  retry, skipped assertion or majority-pass interpretation closes that finding.
- Independently executed local integrated checks passed 110 general-web tests
  with one unavailable React-toolchain skip, four host preparation/shutdown
  tests and eight client-bundle audit tests. They do not replace target CI.

The reviewer also fetched job steps and host logs for
[run 37977968445](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37977968445),
which checked out `6a868f9fcfe9f1a9f38d7cd11d6846b9ce0bdd4b`.
Both baseline jobs succeeded, and the committed npm tree built and passed the
same 10-JS/seven-map audit. Actual local D1 executed the initial conditional
INSERT SELECT probe with changes `[1,0,0,0]`. That initial replay case also had
full capacity, so it does not independently establish the replay predicate;
the revised probe adds an enabled capacity-two scope with one remaining slot.
At that checkpoint the revised source had been inspected but had not yet been
executed in a recorded successful target run; the final run establishes it.

Run 37977968445 then failed during seed reads. The captured HTTP 503 body states
that the worker restarted mid-request and only GET/HEAD are retried automatically.
This establishes a provider transport failure rather than the dispatcher's JSON
error envelope; its text does not establish an actual worker restart. The
maintainer's pinned proxy inspection also questioned its restart classification.
A complete rerun was required rather than retrying application writes to conceal
the failure; that unchanged sequence passes in the final run.

Run
[37978716172](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37978716172)
checked out `5335719133985fa00f08cc8bf2bf94f88a0a2b21`. Both Python jobs exposed
one failed frozen-file assertion for `docs/ASSURANCE.md`: 702 tests and 260
subtests passed, with one optional skip. Ruff, strict Mypy and the provisioned
strict TypeScript, React and wheel checks passed. The strengthened actual local
D1 conditional INSERT SELECT probe passed with changes `[1,0,0,0,1,0]` and one
remaining slot in the replay scope. The host then failed to become ready within
90 seconds; browser tests were not reached. The frozen document required
restoration and host startup required correction before the package rerun. Changing the
expected digest or counting earlier partial target runs would not close these
regressions. The reviewer independently checked that all 55 frozen raw-file
digests match their unchanged fixture after the working-tree restoration.

Run
[37979355263](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37979355263)
checked out `cb7f3bce1e13b0c0d2d3898cc087671511cac328`. Both complete baseline
jobs passed: 703 tests and 260 subtests each, Ruff, strict Mypy, and provisioned
strict TypeScript, six React checks and both installed-wheel checks. The
strengthened D1 INSERT probe passed again. Host startup succeeded, but seed's
valid task fetch immediately after the foreign-origin rejection received the
same HTTP 503. This request ordering supports the unread-body hypothesis without
proving causation. The subsequent bounded-disposal fix and restored original
host configuration then passed the complete target run.

The reviewer completed the target, strengthened conditional-INSERT, full
regression, dependency-lock and final documentation checks before approval.
The intermediate run at `5566b5d5c6bd6e6e9c183c8049acb6afbee50771` also passed
the full host suite, but a 102-character helper signature failed Ruff. The sole
line-wrap correction was inspected, and the final run passed every job together.

After approval and before merge, the maintainer must attach issue completion
evidence, close all three issues as completed, set readiness and pass the exact
candidate gate on the work branch. This order avoids treating a gate that
requires the review marker as a precondition for writing that same marker. At
the time approval was written, readiness remained false and the three issues
were still open; this document does not claim those administrative steps occurred.

## Assurance and product limits

The demonstrated provider is Cloudflare's actual local D1/workerd implementation,
not a D1-shaped double, production deployment or remote Cloudflare database.
The acceptance host pins Node 24.19.0, Vinext 1.0.0-beta.5, Vite 8.0.13 and React
19.2.6 with a committed npm dependency tree. Browser automation uses Chrome for
Testing 148.0.7778.96, Firefox 150.0.2 and WebKit 26.4 in the recorded run; WebKit
is not an executed Safari test, and neither Edge nor native Safari was exercised.

Both examples intentionally expose public shared data. Protected actions require
a real trusted host identity/policy adapter; client field rejection is not an
authentication proof. Response/output failure after a committed write does not
prove rollback or resolve an unknown commit. Zero matching UPDATE rows do not
imply rollback of later writes in a multi-statement batch. The INSERT probe is
test-only target evidence, not a language-level booking transaction, concurrent
capacity proof or generally supported transaction block.

Query admission is a closed subset with non-null scalar columns and bounded
prepared statements. Paging does not promise a database snapshot under concurrent
writes. Older Previous cursors can be evicted; Next remains available and Clear
allows traversal from the first page. Generated schema creation is for fresh
databases, not an existing-data migration plan. Tenant/session/CRM relationships,
booking workflows and general transactions remain the separately scoped M4 work.

Structural checking, hash binding, testing and this review do not establish a
whole-website theorem or formal target equivalence. The bundle scan is evidence
about the inspected artifacts, not a general browser-isolation proof. Token,
aggregate throughput and complete elapsed-time counters are unavailable.
