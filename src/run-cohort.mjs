import { pythonExecutable } from './python.mjs';
import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { randomUUID } from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import { digest } from './core.mjs';
import { createCoordinator, createStudentAgent, StudentRegistry, validateFrozenRubric, parseConcurrency, MAIN_PROMPT, REPLAY_MAIN_PROMPT, studentPromptForProtocol } from './cohort-core.mjs';
import { createRuntime, freezeJson, readImage } from './cohort-runtime.mjs';
import { ResultsStore } from './results-store.mjs';
import { createReporting, REPORTING_INSTRUCTIONS, ECONOMY_REPORTING_INSTRUCTIONS, LEAN_REPORTING_INSTRUCTIONS } from './cohort-reporting.mjs';
import { EVIDENCE_PROTOCOL_PROMPT, EVIDENCE_SUBMIT_SCHEMA } from './point-evidence.mjs';
import { inlineAnnotationSchema, inlineAnnotationPrompt } from './inline-annotations.mjs';
import { MS_REVIEW_PROMPT, MS_REVIEW_SCHEMA } from './ms-review.mjs';
import { runExceptionReview, exceptionRequests, EXCEPTION_REVIEW_PROMPT, EXCEPTION_REVIEW_SCHEMA } from './exception-review.mjs';
import { runStudentFeedback, FEEDBACK_PROMPT, FEEDBACK_SCHEMA } from './student-feedback.mjs';
import { COMPACT_FEEDBACK_PROMPT, COMPACT_FEEDBACK_SCHEMA } from './compact-feedback.mjs';
import {NAMED_FEEDBACK_PROMPT, namedFeedbackSchema} from './focused-feedback.mjs';
import {COMPACT_POINTS_PROMPT,COMPACT_POINTS_SCHEMA} from './compact-points.mjs';
import {SHARED_EVIDENCE_PROMPT,SHARED_EVIDENCE_SCHEMA} from './shared-evidence.mjs';
import {BRIEF_REASON_STYLE,compactPromptForReasons} from './full-credit-reasons.mjs';
import {runIndependentSourceReview,SOURCE_REVIEW_PROMPT,SOURCE_REVIEW_SCHEMA} from './independent-source-review.mjs';
import {PERMISSION_SUBMIT_SCHEMA,sourcePermissionPrompt} from './source-permissions.mjs';
import {CohortProgress} from './cohort-progress.mjs';
import {experimentModel, experimentProvider} from './experiment-models.mjs';
import {GRADING_CORRECTION_OUTPUT_POLICY,STUDENT_SELF_REVIEW_PROMPT} from './submission-contract.mjs';
import {SOURCE_BOUND_FEEDBACK_PROMPT,sourceBoundFeedbackSchema} from './source-bound-feedback.mjs';
import {sourceBoundReportingInstructions,SOURCE_BOUND_REPORT_SCHEMA} from './source-bound-report.mjs';
import { TeacherInteraction } from './teacher-interaction.mjs';
import { runScriptedGrading, validateReplayGuide, DEFAULT_EXECUTION_METHOD } from './scripted-grading.mjs';
import { singlePassSchema, singlePassPrompt } from './single-pass-grading.mjs';

