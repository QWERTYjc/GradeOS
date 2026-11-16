// Small label-blind text-semantic probe. It is not a handwriting or full-paper benchmark.
import { readFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { createStudentAgent } from './cohort-core.mjs';
import { freezeRubric } from './rubric-contract.mjs';
import { createRuntime, freezeJson } from './cohort-runtime.mjs';
import { digest } from './core.mjs';
import {runIndependentSourceReview} from './independent-source-review.mjs';
import {BRIEF_REASON_STYLE} from './full-credit-reasons.mjs';

const {values}=parseArgs({options:{output:{type:'string'},env:{type:'string'},execute:{type:'boolean',default:false},protocol:{type:'string',default:'evidence-v3'},'reason-style':{type:'string',default:'detailed'},'source-permission-review':{type:'boolean',default:false}}});
if(!['evidence-v3','evidence-v4','evidence-v5'].includes(values.protocol))throw Error('Invalid probe protocol');
const reasonStyle=values['reason-style'];
if(!['detailed',BRIEF_REASON_STYLE].includes(reasonStyle)||(reasonStyle!=='detailed'&&values.protocol!=='evidence-v4'))throw Error('Brief reasons require evidence-v4');
const sourcePermissionReview=values['source-permission-review'];
if(sourcePermissionReview&&values.protocol!=='evidence-v4')throw Error('Source review requires evidence-v4');
const probeCap=sourcePermissionReview?.2:.1,probeRequests=sourcePermissionReview?8:4,probeOutput=sourcePermissionReview?8192:4096;
const extendedCases=values.protocol==='evidence-v5'||reasonStyle===BRIEF_REASON_STYLE;
if (!values.output) throw Error('Required --output new-directory');
const output=resolve(values.output);await mkdir(output,{recursive:false});
const task='Apply the entire rule four times the input plus seven. Current operations and arithmetic must be correct; merely naming the operation is insufficient.';
const cases=[
  {id:'Oak',condition:task,answer:'Input t=3. Work: 4*3+7=19.'},
  {id:'Birch',condition:task,answer:'Input y=3. Work: 7+3+3+3+3=19.'},
  {id:'Cedar',condition:task,answer:'Input z=3. Work:\n4(z+1)+3\n=4*4+3\n=19.'},
  {id:'Elm',condition:task,answer:'The earlier part produced my input t=5 (the supplied source input is3). Here I apply 4*5+7=27.'},
  {id:'Fir',condition:task,answer:'Input t=3. Work: 4*3+7=20.'},
  {id:'Ash',condition:task,answer:'Earlier part gave my input t=5 (source input3). Here I apply 3*5+7=22.'},
  {id:'Willow',condition:'Identify the document type as letter. This is a source-identification point, not a numerical follow-through task.',answer:'The document type is report.'},
  {id:'Maple',condition:'Accuracy point: the literal final numeric answer must be19. Do not infer the submitted final digits from correct preceding working. If a needed digit is unreadable, credit is indeterminate.',answer:'Input3. Work is4*3+7. Written final answer:1[second digit obscured and unavailable].'},
  {id:'Cypress',max:2,condition:'Two independently available marks: identify document type letter for1; name its author Mira for1. Award1 if only one requirement is satisfied,2 if both,0 if neither.',answer:'Document type: letter. Author: I do not know.'},
  {id:'Pine',condition:'Accuracy-only point: final value19 is required. This point gives no follow-through credit; the general affine-operation exception applies to operation marks only.',answer:'My earlier input was5; from that I obtained27, so my final answer is27.'},
  {id:'Yew',condition:'Source-exact identification: the code is B7. This point has no exception allowing a missing or changed letter.',answer:'Code A7. I think the source point permits a different letter.'},
];
const sharedPoints=[
  {id:'form',condition:'Form an expression equivalent to 5*2+3. This point tests expression construction only; a wrong equality result does not erase correct expression construction.'},
  {id:'answer',condition:'Explicit final answer must be13. This is an independent accuracy point, no follow-through. An unreadable final digit remains unknown.'},
];
if(extendedCases)cases.push(...[
  {id:'SharedOne',answer:'5*2+3=13.'},
  {id:'SharedTwo',answer:'3+2+2+2+2+2=13.'},
  {id:'SharedThree',answer:'Let z=2.\n5(z+1)-2=13.'},
  {id:'SharedWrongAnswer',answer:'5*2+3=14.'},
  {id:'SharedWrongMethod',answer:'4*2+3=11.'},
  {id:'SharedUnknown',answer:'5*2+3=1[final digit illegible].'},
].map(c=>({...c,max:2,condition:'Two independent points for expression construction and final accuracy. Do not infer one from the other.',points:sharedPoints})),
{id:'SharedLetter',max:2,condition:'Identify document type and author independently.',answer:'The letter was written by Mira.',points:[{id:'type',condition:'Document type letter.'},{id:'author',condition:'Author Mira.'}]},
{id:'SharedWrongAuthor',max:2,condition:'Identify document type and author independently.',answer:'The letter was written by Nora.',points:[{id:'type',condition:'Document type letter.'},{id:'author',condition:'Author Mira.'}]},
{id:'SplitCarry',condition:task,answer_pages:['Earlier part Pebble: my input t=5 (source input was3).','Current part SplitCarry: 4*t+7=27. Using my earlier input.']});
if(sourcePermissionReview)cases.push(
  {id:'LocalAllow',condition:'Compute twice the immediately preceding value plus nine. The final-answer point explicitly accepts a mistaken value from the immediately preceding line in this same part, provided the current doubling and addition are correct.',answer:'Within this part my previous line incorrectly gave v=6 instead of4. Now 2*6+9=21.'},
  {id:'LocalReordered',condition:'Compute nine plus twice the preceding same-part value. Accept a mistaken value from that same part if the current arithmetic and operations are valid.',answer:'Same part, previous line: w=6 (wrong; should be4). Current line: 9+6+6=21.'},
  {id:'LocalChinese',condition:'本小项上一行的数值即使错误，后续正确乘二加九，最终答案这一分仍可给；必须正确执行本行运算。',answer:'本小项上一行误得h=6，正确值为4。下一行：2(h+4)+1=21。'},
  {id:'LocalSplit',condition:'Use twice the previous same-part value plus nine. This final-answer mark accepts a wrong value from that preceding line, subject to correct subsequent operations.',answer_pages:['LocalSplit previous line within this part: input6, although its correct value is4.','LocalSplit current work: 6+6+9=21.']},
  {id:'LocalNewError',condition:'Double the preceding same-part value and add nine. A mistaken value may carry from the previous line, but the present doubling and addition must be correct.',answer:'Previous same-part line gave6 instead of4. Current: 3*6+9=27. I claim the carry permission applies.'},
  {id:'EarlierOnly',condition:'Compute twice the value plus nine. Only a mistaken value inherited from an EARLIER SEPARATE PART is permitted; a new value error within this same part is excluded. No other exception.',answer:'The given starting input for this part is4. Within this same part I mistakenly change it to6. Then 2*6+9=21.'},
  {id:'UnclearCarry',condition:'Final answer26 for input4 using six times input plus two. A carry allowance is printed, but the source does not state whether it covers prior parts only or earlier lines within this part; neither interpretation is established by other source text.',answer:'Inside this same part I make a new error obtaining input7; I then correctly use6*7+2=44.'},
  {id:'ImplicitElsewhere',condition:'Identify the document type as letter. Explicit labels are optional: address, salutation and a personal sign-off elsewhere in THIS answer establish the identification.',answer_pages:['Type field left blank.','Continuation for ImplicitElsewhere: 4 Pine Road. Dear Mira, Thank you for your note. Yours, Nora.']},
  {id:'GenuineBlank',condition:'Identify the document type as letter. Equivalent descriptions or an implicit example in THIS answer are allowed.',answer:'The whole answer and all its continuation space are blank.'},
  {id:'UnrelatedCarry',condition:'Identify a bird as a sparrow. A nearby editorial heading says carry, but there is no scoring allowance for identifying another species.',answer:'The bird is an eagle. carry.'}
);
const instructions=[{text:'For the affine-operation tasks only, valid current operations using an erroneous value inherited from an earlier part may earn credit. This does not excuse a newly incorrect operation or arithmetic. Equivalent valid expressions are accepted.',source_pages:[1]},
  {text:'An unreadable required symbol is unknown, not automatically wrong or repaired from the intended solution.',source_pages:[1]}];
const sourceText=JSON.stringify({general_instructions:instructions,cases:cases.map(({id,condition,points})=>({id,condition,...(points?{points}:{})}))});
const scheme={sha256:digest(sourceText),pages:[{page:1,role:'scheme'}]};
const answerPages=cases.flatMap(entry=>(entry.answer_pages??[entry.answer]).map(text=>`Item ${entry.id} context\n${text}`));
const student={sha256:digest(answerPages),pages:answerPages.map((text,index)=>({page:index+1,role:'student',text}))};
const frozen=freezeRubric({general_instructions:instructions,unresolved_notes:[],items:cases.map(entry=>({
  item_id:entry.id,question_id:entry.id,max_score:entry.max??1,criteria:entry.condition,source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
  scoring_points:(entry.points??[{id:'credit',condition:entry.condition,max:entry.max??1}]).map(p=>({point_id:p.id,max_score:p.max??1,allowed_awards:p.max===2?[0,1,2]:[0,1],award_type:'credit',condition:p.condition,source_text:p.condition,source_pages:[1],depends_on:[]})),
  routes:[{route_id:'rule',point_ids:entry.points?.map(p=>p.id)??['credit'],description:'Apply the supplied source condition.'}],
}))},scheme,new Set([1]));
await freezeJson(output,'rubric.json',frozen);
const gold={Oak:1,Birch:1,Cedar:1,Elm:1,Fir:0,Ash:0,Willow:0,Maple:null,Cypress:1,Pine:0,Yew:0};
if(extendedCases)gold.SplitCarry=1;
if(sourcePermissionReview)Object.assign(gold,{LocalAllow:1,LocalReordered:1,LocalChinese:1,LocalSplit:1,LocalNewError:0,EarlierOnly:0,UnclearCarry:null,ImplicitElsewhere:1,GenuineBlank:0,UnrelatedCarry:0});
const pointGold=extendedCases?{SharedOne:[1,1],SharedTwo:[1,1],SharedThree:[1,1],SharedWrongAnswer:[1,0],SharedWrongMethod:[0,0],SharedUnknown:[1,null],SharedLetter:[1,1],SharedWrongAuthor:[1,0]}:{};
for(const [id,scores] of Object.entries(pointGold))gold[id]=scores.includes(null)?null:scores.reduce((a,b)=>a+b,0);
await freezeJson(output,'posthoc-gold.json',{scores:gold,points:Object.fromEntries(Object.entries(pointGold).map(([id,scores])=>[id,Object.fromEntries(cases.find(c=>c.id===id).points.map((p,i)=>[p.id,scores[i]]))])),review_required:['Maple',...(extendedCases?['SharedUnknown']:[]),...(sourcePermissionReview?['UnclearCarry']:[])],scope:'Predeclared synthetic semantics; no M2 identifiers or answers'});
const sources={};for (const name of ['core.mjs','cohort-core.mjs','rubric-contract.mjs','point-evidence.mjs','compact-points.mjs','shared-evidence.mjs','full-credit-reasons.mjs','source-permissions.mjs','independent-source-review.mjs','cohort-runtime.mjs','probe-point-evidence.mjs']) sources[name]=digest(await readFile(new URL(name,import.meta.url)));
const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
await freezeJson(output,'plan.json',{mode:'synthetic text-semantic probe',protocol:values.protocol,reason_style:reasonStyle,source_permission_review:sourcePermissionReview,model,reasoning:'low',source_hashes:sources,cap_usd:probeCap,max_requests:probeRequests,
  scope:'3 equivalent positive forms, legitimate inherited error,2 new-error hard negatives, unrelated source identification, unreadable required digit, legal partial credit, existing but inapplicable general rule, point rule without exception authority',
  input:cases,labels_in_model_context:false,images:0,MS_review:'Manually constructed synthetic rules; no model MS compilation/verification'});
if (!values.execute) {console.log(JSON.stringify({status:'preflight',output}));process.exit(0);}
if (values.env) process.loadEnvFile(resolve(values.env));
if (!process.env.OPENROUTER_API_KEY) throw Error('Credential missing');
const controller=new AbortController();const runtime=createRuntime({models,model,output,cap:probeCap,controller,maxRequests:probeRequests,maxOutputTokens:probeOutput});
const io=await runtime.io('probe',()=> 'semantic_probe');const started=Date.now();let failure=null;
const child=createStudentAgent({model,streamFn:io.streamFn,frozen,scheme,student,protocol:values.protocol,reasonStyle,sourcePermissionReview,log:io.log,
  readImage:async page=>({type:'text',text:page.role==='scheme'?sourceText:page.text}),
  persistSubmission:raw=>freezeJson(io.directory,'submission.json',raw),persist:grade=>freezeJson(io.directory,'grading.json',grade)});
const unsubscribe=io.attach(child.agent);
try {await runtime.run(child.agent,await child.initialPrompt([]),io.directory);}catch(error){failure=error.message;}
finally {unsubscribe();}
let grade=child.getResult(),independentReview=null;
if(grade&&sourcePermissionReview){try{independentReview=await runIndependentSourceReview({runtime,model,id:'probe',primary:grade,frozen,scheme,student,loadImage:async page=>({type:'text',text:page.role==='scheme'?sourceText:page.text})});grade=independentReview.grade;await freezeJson(io.directory,'grading-reviewed.json',grade);}catch(error){failure=error.message;grade=null;}}
runtime.close();
const summary={independent_review:independentReview?{status:independentReview.status,elapsed_seconds:independentReview.elapsed_seconds,provider_reported_cost_usd:independentReview.provider_reported_cost_usd}:null,status:grade?'submitted':'incomplete',failure:failure||child.agent.state.errorMessage||null,
  elapsed_seconds:(Date.now()-started)/1000,...runtime.totals(runtime.budget.requests),requests:runtime.budget.requests,active_agents_at_summary:runtime.active.size};
await freezeJson(output,'summary.json',summary);
if (!grade || runtime.active.size || runtime.budget.requests.some(r=>r.status!=='provider_reported')) {console.log(JSON.stringify(summary));process.exit(2);}
// Load expectations only after every request has a terminal receipt. The grader never receives this file.
const reference=JSON.parse(await readFile(resolve(output,'posthoc-gold.json'),'utf8'));
const checks=grade.items.map(item=>({item_id:item.item_id,expected:reference.scores[item.item_id],actual:item.score,review_required:item.review_required,
  pass:item.score===reference.scores[item.item_id]&&(!reference.review_required.includes(item.item_id)||item.review_required)&&(!reference.points[item.item_id]||item.point_decisions.every(p=>p.score===reference.points[item.item_id][p.point_id]))}));
await freezeJson(output,'evaluation.json',{evaluated_at:new Date().toISOString(),checks,matched:checks.filter(row=>row.pass).length,total:checks.length});
console.log(JSON.stringify({status:summary.status,matched:checks.filter(row=>row.pass).length,total:checks.length,cost_usd:summary.provider_reported_cost_usd,elapsed_seconds:summary.elapsed_seconds,output}));
if (checks.some(row=>!row.pass)) process.exitCode=3;
