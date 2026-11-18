export const normalizedPoint = (clientX, clientY, bounds) => [
  Math.max(0, Math.min(1, (clientX - bounds.left) / bounds.width)),
  Math.max(0, Math.min(1, (clientY - bounds.top) / bounds.height)),
];
export function selectionBounds(points) {
  const xs = points.map(point => point[0]), ys = points.map(point => point[1]);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
}

// Hit the actual freehand region, including a small screen-space allowance at its edge.
export function hitSelection(point, selections, bounds, tolerance = 6) {
  const [px, py] = point.map((value, index) => value * (index ? bounds.height : bounds.width));
  const hits=selections.filter(selection => {
    const { x, y, width, height } = selection.rect;
    const polygon = selection.shape === 'lasso' ? selection.points : [[x, y], [x + width, y], [x + width, y + height], [x, y + height]];
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const [ax, ay] = [polygon[j][0] * bounds.width, polygon[j][1] * bounds.height];
      const [bx, by] = [polygon[i][0] * bounds.width, polygon[i][1] * bounds.height];
      const dx = bx - ax, dy = by - ay;
      const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy || 1)));
      if (Math.hypot(px - ax - t * dx, py - ay - t * dy) <= tolerance) return true;
      if ((ay > py) !== (by > py) && px < (bx - ax) * (py - ay) / (by - ay) + ax) inside = !inside;
    }
    return inside;
  });
  // A narrow step inside a broader result is the more specific target. Manual
  // circles retain their existing topmost priority; scoring points stay distinct.
  return hits.findLast(selection=>!selection.generated)||hits.sort((a,b)=>a.rect.width*a.rect.height-b.rect.width*b.rect.height)[0];
}