const { values } = parseArgs({ options: {
  manifest: { type: 'string' }, output: { type: 'string' }, env: { type: 'string' },
  execute: { type: 'boolean', default: false }, cap: { type: 'string', default: '2' },
  concurrency: { type: 'string' }, model: { type: 'string', default: 'openai/gpt-6.1-terra' },
  'worker-model': { type: 'string' },
  scripted: { type: 'boolean', default: false },
  'student-cap': { type:'string',default:'0.01' },
  'approved-guide': { type: 'string' },
  'cold-cache-namespace': { type: 'string' },
  'max-requests': { type: 'string', default: '120' },
  rubric: { type: 'string' },
  'interaction-dir': { type: 'string' },
  'student-protocol': { type: 'string' },
  'reason-style': {type:'string'},
  'source-permission-review': {type:'boolean',default:false},
  'isolate-student-cache': { type: 'boolean', default: false },
  'economy-reporting': { type:'boolean',default:false },
  'lean-reports': {type:'boolean',default:false},
  'trim-white-margins': {type:'boolean',default:false},
  'annotation-grid': {type:'boolean',default:false},
  'grading-reasoning': {type:'string',default:'low'},
  'all-ms-images': {type:'boolean',default:false},
  'local-ocr': {type:'boolean',default:false},
  'inline-annotations': {type:'boolean',default:false},
  json: {type:'boolean',default:false},
} });
if (!values.manifest || !values.output) throw Error('Required: --manifest cohort.json --output new-directory');
const output = resolve(values.output); const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const input = JSON.parse(await readFile(resolve(values.manifest), 'utf8'));
const loadDocument = async (directory, role) => {
  const base = resolve(directory); const manifest = JSON.parse(await readFile(resolve(base, 'manifest.json'), 'utf8'));
  const document = structuredClone(manifest.documents[role]);
  if (!document?.pages?.length || !Number.isInteger(manifest.long_side) || manifest.long_side < 1 || manifest.long_side > 50000) throw Error('Expected prepared source image dimensions');
  for (const page of document.pages) {
    page.absolute_path = resolve(base, page.path);
    if (!page.absolute_path.startsWith(base + sep)) throw Error('Input page escapes directory');
    if (digest(await readFile(page.absolute_path)) !== page.sha256) throw Error('Image hash mismatch');
  }
  return document;
};
const concurrency = parseConcurrency(values.concurrency); const cap = Number(values.cap);
const studentCacheNamespace = values['isolate-student-cache'] ? randomUUID() : null;
const economy=values['economy-reporting'],lean=values['lean-reports'];
if(lean&&!economy)throw Error('Lean reports require economy reporting');
const feedbackMode=lean?'source-bound-v5':economy?'compact-v2':'detailed-v1';
const maxRequests = Number(values['max-requests']);
const studentCapUsd=Number(values['student-cap']);
if(!Number.isFinite(studentCapUsd)||studentCapUsd<=0||studentCapUsd>0.01)throw Error('Per-student Luna budget must be positive and no more than $0.01');
if (!Number.isFinite(cap) || cap <= 0 || cap > 5) throw Error('Invalid cohort limits');
if (!Number.isInteger(maxRequests) || maxRequests < 1 || maxRequests > 512) throw Error('Invalid aggregate request limit');
new StudentRegistry(input.students.map(x => x.id), concurrency);
const scheme = await loadDocument(input.scheme_input, 'scheme');
const students = new Map(await Promise.all(input.students.map(async x => [x.id, await loadDocument(x.input, 'student')])));
let reusedRubric = null; let rubricReuse = null;
if (values.rubric) {
  const path = resolve(values.rubric);
  if (!path.endsWith('.json')) throw Error('Expected frozen rubric.json with a .sha256 sidecar');
  const bytes = await readFile(path);
  const fileHash = (await readFile(path.replace(/\.json$/, '.sha256'), 'utf8')).trim();
  if (digest(bytes) !== fileHash) throw Error('Frozen rubric file hash mismatch');
  reusedRubric = validateFrozenRubric(JSON.parse(bytes.toString('utf8')), scheme);
  rubricReuse = { path, file_sha256: fileHash, rubric_hash: reusedRubric.hash, source_sha256: scheme.sha256 };
}
const studentProtocol=values['student-protocol'] ?? (values.scripted?'evidence-v4':reusedRubric?.artifact.version===1?'legacy':'evidence-v3');
if (!['legacy','evidence-v3','evidence-v4','evidence-v5'].includes(studentProtocol)) throw Error('Invalid student protocol');
const pointProtocol=studentProtocol!=='legacy';
const studentSelfReviewEnabled=studentProtocol==='evidence-v4'&&!values.scripted&&!values['source-permission-review'];
const inlineAnnotations=values['inline-annotations'];
const scripted=values.scripted;
const annotationGrid=values['annotation-grid'],gradingReasoning=values['grading-reasoning'];
if(values['local-ocr']&&(!scripted||process.platform!=='darwin'))throw Error('Local optical hints require scripted grading on macOS');
if(annotationGrid&&!scripted)throw Error('Spatial ruler requires scripted grading');
if(!['off','low','medium','high'].includes(gradingReasoning))throw Error('Grading reasoning must be off, low, medium or high');
if(scripted&&studentProtocol!=='evidence-v4')throw Error('Scripted execution requires evidence-v4');
if(values['approved-guide']&&(!scripted||!reusedRubric||values['interaction-dir']))throw Error('Approved guide replay requires scripted frozen rubric without live interaction');
const replayGuide=values['approved-guide']?validateReplayGuide(JSON.parse(await readFile(resolve(values['approved-guide']),'utf8')),reusedRubric):null;
if(inlineAnnotations&&studentProtocol!=='evidence-v4')throw Error('Inline annotations require evidence-v4');
const reasonStyle=values['reason-style']??(scripted?BRIEF_REASON_STYLE:'detailed');
if(scripted&&reasonStyle!==BRIEF_REASON_STYLE)throw Error('Scripted execution supports brief-full-credit reasons only');
if(!['detailed',BRIEF_REASON_STYLE].includes(reasonStyle)||(reasonStyle!=='detailed'&&studentProtocol!=='evidence-v4'))throw Error('Brief full-credit reasons require evidence-v4');
const sourcePermissionReview=values['source-permission-review'];
if(scripted&&sourcePermissionReview)throw Error('Scripted execution defers unresolved source permissions to the teacher; no independent model review');
if(sourcePermissionReview&&studentProtocol!=='evidence-v4')throw Error('Source-permission review requires evidence-v4');
let pointPrompt=studentProtocol==='evidence-v5'?SHARED_EVIDENCE_PROMPT:studentProtocol==='evidence-v4'?compactPromptForReasons(reasonStyle):EVIDENCE_PROTOCOL_PROMPT;
if(sourcePermissionReview)pointPrompt=sourcePermissionPrompt(pointPrompt);
if(inlineAnnotations)pointPrompt=inlineAnnotationPrompt(pointPrompt);
const basePointSchema=sourcePermissionReview?PERMISSION_SUBMIT_SCHEMA:studentProtocol==='evidence-v5'?SHARED_EVIDENCE_SCHEMA:studentProtocol==='evidence-v4'?COMPACT_POINTS_SCHEMA:EVIDENCE_SUBMIT_SCHEMA;
const pointSchema=scripted&&reusedRubric?singlePassSchema({frozen:reusedRubric,student:students.values().next().value,inlineAnnotations,annotationGrid}):inlineAnnotations?inlineAnnotationSchema(basePointSchema):basePointSchema;
if(values['trim-white-margins']&&!['evidence-v4','evidence-v5'].includes(studentProtocol))throw Error('Source-tracked image variants require evidence-v4 or evidence-v5');
const models = createModels(); models.setProvider(openrouterProvider());
const model = experimentModel(models, values.model);
const provider = experimentProvider(model.id);
const workerModel = experimentModel(models, values['worker-model'] ?? (scripted?'openai/gpt-6-luna':values.model));
const workerProvider = experimentProvider(workerModel.id);
await mkdir(output, { recursive: false });
let imageVariants=null;const preparationStarted=Date.now();
if(values['trim-white-margins']||annotationGrid){
  await freezeJson(output,'student-image-input.json',Object.fromEntries(students));
  await promisify(execFile)(pythonExecutable(),[resolve(root,'student_images.py'),'--documents',resolve(output,'student-image-input.json'),'--output',resolve(output,'student-image-variants'),...(annotationGrid?['--grid']:[])],
    {cwd:root,env:{PATH:process.env.PATH},timeout:60000,maxBuffer:1024*1024});
  imageVariants=JSON.parse(await readFile(resolve(output,'student-image-variants/manifest.json'),'utf8'));
  for(const [id,document] of students){
    const variant=imageVariants.documents[id];
    if(variant?.sha256!==document.sha256||variant.pages.length!==document.pages.length||new Set(variant.pages.map(p=>p.page)).size!==document.pages.length)throw Error('Image variant source coverage mismatch');
    for(const page of variant.pages){
      const original=document.pages.find(p=>p.page===page.page);
      if(!original||page.original_sha256!==original.sha256||!page.pixel_identity_verified)throw Error('Image variant source binding mismatch');
      if(!page.absolute_path.startsWith(resolve(output,'student-image-variants')+sep)||digest(await readFile(page.absolute_path))!==page.sha256)throw Error('Image variant bytes mismatch');
    }
  }
}
const imagePreparationSeconds=imageVariants?(Date.now()-preparationStarted)/1000:0;
const opticalStarted=Date.now();let localObservations=null;
if(values['local-ocr']) {
  await freezeJson(output,'local-observation-input.json',Object.fromEntries(students));
  await promisify(execFile)('xcrun',['swift',resolve(root,'student_ocr.swift'),resolve(output,'local-observation-input.json'),resolve(output,'student-local-observations.json')],
    {cwd:root,env:{PATH:process.env.PATH},timeout:120000,maxBuffer:1024*1024});
  localObservations=JSON.parse(await readFile(resolve(output,'student-local-observations.json'),'utf8'));
  for(const [id,doc]of students) {
    const observed=localObservations.documents[id];
    if(observed?.source_sha256!==doc.sha256||observed.pages.length!==doc.pages.length||new Set(observed.pages.map(p=>p.page)).size!==doc.pages.length)throw Error('Optical source coverage mismatch');
  }
}
const opticalPreparationSeconds=localObservations?(Date.now()-opticalStarted)/1000:0;
const sourceHashes = {};
for(const path of ['native_pages.py','prepare.py','workspace_documents.py'])sourceHashes[path]=digest(await readFile(resolve(root,path)));
sourceHashes['src/inline-annotations.mjs']=digest(await readFile(resolve(root,'src/inline-annotations.mjs')));
sourceHashes['src/scripted-grading.mjs']=digest(await readFile(resolve(root,'src/scripted-grading.mjs')));
sourceHashes['src/single-pass-grading.mjs']=digest(await readFile(resolve(root,'src/single-pass-grading.mjs')));
for(const path of ['src/local-observations.mjs','student_ocr.swift'])sourceHashes[path]=digest(await readFile(resolve(root,path)));
if (values['interaction-dir']) for (const path of ['src/teacher-interaction.mjs','src/marking-guide.mjs','src/workspace/editable-documents.mjs', 'src/workspace/canvas-context.mjs', 'src/workspace/documents.mjs', 'src/workspace/store.mjs', 'workspace_crop.py']) sourceHashes[path] = digest(await readFile(resolve(root, path)));
for (const path of ['src/core.mjs', 'src/rubric-contract.mjs', 'src/point-evidence.mjs', 'src/compact-points.mjs', 'src/shared-evidence.mjs', 'src/full-credit-reasons.mjs', 'src/source-permissions.mjs', 'src/independent-source-review.mjs', 'student_images.py', 'src/report-context.mjs', 'src/ms-review.mjs', 'src/exception-review.mjs', 'src/cohort-core.mjs', 'src/cohort-runtime.mjs', 'src/input-context-estimate.mjs', 'src/submission-contract.mjs', 'src/teacher-interaction.mjs','src/marking-guide.mjs','src/workspace/editable-documents.mjs', 'src/experiment-models.mjs', 'src/cohort-progress.mjs', 'src/run-cohort.mjs', 'src/student-feedback.mjs', 'src/source-bound-feedback.mjs', 'src/source-bound-report.mjs', 'src/compact-feedback.mjs', 'src/focused-feedback.mjs', 'src/results-store.mjs', 'src/cohort-reporting.mjs', 'src/report-markdown.mjs', 'analytics.py', 'src/python.mjs', 'gradeos_analysis.py', 'package-lock.json']) sourceHashes[path] = digest(await readFile(resolve(root, path)));
const phaseOutputLimits = { student_self_review: 8192, ms_compilation: 24000, ms_verification: 20000, student_grading: scripted || gradingReasoning === 'high' ? 20000 : 16000, exception_review:4096, source_permission_review:12000 };
if(economy)Object.assign(phaseOutputLimits,{student_feedback:4096,coordination:4096,reporting:4096});
const plan = { version: 2, mode: reusedRubric ? 'frozen-rubric replay' : 'full-cold fixture with shared MS compilation', created_at: new Date().toISOString(),
  source_hashes: sourceHashes, model, economy_reporting:economy, lean_reports:lean, feedback_mode:feedbackMode, main_prompt_hash: digest([reusedRubric ? REPLAY_MAIN_PROMPT : MAIN_PROMPT, lean?sourceBoundReportingInstructions(LEAN_REPORTING_INSTRUCTIONS):economy?ECONOMY_REPORTING_INSTRUCTIONS:REPORTING_INSTRUCTIONS].join('\n\n')), student_prompt_hash: digest(studentPromptForProtocol(studentProtocol)+(studentSelfReviewEnabled?'\n\n'+STUDENT_SELF_REVIEW_PROMPT:'')+(pointProtocol?'\n\n'+pointPrompt:'')), student_protocol:studentProtocol, point_reason_style:reasonStyle, source_permission_review:sourcePermissionReview?{enabled:true,scope:'every primary non-full/null and positive exception independently reviewed',prompt_hash:digest(SOURCE_REVIEW_PROMPT),schema_hash:digest(SOURCE_REVIEW_SCHEMA)}:false, evidence_schema_hash:pointProtocol?digest(pointSchema):null, rubric_reuse: rubricReuse,
  ms_review: 'The main coordinator reviews its saved candidate in the same conversation, retaining original MS images and compilation history until review is submitted; no separate MS reviewer session or duplicate image/candidate packet',
  ms_write: {protocol:'named-source-reference-v2',batching:'model plans complete-item batches within the actual output-token allowance; no fixed item-count limit',output_tokens:phaseOutputLimits.ms_compilation,semantics:'Named fields; null condition explicitly copies complete source text. Canonical fields and validation unchanged.'},
  ms_review_prompt_hash: digest(MS_REVIEW_PROMPT), ms_review_schema_hash: digest(MS_REVIEW_SCHEMA),
  student_self_review:studentSelfReviewEnabled?{mode:'same student agent and conversation',scope:'all items and points including ordinary full credit; local revisions before final persistence',prompt_hash:digest(STUDENT_SELF_REVIEW_PROMPT),independent:false}:false,
  exception_review:{enabled:pointProtocol&&!sourcePermissionReview&&!studentSelfReviewEnabled,prompt_hash:digest(EXCEPTION_REVIEW_PROMPT),schema_hash:digest(EXCEPTION_REVIEW_SCHEMA),
    policy:'Only proposed positive exceptions; independent source-and-answer review with scope/error coverage; no target scores; unresolved stays null. Primary proposal saved separately.'},
  reporting: 'Parallel student grading and same-agent self-review -> immutable final records -> main reads results -> GradeOS analysis and summary',
  student_feedback: 'After each immutable grade, a separate Pi feedback session writes a source-bound summary and per-item comments; it cannot modify awards',
  feedback_prompt_hash: digest(lean?SOURCE_BOUND_FEEDBACK_PROMPT:economy?COMPACT_FEEDBACK_PROMPT:FEEDBACK_PROMPT), feedback_schema_hash: digest(lean?sourceBoundFeedbackSchema.toString():economy?COMPACT_FEEDBACK_SCHEMA:FEEDBACK_SCHEMA),
  source_bound_reporting:lean?{schema_hash:digest(SOURCE_BOUND_REPORT_SCHEMA),authority:'Host renders exact score facts and full source targets; model chooses references and practice actions only; no new score or causal/solution prose'}:false,
  feedback_schema_hash_kind:lean?'generator; exact grade-bound schema frozen in feedback/input-contract.json':'static schema',
  submission_contract:{feedback_tool_choice:'named submit_student_feedback only',validation_context:'diagnostics without duplicate rejected arguments; full transcript preserved',local_grading_correction:'hash-bound complete-item amendments, all grading checks repeated',
    grading_correction_output:GRADING_CORRECTION_OUTPUT_POLICY,grading_correction_tools:'required choice among local item amendments, original-page reads and full-context reopen; merged ledger fully validated',
    grading_correction_context:'request-only checkpoint: complete affected/related items, original general rules, rejected local ledgers, bound relevant images and subsequent tool turns; ambiguous bindings or prior interactive instructions retain full context',
    full_grading_restore:'reopen_grading restores original history and normal output allowance; all rejected drafts can receive local corrections; reservation uses projected wire'},
  scheme, students: Object.fromEntries(students), cap_usd: cap, host_concurrency_limit: concurrency,
  inline_annotations: inlineAnnotations ? { version:annotationGrid?2:1, grid:annotationGrid?'10 columns by 40 rows; original page':'1000', frames:'iN initial image; oN delivered original reinspection', max_regions_per_point:annotationGrid?12:3, invalid_policy:'annotation fallback only; no grade mutation or annotation-only retry' } : false,
  local_optical_hints:localObservations?{engine:localObservations.engine,network_requests:0,preparation_elapsed_seconds:opticalPreparationSeconds,authority:'Optical guesses only; original images and unchanged source criteria remain authoritative',sha256:digest(await readFile(resolve(output,'student-local-observations.json')))}:null,
  preparation_elapsed_seconds:imagePreparationSeconds+opticalPreparationSeconds,
  student_cache_namespace: studentCacheNamespace,
  cache_experiment: studentCacheNamespace ? 'Unique first-user namespace per student/feedback lane, after shared system/MS prefix; same namespace across turns. Verify actual cache receipts.' : 'Provider automatic caching without artificial input isolation',
  max_requests: maxRequests, max_output_tokens: 12000, phase_output_limits: phaseOutputLimits, deadline_seconds: 900, reasoning: 'low', grading_reasoning:gradingReasoning, temperature: null, seed: null,
  provider, model_roles: {main:{model,provider,phases:['ms_compilation','ms_verification','coordination','reporting']},
    worker:{model:workerModel,provider:workerProvider,phases:['student_grading','student_self_review','exception_review','source_permission_review','student_feedback']}},
  network_retries: 0, attempts_per_student: 1, labels_in_model_context: false,
  teacher_interaction: Boolean(values['interaction-dir']),
  image_policy: pointProtocol?'Host supplies the entire own answer book once in the first request, satisfying page delivery; parent selects MS pages. Answer reinspection requires a concrete visual question; source images remain available on demand.':'Parent chooses initial source pages; child reads answers through tools; visual requirements gate submission.',
  initial_student_image_variant:imageVariants?{mode:imageVariants.mode,manifest_sha256:digest(await readFile(resolve(output,'student-image-variants/manifest.json'))),pixel_reduction_fraction:imageVariants.pixel_reduction_fraction,preparation_elapsed_seconds:imagePreparationSeconds}:null,
  context_policy: 'Main preserves the compilation prefix through MS self-review, then receives frozen rubric navigation; scoped source views remain available. Student/exception/feedback sessions stay isolated. Delivered result batches and point/image views can be checkpointed with source-bound notes; context retains score/null/review/source issues and immutable refs.',
  comparison: 'Count declared tasks and actual executions separately; duplicated answer books measure repeatability, not a diverse student population.' };
