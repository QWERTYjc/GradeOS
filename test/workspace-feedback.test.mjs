import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Agent } from '@earendil-works/pi-agent-core';
import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { createRuntime } from '../src/cohort-runtime.mjs';
import { TeacherInteraction } from '../src/teacher-interaction.mjs';
import { requireFeedbackSubmission } from '../src/submission-contract.mjs';
import { createFeedbackAgent } from '../src/student-feedback.mjs';
import { exceptionProbeFixture } from '../src/exception-probe-fixture.mjs';
import { digest } from '../src/core.mjs';

test('interactive feedback preserves its terminal-only tool contract and receives the adopted guide', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'pi-feedback-bridge-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const interaction = await new TeacherInteraction(join(directory, 'interaction')).init();
  const body = 'Use the confirmed source-bound implementation; retain unresolved evidence.';
  interaction.guide = { revision: 2, body, hash: digest(body) };
  const models = createModels(); models.setProvider(openrouterProvider());
  const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
  const runtime = createRuntime({ models, model, output: directory, cap: 1, controller: new AbortController(), interaction });
  t.after(() => runtime.close());
  const fixture = exceptionProbeFixture();
  for (const mode of ['detailed-v1', 'compact-v2', 'source-bound-v5']) {
    const io = await runtime.io(`feedback-${mode}`, () => 'student_feedback');
    const child = createFeedbackAgent({ model, streamFn: () => assert.fail('No paid call'), grade: fixture.primary, frozen: fixture.frozen, mode, log: async () => {}, persist: async () => {} });
    const detach = io.attach(child.agent); t.after(detach);
    const payload = { tools: child.agent.state.tools.map(tool => ({ type: 'function', function: { name: tool.name } })) };
    assert.doesNotThrow(() => requireFeedbackSubmission(payload, 'student_feedback'));
    assert.deepEqual(payload.tool_choice, { type: 'function', function: { name: 'submit_student_feedback' } });
    const prompt = JSON.stringify(await interaction.preparePrompt(child.agent, child.initialPrompt));
    assert.ok(prompt.includes(body)); assert.ok(prompt.includes(interaction.guide.hash));
    assert.doesNotMatch(child.agent.state.systemPrompt, /use ask_teacher/);
  }
  const io = await runtime.io('student-neutral', () => 'student_grading');
  const student = new Agent({ streamFn: () => assert.fail('No paid call'), initialState: { model, systemPrompt: 'Read source evidence.', tools: [] } });
  t.after(io.attach(student));
  assert.ok(student.state.tools.some(tool => tool.name === 'ask_teacher'));
  assert.ok(student.state.tools.some(tool => tool.name === 'read_teacher_selection'));
});

test('single-pass interaction appends the exact approved guide after the complete answer input',async t=>{
  const directory=await mkdtemp(join(tmpdir(),'pi-guide-order-'));
  t.after(()=>rm(directory,{recursive:true,force:true}));
  const interaction=await new TeacherInteraction(join(directory,'interaction')).init();
  const body='Accept a valid alternative method; retain uncertain source readings.';
  interaction.guide={revision:7,body,hash:digest(body)};
  const models=createModels();models.setProvider(openrouterProvider());
  const agent=new Agent({initialState:{model:models.getModel('openrouter','openai/gpt-6-luna'),systemPrompt:'Grade once.',tools:[]},streamFn:()=>assert.fail('No paid call')});
  t.after(interaction.attach(agent,'student-neutral',{interactiveTools:false,singlePass:true}));
  const original={role:'user',timestamp:1,content:[{type:'image',data:'full-page-one',mimeType:'image/png'},{type:'image',data:'full-page-two',mimeType:'image/png'},{type:'text',text:'Frozen source conditions.'}]};
  const prepared=await interaction.preparePrompt(agent,original);
  assert.deepEqual(prepared[0],original);
  assert.equal(prepared.length,2);
  const suffix=prepared[1].content[0].text;
  assert.ok(suffix.includes(`execution document v7, hash ${digest(body)}:\n${body}\n`));
  assert.equal(JSON.stringify(prepared).split(body).length-1,1);
  assert.deepEqual(agent.state.tools,[]);
});
