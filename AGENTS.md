# GradeOS Pi

This is the standalone successor foundation extracted from GradeOS's Pi prototype.
Keep one Node ESM service, a static browser UI, local durable files, and small Python PDF helpers.
Do not add GradeOS backend, Next.js, LangGraph, PostgreSQL, or Redis as runtime prerequisites.
No build step is needed for the browser modules. Pi dependencies are pinned in package-lock.json;
Python dependencies are pinned in uv.lock. Optional macOS Vision OCR must remain optional.

## Verification

Run `npm ci --ignore-scripts`, `uv sync --locked`, and `npm run check`.
The check runs Node contracts and Python tests without model requests.
Use a fresh ignored directory under `runs/` for every experiment. `--execute` is an explicit paid
run action; never invoke it as part of installation, CI, fixture preparation, or an offline check.

## Grading integrity

Keep `evals/**/posthoc/` and official scores outside model requests and runtime imports.
Only scheme, student, and question documents from `input.json` may become grading inputs.
Load posthoc references only after terminal status and frozen result hashes are verified.
Unknown, failed, cancelled, and incomplete results are not zero marks. Never choose retries,
providers, outputs, or thresholds based on expected scores. Preserve all attempts and receipts.
No offline check or single-paper pass proves general accuracy or readiness to replace production.

## Changes and data

Protect unrelated work. Keep source provenance and third-party licenses. Tests should cover
meaningful behavior, including unavailable scores and source/evidence ownership.
Never commit credentials, .env files, workspaces, generated pages, model transcripts, or runs.
Bundled examination materials retain their original rights and are for this private repository's
evaluation workflow; the code license does not license the papers. Keep the repository private.
Keep private evaluation data and its history outside all public refs.
