import test from 'node:test';
import assert from 'node:assert/strict';
import {markingGuideMarkdown} from '../src/marking-guide.mjs';
import {packGuide,unpackGuide,guideSourceSections} from '../src/guide-wire.mjs';
import {digest} from '../src/core.mjs';

const frozen={artifact:{general_instructions:[{text:'Accept equivalent labels.',source_pages:[2]}],unresolved_notes:[],items:[{
  item_id:'Fable',max_score:2,criteria:'Classify the narrative.',source_pages:[2],related_item_ids:[],uncertainties:[],requires_source_image:false,
  scoring_points:[{point_id:'genre',award_type:'A',max_score:2,allowed_awards:[0,2],source_text:'A fable.',condition:'Identify a fable.',depends_on:[],source_pages:[2]}],
  routes:[{route_id:'r',point_ids:['genre'],description:'Any equivalent wording.'}],
},{item_id:'Sound',max_score:1,criteria:'Identify the instrument.',source_pages:[3],related_item_ids:[],uncertainties:[],requires_source_image:false,
  scoring_points:[{point_id:'instrument',award_type:'A',max_score:1,allowed_awards:[0,1],source_text:'Flute.',condition:'Name a flute.',depends_on:[],source_pages:[3]}],
  routes:[{route_id:'r',point_ids:['instrument'],description:''}],
}]}};
const base=markingGuideMarkdown(frozen,'Use short comments.');
const pack=body=>packGuide({body,hash:digest(body),revision:4},frozen);

test('only unchanged generated sections are deduplicated; exact teacher edits round-trip',()=>{
  const before=JSON.stringify(frozen),source=guideSourceSections(frozen),section=source.get('item:Fable');
  for(const body of [base,base.replace('Identify a fable.','Accept allegories too.'),
    base.replace(section,''),base.replace(section,section+'\nTeacher note: no automatic follow-through.\n'),
    base.replace(section,'')+section,base.replace('Name a flute.','Name a flute; review blurred symbols.'),
    '# Custom guide\nRetain a teacher choice unrelated to the generated template.\n']) {
    const packed=pack(body);assert.equal(unpackGuide(packed.parts,frozen),body);assert.equal(packed.hash,digest(body));
    if(body.includes('Accept allegories too.')) {
      assert.ok(packed.parts.some(part=>typeof part==='string'&&part.includes('Accept allegories too.')));
      assert.equal(packed.parts.some(part=>part.source_section==='item:Fable'),false);
    }
  }
  assert.ok(JSON.stringify(pack(base)).length<base.length);
  assert.equal(JSON.stringify(frozen),before);
});

test('source references never resolve to a different source or hide a guide hash mismatch',()=>{
  assert.throws(()=>packGuide({body:base,hash:'wrong',revision:1},frozen),/hash mismatch/);
  assert.throws(()=>unpackGuide([{source_section:'item:Missing'}],frozen),/Invalid guide source reference/);
  const edited=structuredClone(frozen);edited.artifact.items[0].scoring_points[0].condition='Identify a satire.';
  assert.notEqual(digest(unpackGuide(pack(base).parts,edited)),digest(base));
});

test('headings quoted inside source text fall back to the literal guide, never a misbound section',()=>{
  const source=structuredClone(frozen);
  source.artifact.items[0].scoring_points[0].source_text+='\n## Sound · 1 分\nQuoted document heading.';
  const body=markingGuideMarkdown(source,'Keep source headings.');
  const packed=packGuide({body,hash:digest(body),revision:1},source);
  assert.deepEqual(packed.parts,[body]);assert.equal(unpackGuide(packed.parts,source),body);
});
