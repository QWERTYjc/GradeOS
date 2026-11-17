# GradeOS system interface

The product is GradeOS; the main entry is 工作台. The single sidebar connects 工作台, 批改,
文件, Skills and 任务. Local profile and settings are at the bottom. The homepage contains
one heading and composer. Tools, source metadata and process details open on demand.

## Runtime boundary

`system-store.mjs` persists independent conversations, preferences, Skills and output versions.
`system-service.mjs` handles guarded API actions and task lifecycle. `system-agent.mjs` uses the
existing Pi runtime and OpenRouter connection with bounded requests, time and per-task budget.
The general assistant has list/read/save file tools, not shell or arbitrary network tools.

`/` loads the system shell. `/grading` retains the existing grading application, isolated in a
same-origin frame inside the shell. Source grading documents and computed results appear in
Files; their original score/review state is preserved. General task history never imports the
grading transcript or other conversations. Metadata is discoverable; content is read on demand.
Selected or read source versions are pinned by ID, revision and hash, with a durable snapshot.
Generated output records its sources. Later grading updates do not replace those snapshots.

Generated/local files have immutable copies in `files/<id>/v<revision>/<name>` within the data
folder. Edits require the current revision; older versions remain readable. Partial/cancelled
runs preserve their already-saved files and label them partial. Restarted tasks become interrupted.
HTML preview has no script, remote content or navigation capability. Downloads retain exact bytes.

## Implemented scope and limits

- Native browser UI; no build step. This is a local web application, not a native installer.
- Skills: teaching Markdown, HTML slides, CSV tables and code text; local SKILL.md imports default off.
- HTML slides support preview pagination; original PPTX/XLSX editing is not implemented.
- General task execution uses the configured model; verification uses an injected deterministic
  test agent, never an invented production reply or a paid model request.
- Account settings are a local profile; no cloud authentication, billing or cross-device sync.
- Grading uses its existing review/start/stop contracts. This change does not redesign grading.
- Website design and deployment remain separate from the product application.

## Verification and fidelity ledger

Accepted references were the clean homepage and single-artifact working screen from the design
conversation (image IDs `exec-f463e66a-9e86-449e-b294-78a0fef5cbf0` and
`exec-74682db8-1a96-4131-aa5d-7cbfe0a30ce6`). The earlier dense two-sidebar designs are superseded.
The design token and copy inventory was extracted before implementation.

| Comparison | Implementation and evidence |
| --- | --- |
| Layout | One 17.5vw sidebar, at most 278px; no permanent second rail or inspector. |
| Palette | True white main canvas, neutral #f7f7f7 sidebar, fine gray dividers; no colored dashboard cards. |
| Typography | System sans, regular Chinese headline; deliberate navigation, composer and control sizes. |
| Composer | Wide quiet bordered surface, plus, workspace scope and circular send; file source chips move to its lower row in artifact mode. |
| Canvas | One large document/slide preview, filename above, metadata/process on demand, compact composer below. |
| Icons | Thin plus/folder/chevron/arrow SVG controls; navigation remains text-only. |
| Responsive | Verified at 1586×992 (reference dimensions) and 390×844; mobile sidebar becomes an inert, focus-isolated drawer. |
| Motion | 180–240ms state/panel transitions; system and explicit reduced-motion preferences suppress them. |
| Copy | Above-the-fold copy matches the approved inventory, with 工作台 replacing Pi Agent and actual local profile/workspace names. |

Intentional differences: browser-based delivery omits fake macOS traffic lights and 设计稿;
local profile replaces the fictional teacher; imported demo content is explicitly an example;
HTML output uses its real .html extension; editable local outputs have an 编辑 control.
The website and unimplemented native file formats are not represented as functioning features.

Browser validation covered empty-home input, unconfigured-model feedback retaining the draft,
settings persistence, Skill toggle persistence, local file import, edit to v2, version inspection,
download, slide pagination, source references, grading entry and mobile navigation. A delegated
click selector was narrowed to navigation anchors after browser QA caught content clicks opening
history. The canvas padding was corrected, source chips moved to the lower composer row, and
background polling was prevented from reloading the open file preview. Remaining differences are
the explicit delivery/content distinctions above, not unaddressed layout defects.

Screenshots: [home](ui/workbench.jpg), [artifact canvas](ui/artifact.jpg), [mobile](ui/mobile.jpg).
Only synthetic content is used in screenshots. Runtime/test workspaces and provider traces are ignored.