export function bindSelection(canvas, { getPage, getMode, getSelections, onSelect, getActiveId = () => null,getHoveredId = () => null,
  onActivate = () => {}, onHover = () => {}, onInvalid = () => {}, onLayout = () => {} }) {
  const context = canvas.getContext('2d'); let gesture = null, hovered = null;
  const selections = () => getSelections().filter(selection => selection.pageId === getPage()?.id);
  const draw = () => {
    const { width, height } = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * ratio)) canvas.width = Math.round(width * ratio);
    if (canvas.height !== Math.round(height * ratio)) canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    const visible = selections();
    if (gesture) visible.push({ shape: gesture.mode, points: gesture.points, rect: selectionBounds(gesture.points), live: true });
    for (const selection of visible) {
      const active = (selection.annotationId || selection.id) === getActiveId();
      const hoverId=getHoveredId()||hovered;
      const highlighted=hoverId?(selection.annotationId||selection.id)===hoverId:active;
      if(selection.generated&&!highlighted)continue;
      context.beginPath(); context.lineWidth = 1.5; context.lineCap = 'round'; context.lineJoin = 'round';
      context.setLineDash(selection.generated ? [] : [5, 4]);
      context.strokeStyle = selection.generated
        ? ({credit:'#176441',deduction:'#a33636',review:'#80560d'}[selection.tone]||'#566881') : active||selection.live?'#0759d4':'#566881';
      context.globalAlpha=1;
      if(selection.generated&&selection.shape!=='lasso') {
        const r=selection.rect,x=r.x*width,y=r.y*height,w=r.width*width,h=r.height*height;
        context.lineWidth=active?2:1.5;context.roundRect(x,y,w,h,Math.min(4,w/4,h/4));
        context.fillStyle={credit:'rgba(23,100,65,.09)',deduction:'rgba(163,54,54,.09)',review:'rgba(128,86,13,.09)'}[selection.tone]||'rgba(7,89,212,.06)';context.fill();
        context.stroke();context.globalAlpha=1;continue;
      }
      if (selection.shape === 'lasso') {
        selection.points.forEach(([x, y], index) => index ? context.lineTo(x * width, y * height) : context.moveTo(x * width, y * height));
        // Keep the moving stroke open. Closing every frame creates a distracting moving chord.
        if (!selection.live) context.closePath();
      } else { const { x, y, width: w, height: h } = selection.rect; context.rect(x * width, y * height, w * width, h * height); }
      if (active && !selection.live) { context.fillStyle = 'rgba(7,89,212,.035)'; context.fill('evenodd'); }
      context.stroke();
      context.globalAlpha = 1;
    }
  };
  const point = (event, bounds = canvas.getBoundingClientRect()) => normalizedPoint(event.clientX, event.clientY, bounds);
  const hit = event => hitSelection(point(event), selections(), canvas.getBoundingClientRect());
  const hover = selection => { const id = selection?.annotationId || selection?.id || null; if (hovered !== id) { hovered = id; onHover(id);draw(); } };
  const down = event => {
    if (event.button !== 0 || event.isPrimary === false || gesture || !getPage() || getMode() === 'browse') return;
    event.preventDefault();
    const bounds = canvas.getBoundingClientRect();
    gesture = { pointerId: event.pointerId, mode: getMode(), page: getPage(), bounds, points: [point(event, bounds)], dragged: false };
    canvas.setPointerCapture(event.pointerId); hover(null); draw();
  };
  const move = event => {
    if (!gesture) {
      const selection = hit(event); hover(selection);
      canvas.style.cursor = getMode() === 'browse' ? selection ? 'pointer' : 'default' : 'crosshair';
      return;
    }
    if (event.pointerId !== gesture.pointerId) return;
    const { bounds, mode } = gesture;
    const samples = [...(event.getCoalescedEvents?.() || []), event];
    for (const sample of samples) {
      const next = point(sample, bounds), first = gesture.points[0], previous = gesture.points.at(-1);
      if (Math.hypot((next[0] - first[0]) * bounds.width, (next[1] - first[1]) * bounds.height) > 4) gesture.dragged = true;
      if (mode === 'rectangle') gesture.points = [first, next];
      else if (Math.hypot((next[0] - previous[0]) * bounds.width, (next[1] - previous[1]) * bounds.height) >= .5) {
        gesture.points.push(next);
        if (gesture.points.length > 500) gesture.points = gesture.points.filter((_point, index, all) => index % 2 === 0 || index === all.length - 1);
      }
    }
    draw();
  };
  const up = event => {
    if (!gesture || event.pointerId !== gesture.pointerId) return;
    move(event);
    const { points, page, mode, dragged } = gesture; gesture = null;
    canvas.releasePointerCapture(event.pointerId);
    if (!dragged) { onActivate(hit(event) || null); draw(); return; }
    const rect = selectionBounds(points);
    const area = Math.abs(points.reduce((sum, [x, y], index) => { const [nextX, nextY] = points[(index + 1) % points.length]; return sum + x * nextY - nextX * y; }, 0)) / 2;
    if (mode === 'lasso' && area < .00002) onInvalid('沿内容四周画一圈，松手后点击选区添加注释。');
    else if (rect.width >= .002 && rect.height >= .002 && (mode !== 'lasso' || points.length >= 3))
      onSelect({ id: crypto.randomUUID(), pageId: page.id, pageHash: page.sha256, fileName: page.fileName, sourcePage: page.sourcePage,
        role: page.role, shape: mode, rect, points: mode === 'lasso' ? points : [] });
    draw();
  };
  const cancel = event => {
    if (event && gesture && event.pointerId !== gesture.pointerId) return;
    const pointerId = gesture?.pointerId; gesture = null;
    if (pointerId != null && canvas.hasPointerCapture(pointerId)) canvas.releasePointerCapture(pointerId);
    draw();
  };
  const click = event => { if (getMode() === 'browse') onActivate(hit(event) || null); };
  const leave = () => { if (!gesture) hover(null); };
  const handlers = { pointerdown: down, pointermove: move, pointerup: up, pointercancel: cancel, lostpointercapture: cancel, click, pointerleave: leave };
  for (const [name, handler] of Object.entries(handlers)) canvas.addEventListener(name, handler);
  const observer = new ResizeObserver(()=>{draw();onLayout();}); observer.observe(canvas); draw();
  return { draw, cancel, destroy() { observer.disconnect(); for (const [name, handler] of Object.entries(handlers)) canvas.removeEventListener(name, handler); cancel(); } };
}
