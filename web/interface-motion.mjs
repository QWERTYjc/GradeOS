// One responsive print surface per document, including the embedded grading reader.
const controlSelector = 'button, a[href], summary, [role="tab"], [role="switch"], .composer-model, .scope-picker label';
const rowSelector = '.archive-file, .cohort-student, .staged-file, .skill-row, .connection-row';
const preference = matchMedia('(prefers-reduced-motion: reduce)');
let active = null, frame = 0, pointer = null;

function surface(element) {
  if (!(element instanceof Element) || element.closest('.wordmark, .canvas-wordmark, .skip-link, .page-image, .annotation-target, .annotation-marker, :disabled, [aria-disabled="true"]')) return null;
  const control = element.closest(controlSelector);
  if (control?.matches('.student-toggle[aria-expanded="false"]')) return control.closest('.cohort-student');
  if (control?.matches('.archive-file-open')) return control.closest('.archive-file');
  if (control) return control;
  const row = element.closest(rowSelector);
  if (row?.matches('.cohort-student') && !row.querySelector('.student-toggle[aria-expanded="false"]')) return null;
  return row;
}

function clear() {
  if (!active) return;
  active.removeAttribute('data-illuminated');
  active.style.removeProperty('--surface-x');
  active.style.removeProperty('--surface-y');
  active = null;
}

function illuminate(next, position) {
  if (active !== next) { clear(); active = next; }
  if (!active) return;
  const rect = active.getBoundingClientRect();
  if (!rect.width || !rect.height) return clear();
  const track = position && !preference.matches && document.documentElement.dataset.motion !== 'reduce';
  // Reduced motion and keyboard use a fixed patch, leaving the focus outline intact.
  const x = track ? Math.round(position.x - rect.left) + 'px' : '75%';
  const y = track ? Math.round(position.y - rect.top) + 'px' : '50%';
  active.style.setProperty('--surface-x', x);
  active.style.setProperty('--surface-y', y);
  if (!active.hasAttribute('data-illuminated')) active.setAttribute('data-illuminated', '');
}

function update() {
  frame = 0;
  if (pointer) illuminate(surface(document.elementFromPoint(pointer.x, pointer.y)), pointer);
  else illuminate(document.activeElement?.matches(':focus-visible') ? surface(document.activeElement) : null);
}
function schedule() {
  if (!frame) frame = requestAnimationFrame(update);
}
function leave() {
  pointer = null;
  if (frame) cancelAnimationFrame(frame);
  frame = 0;
  clear();
}
function move(event) {
  if (event.pointerType === 'touch') return leave();
  pointer = { x:event.clientX, y:event.clientY };
  schedule();
}
for (const type of ['pointermove', 'pointerover', 'pointerdown']) document.addEventListener(type, move, {passive:true});
document.addEventListener('pointerout', event => { if (!event.relatedTarget) leave(); });
document.addEventListener('pointercancel', leave);
document.addEventListener('focusin', event => {
  if (event.target.matches(':focus-visible')) { pointer = null; schedule(); }
});
document.addEventListener('focusout', schedule);
document.addEventListener('scroll', schedule, {capture:true, passive:true});
window.addEventListener('blur', leave);
preference.addEventListener('change', schedule);
new MutationObserver(schedule).observe(document.documentElement, {attributes:true, attributeFilter:['data-motion']});
