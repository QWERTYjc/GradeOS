import test from 'node:test';
import assert from 'node:assert/strict';
import { bindSelection, hitSelection, selectionBounds } from '../web/canvas-selection.mjs';
import { WorkspaceCanvas } from '../web/workspace-canvas.mjs';

test('editable document comments render without a source-page parent', () => {
  const workspace = Object.create(WorkspaceCanvas.prototype);
  const marker = { dataset: { pin: 'text-note' }, style: {}, classList: { toggle() {} },
    querySelector: () => ({ setAttribute() {} }) };
  const pins = { children: [marker] };
  const root = { querySelector: name => name === '.document-annotations' ? pins : name === '.pane-content' ? { clientHeight: 600 } : null,
    querySelectorAll: () => [] };
  const panel = { documentId: 'guide', root, editor: { annotationTop: () => 100 } };
  workspace.annotations = () => [{ id: 'text-note', target: { documentId: 'guide', start: 0, end: 12 } }];
  workspace.renderPins(panel);
  assert.equal(marker.hidden, false);
  assert.equal(marker.style.top, '100px');
  assert.match(pins.innerHTML, /annotation-marker/);
});

function canvasFixture(t, { mode = 'lasso', selections = [], scale = 1 } = {}) {
  const priorWindow = globalThis.window, priorObserver = globalThis.ResizeObserver;
  globalThis.window = { devicePixelRatio: 2 };
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
  const handlers = new Map(), captured = new Set(), frames = [], created = [], activated = [], errors = [];
  const bounds = { left: 100, top: 75, width: 500 * scale, height: 800 * scale };
  let commands = [];
  const context = Object.fromEntries(['setTransform', 'clearRect', 'setLineDash', 'beginPath', 'moveTo', 'lineTo', 'closePath', 'rect', 'fill'].map(name => [name, (...args) => {
    if (name === 'clearRect') commands = [];
    commands.push([name, ...args]);
  }]));
  context.stroke = () => frames.push([...commands]);
  const canvas = { style: {}, getContext: () => context, getBoundingClientRect: () => bounds,
    setPointerCapture: id => captured.add(id), releasePointerCapture: id => captured.delete(id), hasPointerCapture: id => captured.has(id),
    addEventListener: (name, handler) => handlers.set(name, handler), removeEventListener: name => handlers.delete(name) };
  const binding = bindSelection(canvas, { getPage: () => ({ id: 'source', sha256: 'original' }), getMode: () => mode, getSelections: () => selections,
    onSelect: region => { created.push(region); selections.push(region); }, onActivate: region => activated.push(region), onInvalid: error => errors.push(error) });
  t.after(() => { binding.destroy(); globalThis.window = priorWindow; globalThis.ResizeObserver = priorObserver; });
  const event = ([x, y], extra = {}) => ({ button: 0, pointerId: 1, clientX: bounds.left + x * bounds.width, clientY: bounds.top + y * bounds.height, preventDefault() {}, ...extra });
  const emit = (name, point, extra) => handlers.get(name)(event(point, extra));
  return { binding, frames, created, activated, errors, captured, emit, event, selections, bounds, handlers };
}

test('lasso draws an open dashed stroke and closes only on release, without opening a comment', t => {
  const f = canvasFixture(t), path = [[.1, .2], [.2, .1], [.6, .1], [.55, .5], [.3, .3], [.11, .21]];
  f.emit('pointerdown', path[0]);
  for (const point of path.slice(1, -1)) f.emit('pointermove', point);
  assert.ok(f.frames.every(frame => !frame.some(([name]) => ['closePath', 'fill'].includes(name))));
  assert.deepEqual(f.frames.at(-1).find(([name]) => name === 'setLineDash'), ['setLineDash', [5, 4]]);
  f.emit('pointerup', path.at(-1));
  assert.equal(f.created.length, 1); assert.deepEqual(f.created[0].points, path);
  assert.ok(f.frames.at(-1).some(([name]) => name === 'closePath'));
  assert.equal(f.activated.length, 0); assert.equal(f.captured.size, 0);
});

test('freehand hits preserve the concave outline at different zooms, including the closing edge', () => {
  const points = [[.1, .1], [.8, .1], [.8, .3], [.3, .3], [.3, .8], [.1, .8]];
  const shape = { id: 'concave', shape: 'lasso', points, rect: selectionBounds(points) };
  for (const scale of [.6, 1, 2]) {
    const bounds = { width: 500 * scale, height: 800 * scale };
    assert.equal(hitSelection([.2, .65], [shape], bounds), shape);
    assert.equal(hitSelection([.65, .2], [shape], bounds), shape);
    assert.equal(hitSelection([.65, .65], [shape], bounds), undefined, 'empty notch must not act like the bounding box');
    assert.equal(hitSelection([.1 - 4 / bounds.width, .4], [shape], bounds), shape, 'edge tolerance stays in screen pixels');
    assert.equal(hitSelection([.1 - 9 / bounds.width, .4], [shape], bounds), undefined);
  }
  assert.equal(hitSelection([.2, .2], [shape, { ...shape, id: 'top' }], { width: 500, height: 800 }).id, 'top');
});

