# Contributing to GradeOS

Use Node >=22.19, Python >=3.11, uv and Poppler. Install with `npm ci --ignore-scripts`
and `uv sync --locked`. Run `npm run check:public` for source-only offline tests.
The offline suite runs without a provider key. Use `npm run fixtures:check -- --fixture NAME` for a separately installed local fixture.

Keep the service as Node ESM with native browser modules. No frontend build step or database
is required. The workbench uses `system.json` and versioned `files/` inside the selected local
data directory; grading uses its existing workspace files.

Never commit credentials, user files, workspaces, model transcripts or evaluation datasets.
Use synthetic fixtures in tests and screenshots. Preserve unknown and incomplete scores.
Changes to grading logic must retain the existing evidence and teacher-review contracts.

For UI changes, verify the main flows at desktop and mobile widths and respect reduced motion.
Describe the user-visible behavior, validation and limitations in the pull request.
Contributions are distributed under GPL-3.0-only; retain third-party notices.
