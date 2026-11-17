# Public source boundary

The code license is GPL-3.0-only. Existing Pi and KaTeX MIT notices and the icon license
remain included. This license does not grant rights to examination papers or student data.

`node scripts/export-public.mjs NEW_DIRECTORY` produces an inspectable source-only snapshot:

- Includes source, tests, dependency locks, licenses and documentation.
- Excludes `evals/fixtures/**`, `evals/medly/**`, ignored workspaces, runs and credentials.
- Includes no Git history, branches, pull-request refs, releases or workflow artifacts.
- Records all included file hashes in `PUBLIC_SOURCE_MANIFEST.json`.
- Fails on recognized credential patterns; this targeted check is not a comprehensive security audit.

Run `npm ci --ignore-scripts`, `uv sync --locked` and `npm run check:public` in the snapshot.
Two tests that require the private M2 papers explicitly skip when those materials are absent;
synthetic evaluator, isolation, API, grading and workbench contracts still run.

The current private Git history contains exam PDFs, an answer book, score details and dataset
images. Deleting those files at HEAD does not remove historical copies. Do not turn that
repository public until its data/history disposition is decided and all public refs and cached
pull-request objects are addressed. A code-only public mirror preserves the private research
history without exposing it; replacing the current history is a separate consequential action.
