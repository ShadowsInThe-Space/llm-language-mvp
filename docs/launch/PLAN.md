# Repository discovery plan

Goal: let a new developer understand the project, reproduce a result, and give
useful feedback. Recommendation placement is not a guaranteed outcome.

## Deliver now

1. Keep the plain-English README and explicit distinction between working and planned features.
2. Add an English quickstart with actual expected output and clear host requirements.
3. Show a short illustrated walkthrough using real compiler output and existing browser evidence.
4. Prepare v0.4.0 pre-release notes, contribution guidance and a bug-report template.
5. Keep community posts as drafts until an audience and publication are approved.

## Repository settings

The public repository already has these relevant topics:
`ai-agents`, `compiler`, `dsl`, `formal-verification`, `llm`, `python`, `smt`, `z3`.
No change is needed just to add more keywords.

The existing About description still mentions 178 tests. Proposed replacement:

> An experimental language and compiler for AI-written programs: generate small web apps from one blueprint and check calculation contracts with an independent verifier.

The About website field is empty. Before linking the demo there, confirm that an
outside visitor can open it without owner access. If it remains private, use the
public quickstart URL instead.

The available GitHub connector exposes file/commit updates but no About-settings,
tag-creation or Release-publication action. Those settings are therefore pending.
The browser skill prohibits bypassing unavailable plugin actions through the website.

## Next publication steps

1. Update the About description with the exact text above.
2. Create an experimental pre-release for version 0.4.0, attached to the reviewed
   launch commit, using RELEASE-v0.4.0.md. Do not imply a standalone deployable host.
3. Verify public demo access or prepare a locally runnable host before wider outreach.
4. Publish one tailored announcement after confirming the chosen community's rules.
5. Work through first-user setup problems before seeking broader exposure.

## Feedback measures

Record baseline on 2026-09-13: 0 stars, 0 forks, 0 open issues (GitHub API).
For a later review, compare unique visitors/clones where owner analytics permit,
quickstart completion reports, reproducible issues, and useful contributions.
Do not mistake stars for correctness or promise a recommendation threshold.
This document does not schedule a recurring review.

## Sources

- [GitHub project discovery](https://docs.github.com/en/get-started/exploring-projects-on-github/discovering-projects-on-github)
- [GitHub repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
