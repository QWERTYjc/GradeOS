# Public source

GradeOS source is licensed under GPL-3.0-only. Third-party notices are included in
`THIRD_PARTY_LICENSES/` and `web/assets/icons/LICENSE`.

Use synthetic data for tests, documentation and screenshots. Keep examination materials,
student submissions, score records, workspaces, credentials and model transcripts outside Git.
The local `evals/fixtures/`, `evals/medly/`, workspace directories and `runs/` are ignored.

Run `npm run check` after installing the dependencies. Running private evaluations is a separate,
explicit local action. The source export helper can also package a working tree without Git history.