test('reading mode clicks open only regions on this page and never capture scrolling gestures', t => {
  const selections = [{ id: 'one', pageId: 'source', shape: 'rectangle', rect: { x: .1, y: .1, width: .3, height: .3 } },
    { id: 'other-page', pageId: 'other', shape: 'rectangle', rect: { x: .1, y: .1, width: .3, height: .3 } }];
  const f = canvasFixture(t, { mode: 'browse', selections });
  f.emit('pointerdown', [.2, .2]); f.emit('pointermove', [.2, .4]); f.emit('pointerup', [.2, .4]);
  assert.equal(f.captured.size, 0); assert.equal(f.created.length, 0); assert.equal(f.activated.length, 0);
  f.emit('click', [.2, .2]); f.emit('click', [.8, .8]);
  assert.deepEqual(f.activated.map(region => region?.id || null), ['one', null]);
});

test('lasso taps reopen a region, while dragging over it starts another selection', t => {
  const region = { id: 'one', pageId: 'source', shape: 'rectangle', rect: { x: .1, y: .1, width: .5, height: .5 } };
  const f = canvasFixture(t, { selections: [region] });
  f.emit('pointerdown', [.2, .2]); f.emit('pointerup', [.201, .2]);
  assert.equal(f.activated[0], region); assert.equal(f.errors.length, 0);
  f.emit('pointerdown', [.2, .2]);
  f.emit('pointermove', [.5, .2], { getCoalescedEvents: () => [f.event([.3, .1]), f.event([.4, .15])] });
  f.emit('pointermove', [.5, .5]); f.emit('pointerup', [.2, .2]);
  assert.equal(f.created.length, 1);
  assert.deepEqual(f.created[0].points.slice(1, 3), [[.3, .1], [.4, .15]]);
  assert.equal(f.activated.length, 1, 'drawing does not reopen the prior note');
});

test('a cancelled, secondary-pointer, or straight-line gesture cannot leave a bogus selection', t => {
  const f = canvasFixture(t);
  f.emit('pointerdown', [.1, .1]); f.emit('pointermove', [.8, .8], { pointerId: 2 }); f.emit('pointerup', [.8, .8], { pointerId: 2 });
  assert.equal(f.created.length, 0); assert.equal(f.captured.size, 1);
  f.emit('pointercancel', [.1, .1]); assert.equal(f.captured.size, 0);
  f.emit('pointerdown', [.1, .1], { isPrimary: false }); assert.equal(f.captured.size, 0);
  f.emit('pointerdown', [.1, .1]); f.emit('pointermove', [.4, .4]); f.emit('pointerup', [.8, .8]);
  assert.equal(f.created.length, 0); assert.equal(f.errors.length, 1);
  f.emit('pointerdown', [.1, .1]); f.emit('pointermove', [.5, .2]); f.binding.cancel(); f.emit('pointerup', [.1, .1]);
  assert.equal(f.created.length, 0);
});

test('dismissing a comment retains its draft and clears active selection', t => {
  const previousDocument=globalThis.document;globalThis.document={body:{classList:{remove(){}}}};
  t.after(()=>{globalThis.document=previousDocument;});
  const panel = {}, workspace = Object.create(WorkspaceCanvas.prototype);
  Object.assign(workspace, { root:{classList:{remove(){}}}, note: { row: { id: 'one' }, panel }, noteDrafts: new Map(), panels: [panel],
    popover: { hidden: false, querySelector: () => ({ value: 'A draft that has not been saved' }) }, renderPins() {} });
  workspace.closeNote();
  assert.equal(workspace.noteDrafts.get('one'), 'A draft that has not been saved');
  assert.equal(workspace.popover.hidden, true); assert.equal(workspace.note, null);
});

test('a slow save cannot close or reference another comment opened in the meantime', async () => {
  let resolve, referenced;
  const row = { id: 'one', pending: true, target: { pageId: 'source' }, text: '' };
  const workspace = Object.create(WorkspaceCanvas.prototype);
  Object.assign(workspace, { note: { row, panel: {} }, pending: [row], noteDrafts: new Map(),
    popover: { querySelector: () => ({ value: 'First note' }) }, request: () => new Promise(done => { resolve = done; }),
    onReference: reference => { referenced = reference; }, renderPins() {}, closeNote: () => assert.fail('Must keep the second note open') });
  const save = workspace.noteAction('reference');
  workspace.note = { row: { id: 'two' }, panel: {} };
  resolve({ annotation: { ...row, id: 'saved-one', pending: false, text: 'First note' } }); await save;
  assert.equal(referenced.annotationId, 'saved-one'); assert.equal(workspace.note.row.id, 'two'); assert.equal(workspace.pending.length, 0);
});
