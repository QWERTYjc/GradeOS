// Synthetic source/work only. No expected decisions or examination labels are exposed.
import {digest,validateGrade} from './core.mjs';
import {freezeRubric} from './rubric-contract.mjs';
import {expandPointEvidence} from './point-evidence.mjs';

export function exceptionProbeFixture() {
  const general='For dependent numerical parts, a method mark may follow an erroneous input from the earlier part, provided the current operation and arithmetic are correct. This rule applies only to numerical method marks; it does not cover a new error in the current part.';
  const ordinary='Method mark: correctly apply four times the input plus seven.';
  const cases=[
    {id:'Oak',condition:ordinary,answer:'Earlier part gave x=5 instead of3. Here:4*5+7=27.',origin:'inherited',rule:'G1'},
    {id:'Birch',condition:ordinary,answer:'Earlier part gave y=5 instead of3. Here:7+y+y+y+y=27.',origin:'inherited',rule:'G1'},
    {id:'Cedar',condition:ordinary,answer:'前一小题给出z=5而非3。本问计算四倍z再加七，得27。',origin:'inherited',rule:'G1'},
    {id:'Ash',condition:ordinary,answer:'Earlier part gave x=5 instead of3. Here I newly use three times x plus seven:3*5+7=22.',origin:'mixed',rule:'G1'},
    {id:'Fir',condition:ordinary,answer:'Earlier part correctly gave x=3. Within THIS part I first copy x as5, then compute4*5+7=27.',origin:'current',rule:'G1',correctPrior:true},
    {id:'Elm',condition:'Accuracy mark, local f.t.: accept the final value obtained by correct multiplication by four and addition of seven using ANY numeric value the student copied in this same part, including an incorrect copy. No earlier method marks are prerequisites.',answer:'Earlier part correctly gave x=3. Within THIS part I copy x as5, then compute4*5+7=27.',origin:'current',rule:'P',correctPrior:true},
    {id:'Willow',condition:'Accuracy mark: final19, f.t. The source supplies no further specification of which local errors or carried inputs this f.t. includes.',answer:'Earlier part correctly gave x=3. Within THIS part I change the input to5, then compute4*5+7=27.',origin:'current',rule:'P',correctPrior:true},
    {id:'Maple',condition:ordinary,answer:'Earlier part gave x=5 instead of3. The current multiplier and final result are covered by an opaque sticker; no alternative page is available.',origin:'inherited',rule:'G1'},
    {id:'Yew',condition:'Source identification accuracy mark: identify the document type as letter. This point has no follow-through rule.',answer:'Earlier numerical part gave x=5 instead of3. The document here is a letter, but I wrote report.',origin:'current',rule:'G1'},
  ];
  const scheme={sha256:digest(cases),pages:[{page:1,role:'scheme'}]};
  const student={sha256:digest(cases.map(c=>c.answer)),pages:cases.flatMap((c,n)=>[
    {page:n*2+1,role:'student',text:`${c.id}-input: ${c.correctPrior?'x=3 (correct)':'x=5 (incorrect; the given source value is3)'}`},
    {page:n*2+2,role:'student',text:`${c.id}: ${c.answer}`},
  ])};
  const makeItem=(id,condition,related)=>({item_id:id,question_id:id,max_score:1,criteria:condition,source_pages:[1],related_item_ids:related,requires_source_image:false,image_reason:'',uncertainties:[],
    scoring_points:[{point_id:'credit',max_score:1,allowed_awards:[0,1],award_type:'credit',condition,source_text:condition,source_pages:[1],depends_on:[]}],
    routes:[{route_id:'normal',point_ids:['credit'],description:'Evaluate the whole stated condition.'}]});
  const frozen=freezeRubric({general_instructions:[{text:general,source_pages:[1]}],unresolved_notes:[],items:cases.flatMap(c=>[
    makeItem(`${c.id}-input`,'Source accuracy point: input must be3; no follow-through at this point.',[]),makeItem(c.id,c.condition,[`${c.id}-input`]),
  ])},scheme,new Set([1]));
  const raw={review_notes:[],items:cases.flatMap((c,n)=>[
    {id:`${c.id}-input`,route:'normal',review:false,p:[['credit',c.correctPrior?1:0,student.pages[n*2].text,[n*2+1],c.correctPrior?'met':'unmet',c.correctPrior?'none':'current','','Compare literal source input.']]},
    {id:c.id,route:'normal',review:true,p:[['credit',1,c.answer,[n*2+2],'exception',c.origin,c.rule,'Candidate proposal: follow-through may allow this answer. Independently verify its scope.']]},
  ])};
  const primary={...validateGrade(expandPointEvidence(raw,frozen,student),{documents:{scheme,student}},new Set(['scheme:1',...student.pages.map(p=>`student:${p.page}`)])),source_issues:[],protocol:'evidence-v3',rubric_hash:frozen.hash};
  const sourceText=JSON.stringify(frozen.artifact);
  return {frozen,scheme,student,primary,loadImage:async page=>({type:'text',text:page.role==='scheme'?sourceText:page.text})};
}