if(scripted)Object.assign(plan,{execution:'scripted-single-pass',reporting:'Deterministic scripts from immutable grading records; zero model calls',
  student_prompt_hash:digest(singlePassPrompt({inlineAnnotations,annotationGrid})),point_wire_protocol:annotationGrid?'fixed-observed-ink-grid-v3':'fixed-observed-ink-v3',
  student_feedback:'Exact saved evidence and reasons; deterministic rendering; zero model calls',
  exception_review:{enabled:false,policy:'Positive exception proposals withheld as null pending teacher review; raw primary preserved'},
  cold_cache_namespace:values['cold-cache-namespace']??null,approved_guide:replayGuide?{hash:replayGuide.hash,revision:replayGuide.revision}:null,
  image_policy:values['all-ms-images']?'All MS and student pages attached once':'With an adopted guide and verified source compilation, retain visual/unresolved/general-rule MS images; otherwise all MS. Complete student book once; exact selected pages in grading-input-policy.json.',
  attempts_per_student:1,model_roles:{main:{model,provider,phases:reusedRubric?[]:['ms_compilation','ms_verification']},worker:{model:workerModel,provider:workerProvider,phases:['student_grading']}}});
await freezeJson(output, 'plan.json', plan);
await mkdir(resolve(output, 'source-files'));
for (const path of Object.keys(sourceHashes)) { const target = resolve(output, 'source-files', path); await mkdir(dirname(target), {recursive:true}); await writeFile(target, await readFile(resolve(root,path)), {flag:'wx'}); }
if (reusedRubric) await freezeJson(output, 'rubric.json', reusedRubric);
const progress=new CohortProgress({directory:output,studentIds:[...students.keys()],reusedRubric:Boolean(reusedRubric),reasonStyle,...(values.json?{writeLine:()=>{}}:{})});
if (!values.execute) {
  await progress.preflight();
  if(values.json)console.log(JSON.stringify({ status: 'preflight_only', output, students: students.size }));
  process.exit(0);
}
if (values.env) {
  try {process.loadEnvFile(resolve(values.env));}
  catch {await progress.failBeforeRun('未能读取指定的凭据文件，请检查 --env 的文件路径后重试。');if(values.json)console.log(JSON.stringify({status:'not_started',reason:'credential_file_unavailable',output}));process.exit(2);}
}
if (!process.env.OPENROUTER_API_KEY) {
  await progress.failBeforeRun('请配置 OPENROUTER_API_KEY，或通过 --env 选择已有凭据文件后重试。');
  if(values.json)console.log(JSON.stringify({status:'not_started',reason:'credential_missing',output}));
  process.exit(2);
}
await progress.start();
const controller = new AbortController();
const interaction = values['interaction-dir'] ? await new TeacherInteraction(resolve(values['interaction-dir']), { signal: controller.signal,
  schemePages: scheme.pages, students: new Map([...students].map(([id, document]) => [id, document.pages])) }).init() : null;
const runtime = createRuntime({ models, model, workerModel, output, cap, controller, maxRequests, studentCacheNamespace, phaseOutputLimits, progress, interaction, structuredOutput:values.json,provider,workerProvider,
  singlePassGrading:scripted,coldCacheNamespace:values['cold-cache-namespace']??null,studentCapUsd:scripted?studentCapUsd:null });
process.once('SIGINT', () => {void progress.cancelRequested();controller.abort(Error('User cancellation'));});
if(scripted) {
  const started=Date.now();let frozen=reusedRubric,guide=replayGuide,result=null,failure=null;
  try {
    const requirements=interaction?await interaction.requirements():null;
    const needsRequirements=Boolean(requirements?.original&&requirements.review?.status!=='compatible');
    if(!frozen||needsRequirements) {
      let preparer;
      const io=await runtime.io('main',()=>preparer?.getMSPhase()??'coordination');
      preparer=createCoordinator({model,streamFn:io.streamFn,scheme,studentIds:[...students.keys()],readImage,log:io.log,
        prepareOnly:true,reusedRubric,signal:controller.signal,
        persistCandidate:value=>freezeJson(output,'rubric-draft.json',value),persistReview:value=>freezeJson(output,'ms-review.json',value),
        persistRubric:value=>freezeJson(output,'rubric.json',value),
        publishMarkingGuide:interaction?(value,method)=>interaction.publishGuide(value,method):null});
      const detach=io.attach(preparer.agent);
      try{await runtime.run(preparer.agent,preparer.initialPrompt,io.directory);}finally{detach();}
      frozen=preparer.getRubric();guide=preparer.getMarkingGuide();
      if(!frozen||(interaction&&!guide))throw Error('MS and implementation requirements are not ready');
    } else if(interaction) guide=await interaction.publishGuide(frozen,DEFAULT_EXECUTION_METHOD);
    if(guide){await freezeJson(output,'marking-guide.json',guide);await writeFile(resolve(output,'评分实施.md'),guide.body,{flag:'wx'});}
    await runtime.log({type:'rubric_ready'});
    result=await runScriptedGrading({runtime,output,frozen,guide,scheme,students,model:workerModel,concurrency,inlineAnnotations,imageVariants,interaction,gradingReasoning,allMsImages:values['all-ms-images'],localObservations});
  }catch(error){failure=error.message;}
  finally {
    runtime.close();progress.stop();
    const requests=runtime.budget.requests;
    const summary={...result,status:result?.status??'incomplete',failure,execution:'scripted-single-pass',
      started_at:new Date(started).toISOString(),finished_at:new Date().toISOString(),elapsed_seconds:(Date.now()-started)/1000,
      image_preparation_elapsed_seconds:imagePreparationSeconds,optical_preparation_elapsed_seconds:opticalPreparationSeconds,
      preparation_elapsed_seconds:imagePreparationSeconds+opticalPreparationSeconds,
      elapsed_including_image_preparation_seconds:(Date.now()-started)/1000+imagePreparationSeconds,
      elapsed_including_preparation_seconds:(Date.now()-started)/1000+imagePreparationSeconds+opticalPreparationSeconds,
      students:result?.students??[],...runtime.totals(requests),requests,
      costs_by_phase:Object.fromEntries(['ms_compilation','ms_verification','coordination','student_grading','exception_review','student_feedback','reporting'].map(phase=>[phase,runtime.totals(requests.filter(r=>r.phase===phase))])),
      cost_receipts_complete:requests.length>0&&requests.every(r=>r.status==='provider_reported'),active_agents_at_summary:runtime.active.size,
      admission_cap_exceeded:runtime.budget.chargedOrReserved>cap};
    await freezeJson(output,'summary.json',summary);
    await progress.finish(summary,{cancelled:controller.signal.aborted});
    console.log(JSON.stringify({status:summary.status,output,cost_usd:summary.provider_reported_cost_usd,failure}));
    if(summary.status!=='submitted')process.exitCode=2;
  }
} else {
const started = Date.now(); let coordinator; let failure = null; let compilationFinished = null; let msReady = reusedRubric ? started : null;
let msReview = null; let reviewFinished = null;
const mainIO = await runtime.io('main', () => !coordinator ? 'ms_compilation' : coordinator.getMSPhase() ?? (coordinator.registry.terminal() ? 'reporting' : 'coordination'));
const store = new ResultsStore(resolve(output, 'results'), [...students.keys()]); await store.init();
const reporting = createReporting({ store, output, log: mainIO.log, signal: controller.signal,economy,lean,sourceBound:lean,
  getRubric: () => coordinator.getRubric(),
  context: { unique_answer_sources: new Set([...students.values()].map(doc => doc.sha256)).size, requested_students: students.size },
  ensureSealed: async () => {
    if (!coordinator.registry.terminal()) throw Error('Wait for all student tasks before reading shared results');
    const rows = [...coordinator.registry.rows.values()];
    for (const row of rows) if (!store.records.has(row.student_id) && row.status !== 'submitted')
      await store.publish(row.student_id, { status: row.status, failure: row.failure ?? null, rubric_hash: coordinator.getRubric().hash });
    return store.seal(rows, coordinator.getRubric().hash);
  },
});
coordinator = createCoordinator({ model, streamFn: mainIO.streamFn, scheme, studentIds: [...students.keys()], concurrencyLimit: concurrency,
  msCompilationOutputTokens:phaseOutputLimits.ms_compilation,
  readImage, log: mainIO.log, signal: controller.signal, reusedRubric, reporting,
  publishMarkingGuide: interaction ? async (frozen, implementation) => {
    const approved = await interaction.publishGuide(frozen, implementation);
    await freezeJson(output, 'marking-guide.json', approved);
    await writeFile(resolve(output, '评分实施.md'), approved.body, { flag: 'wx', mode: 0o600 });
    return approved;
  } : null,
  persistCandidate: async candidate => {
    await freezeJson(output, 'rubric-draft.json', candidate); compilationFinished = Date.now();
    await runtime.log({type:'stage_terminal',phase:'ms_compilation',elapsed_seconds:(compilationFinished-started)/1000});
    await mkdir(resolve(output,'ms-review'));
    await mainIO.log({type:'stage_start',phase:'ms_verification',candidate_hash:candidate.hash,review_mode:'coordinator'});
  },
  persistReview: async ({review}) => {
    await freezeJson(resolve(output,'ms-review'),'review.json',review); msReview=review;reviewFinished=Date.now();
    await mainIO.log({type:'stage_terminal',phase:'ms_verification',status:'submitted',review_mode:'coordinator',elapsed_seconds:(reviewFinished-compilationFinished)/1000});
  },
  persistRubric: async frozen => {
    await reviewRubricWithTeacher(frozen);
    await freezeJson(output, 'rubric.json', frozen); msReady = Date.now(); await runtime.log({type:'rubric_ready'});
  },
  persistCohort: result => freezeJson(output, 'cohort.json', result),
  executeStudent: async (id, frozen, seedPages, markingGuide) => {
    let child,primaryFinished=null;
    const io = await runtime.io(`student-${id}`, () => child?.getPhase()??'student_grading'); const childStarted = Date.now(); let failure = null;
    await io.log({ type: 'student_task_start', student_id: id, started_at: new Date(childStarted).toISOString(), rubric_hash: frozen.hash });
    child = createStudentAgent({ model:workerModel, streamFn: io.streamFn, frozen, scheme, student: students.get(id), readImage,
      ...(imageVariants?{readInitialStudentImage:page=>readImage(imageVariants.documents[id].pages.find(p=>p.page===page.page)),initialStudentImageMode:imageVariants.mode,initialStudentGeometry:imageVariants.documents[id].pages}:{}),
      inlineAnnotations,gradingReasoning,
      log: io.log, protocol:studentProtocol, reasonStyle, sourcePermissionReview, selfReview:studentSelfReviewEnabled,
      persistPrimary:async(primary,raw)=>{
        await freezeJson(io.directory,'grading-primary.json',primary);await freezeJson(io.directory,'submission-primary.json',raw);primaryFinished=Date.now();
      },persistSubmission:raw=>freezeJson(io.directory,'submission.json',raw), persist: async result => {
        await freezeJson(io.directory, studentSelfReviewEnabled?'grading.json':'grading-primary.json', result);
        if(!studentSelfReviewEnabled)primaryFinished=Date.now();
      } });
    const unsubscribe = io.attach(child.agent);
    try { await runtime.run(child.agent, await child.initialPrompt(seedPages), io.directory); }
    catch (error) { failure = error.message; }
    finally { unsubscribe(); }
    const primary=child.getPrimary()??child.getResult();const primaryElapsed=((primaryFinished??Date.now())-childStarted)/1000;let grade=child.getResult(),exceptionReview=null;
    if (grade&&pointProtocol&&!studentSelfReviewEnabled) {
      try {exceptionReview=await (sourcePermissionReview?runIndependentSourceReview:runExceptionReview)({runtime,model:workerModel,id,primary,frozen,scheme,student:students.get(id)});grade=exceptionReview.grade;}
      catch(error){failure=error.message;grade=null;}
    }
    const gradingElapsed = (Date.now() - childStarted) / 1000;
    let feedback = null;
    if (grade) {
      if(!studentSelfReviewEnabled)await freezeJson(io.directory,'grading.json',grade);
      await io.log({type:'grading_result_saved',student_id:id,review_status:grade.status});
      const gradingPath = resolve(io.directory, 'grading.json');
      try { feedback = await runStudentFeedback({ runtime, model:workerModel, id, grade, frozen, sourcePath: gradingPath,mode:feedbackMode }); }
      catch (error) { feedback = { status: 'failed', failure: error.message }; }
      await store.publish(id, { status: 'submitted', rubric_hash: frozen.hash,
        grading_path: gradingPath, grading_sha256: digest(await readFile(gradingPath)),
        answer_sha256: students.get(id).sha256, writer: 'pi_student_submit_grading',
        feedback_status: feedback.status, feedback_path: feedback.feedback_path ?? null,
        feedback_sha256: feedback.feedback_sha256 ?? null, feedback_failure: feedback.failure ?? null });
    }
    const requests = [...runtime.budget.requests.filter(r => r.lane === `student-${id}`),...(sourcePermissionReview?runtime.budget.requests.filter(r=>r.lane===`source-review-${id}`):exceptionRequests(runtime.budget.requests,id))];
    const summary = { status: grade ? 'submitted' : controller.signal.aborted ? 'cancelled' : 'failed',
      started_at: new Date(childStarted).toISOString(), finished_at: new Date().toISOString(),
      failure: failure || child.agent.state.errorMessage || null, elapsed_seconds: (Date.now() - childStarted) / 1000,
      grading_elapsed_seconds: gradingElapsed, feedback_elapsed_seconds: feedback?.elapsed_seconds ?? null,
      primary_grading_elapsed_seconds:primaryElapsed,primary_total_score:primary?.total_score??null,
      student_self_review:studentSelfReviewEnabled?{status:grade?.self_review?'submitted':primary?'incomplete':'not_started',elapsed_seconds:grade?.self_review?.elapsed_seconds??null,...runtime.totals(runtime.budget.requests.filter(r=>r.lane===`student-${id}`&&r.phase==='student_self_review')),details:grade?.self_review??null}:null,
      ...(sourcePermissionReview?{source_permission_review:exceptionReview?{status:exceptionReview.status,elapsed_seconds:exceptionReview.elapsed_seconds,provider_reported_cost_usd:exceptionReview.provider_reported_cost_usd,changes:grade?.independent_source_review?.changes??[]}:null}:{}),
      exception_review:!sourcePermissionReview&&exceptionReview?{status:exceptionReview.status,elapsed_seconds:exceptionReview.elapsed_seconds,provider_reported_cost_usd:exceptionReview.provider_reported_cost_usd,changes:grade?.exception_review?.changes??[]}:null,
      rubric_hash: frozen.hash, marking_guide_hash: markingGuide?.hash ?? null, total_score: grade?.total_score ?? null, max_score: grade?.max_score ?? null,
      review_status: grade?.status ?? null, continuations: child.getContinuations(), initial_ms_pages: seedPages,
      source_image_pages_delivered: grade?.source_image_pages_delivered ?? null,
      student_pages_delivered: grade?.student_pages_delivered ?? null, feedback, ...runtime.totals(requests), requests };
    await writeFile(resolve(io.directory, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
    await io.log({ type: 'student_task_terminal', student_id: id, status: summary.status, elapsed_seconds: summary.elapsed_seconds,review_status:summary.review_status,feedback_status:feedback?.status??'unavailable' });
    return { student_id: id, status: summary.status, total_score: summary.total_score, review_status: summary.review_status,
      result_path: resolve(io.directory, 'grading.json'), failure: summary.failure, provider_reported_cost_usd: summary.provider_reported_cost_usd,
      feedback_status: feedback?.status ?? 'unavailable', feedback_report_path: feedback?.report_path ?? null };

  },
});
const unsubscribe = mainIO.attach(coordinator.agent);
async function reviewRubricWithTeacher(frozen) {
  if (!interaction || frozen.verification?.status !== 'review_required') return;
  const uncertain = frozen.artifact.items.filter(item => item.uncertainties?.length);
  const pages = [...new Set(uncertain.flatMap(item => item.source_pages))].slice(0, 12);
  await interaction.ask('main', { question: `评分标准中仍有需要确认的条文：${uncertain.map(item => `${item.item_id}：${item.uncertainties.join('；')}`).join('\n') || frozen.artifact.unresolved_notes.join('；')}\n请核对原页并说明是否继续。未明确的规则会保留待定；已冻结的评分标准不会被悄悄改写。`.slice(0, 4000),
    references: pages.map(page => ({ role: 'scheme', page })) });
}
try { if (reusedRubric) await reviewRubricWithTeacher(reusedRubric); await runtime.run(coordinator.agent, coordinator.initialPrompt, mainIO.directory); }
catch (error) { failure = error.message; }
finally {
  unsubscribe(); runtime.close(); progress.stop();
  const result = coordinator.getResult(); const requests = runtime.budget.requests;
  if (compilationFinished) {
    const reviewRequests=requests.filter(row=>row.phase==='ms_verification');
    const reviewSummary={status:msReview?'submitted':'failed',review_mode:'coordinator',lane:'main',
      failure:msReview?null:failure||coordinator.agent.state.errorMessage||'MS self-review not submitted',
      started_at:new Date(compilationFinished).toISOString(),finished_at:new Date(reviewFinished??Date.now()).toISOString(),
      elapsed_seconds:((reviewFinished??Date.now())-compilationFinished)/1000,
      ...runtime.totals(reviewRequests),requests:reviewRequests,candidate_hash:msReview?.candidate_hash??null,
      rubric_hash:msReview?.final_rubric_hash??null,corrections:msReview?.revised_items.map(item=>item.item_id)??[],review_status:msReview?.status??null};
    await writeFile(resolve(output,'ms-review/summary.json'),JSON.stringify(reviewSummary,null,2)+'\n');
    if(!msReview)await mainIO.log({type:'stage_terminal',phase:'ms_verification',status:'failed',elapsed_seconds:reviewSummary.elapsed_seconds});
  }
  const allSubmitted = [...coordinator.registry.rows.values()].every(x => x.status === 'submitted');
  const allFeedbackSubmitted = [...coordinator.registry.rows.values()].every(row => row.feedback_status === 'submitted');
  const summary = { status: result ? allSubmitted && allFeedbackSubmitted ? 'submitted' : 'partial_completed' : 'incomplete',
    failure: failure || coordinator.agent.state.errorMessage || (controller.signal.aborted ? 'Cohort cancelled' : null),
    started_at:new Date(started).toISOString(), finished_at:new Date().toISOString(),
    elapsed_seconds: (Date.now() - started) / 1000, ms_compilation_elapsed_seconds: compilationFinished ? (compilationFinished-started)/1000 : reusedRubric ? 0 : null,
    image_preparation_elapsed_seconds:imagePreparationSeconds,optical_preparation_elapsed_seconds:opticalPreparationSeconds,
    preparation_elapsed_seconds:imagePreparationSeconds+opticalPreparationSeconds,
    elapsed_including_image_preparation_seconds:(Date.now()-started)/1000+imagePreparationSeconds,
    elapsed_including_preparation_seconds:(Date.now()-started)/1000+imagePreparationSeconds+opticalPreparationSeconds,
    ms_ready_at:msReady ? new Date(msReady).toISOString() : null, downstream_elapsed_seconds:msReady ? (Date.now()-msReady)/1000 : null, rubric_hash: coordinator.getRubric()?.hash ?? null,
    main_continuations: coordinator.getContinuations(), students: [...coordinator.registry.rows.values()],
    ...runtime.totals(requests), costs_by_phase: Object.fromEntries(['ms_compilation','ms_verification','coordination','student_grading','student_self_review','exception_review','source_permission_review','student_feedback','reporting'].map(phase => [phase, runtime.totals(requests.filter(r => r.phase === phase))])),
    feedback_submitted: [...coordinator.registry.rows.values()].filter(row => row.feedback_status === 'submitted').length,
    feedback_complete: allFeedbackSubmitted,
    report_submitted: Boolean(reporting.getResult()), report_records_read: reporting.getReadIds(),
    requests, active_agents_at_summary: runtime.active.size,
    cost_receipts_complete: requests.length > 0 && requests.every(x => x.status === 'provider_reported'),
    admission_cap_exceeded: runtime.budget.chargedOrReserved > cap };
  await writeFile(resolve(output, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
  await progress.finish(summary,{cancelled:controller.signal.aborted&&controller.signal.reason?.message==='User cancellation'});
  if(values.json)console.log(JSON.stringify({ status: summary.status, output, costs: summary.costs_by_phase, elapsed_seconds: summary.elapsed_seconds }));
  if (!result || !allSubmitted || !allFeedbackSubmitted) process.exitCode = 2;
}
}
