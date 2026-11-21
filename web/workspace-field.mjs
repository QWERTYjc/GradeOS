// The pointer and the breathing background share a stationary screen of dots.
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const mix = (a, b, t) => a + (b - a) * t;
const ease = t => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
const tau = Math.PI * 2;
const screenPeriod = 7.4;
const dotPitch = screenPeriod / Math.SQRT2;
const pigment = [98, 118, 139];
const sceneInk = {home:1, intake:.95, files:.95, skills:.93, settings:.90, grading:.89, reader:.88};
const trailLife = 920;
const trailLength = 94;

function halftoneGrid(width, height) {
  const pitch = Math.max(6, Math.ceil(Math.sqrt(width * height / 54000)));
  const cols = Math.ceil(width / pitch) + 1, rows = Math.ceil(height / pitch) + 1;
  const length = cols * rows;
  const warp = new Float32Array(length), phase = new Float32Array(length);
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const i = row * cols + col, x = col * pitch, y = row * pitch;
      warp[i] = 7.6*x/width + 6.1*y/height + 2.4*Math.sin(4.8*y/height - 3.2*x/width);
      phase[i] = 2.1*Math.sin(tau*x/width) - 1.3*Math.cos(tau*y/height);
    }
  }
  return {cols, rows, pitch, warp, phase, exposure:new Float32Array(length),
    clear:new Uint8Array(length), data:new Uint8Array(length * 2)};
}

function protectContent(grid, doc, offsetX, offsetY, width, height) {
  const {cols, rows, pitch} = grid;
  const range = doc.createRange();
  const outside = rect => rect.bottom + offsetY < -24 || rect.top + offsetY > height + 24 ||
    rect.right + offsetX < -24 || rect.left + offsetX > width + 24;
  function protect(rect) {
    if (!rect.width || !rect.height || outside(rect)) return;
    // The whole text line stays on clean paper. Give interpolation a full texel
    // of clearance, then feather the ink in the adjacent white space.
    const x0 = rect.left + offsetX - pitch - 2, x1 = rect.right + offsetX + pitch + 2;
    const y0 = rect.top + offsetY - pitch - 1, y1 = rect.bottom + offsetY + pitch + 1;
    const margin = 13;
    const left = Math.max(0, Math.floor((x0-margin)/pitch)), right = Math.min(cols-1, Math.ceil((x1+margin)/pitch));
    const top = Math.max(0, Math.floor((y0-margin)/pitch)), bottom = Math.min(rows-1, Math.ceil((y1+margin)/pitch));
    for (let row=top; row<=bottom; row++) {
      const dy = Math.max(y0-row*pitch, row*pitch-y1, 0);
      for (let col=left; col<=right; col++) {
        const dx = Math.max(x0-col*pitch, col*pitch-x1, 0), i = row * cols + col;
        const clear = Math.round(255*ease((dx*dx + dy*dy) / (margin*margin)));
        if (clear < grid.clear[i]) grid.clear[i] = clear;
      }
    }
  }
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      if (node.hidden || node.matches('script,style,template,workspace-field,.grading-frame')) return NodeFilter.FILTER_REJECT;
      if (node.matches('input,select,textarea,img,svg,video,canvas,iframe,math,pre,[contenteditable=true]')) {
        protect(node.getBoundingClientRect()); return NodeFilter.FILTER_REJECT;
      }
      if (node.matches('article,.cohort-student,.archive-folder,.workspace-pane') && outside(node.getBoundingClientRect())) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_SKIP;
    },
  });
  while (walker.nextNode()) {
    range.selectNodeContents(walker.currentNode);
    for (const rect of range.getClientRects()) protect(rect);
  }
}

// Each deposit widens and loses concentration with age. Taking the strongest
// contribution keeps a slow turn as transparent as a straight stroke.
function exposeTrail(grid, samples, now, small) {
  const {cols, rows, pitch, exposure} = grid;
  exposure.fill(0);
  const head = samples.at(-1);
  for (const sample of samples) {
    const age = clamp((now - sample.at) / trailLife, 0, 1);
    const sigma = (small ? 18 : 23) + 5 * sample.speed;
    const initial = sigma * sigma;
    sample.variance = initial + (small ? 1450 : 2250) * age;
    const onset = ease((now-sample.started)/165);
    sample.strength = onset * (initial / sample.variance) ** .64 * (1-ease(age));
  }
  for (let i=0; i<samples.length; i++) {
    const b = samples[i], a = i && samples[i-1].stroke === b.stroke ? samples[i-1] : b;
    if (b.stroke !== head.stroke || head.arc-b.arc >= trailLength) continue;
    const peak = Math.max(a.strength, b.strength);
    if (peak < .004) continue;
    const dx = b.x - a.x, dy = b.y - a.y, length2 = dx*dx + dy*dy;
    const radius2 = 2 * Math.max(a.variance,b.variance) * Math.log(peak/.004);
    const radius = Math.sqrt(radius2);
    const left = Math.max(0, Math.ceil((Math.min(a.x,b.x) - radius)/pitch));
    const right = Math.min(cols-1, Math.floor((Math.max(a.x,b.x) + radius)/pitch));
    const top = Math.max(0, Math.ceil((Math.min(a.y,b.y) - radius)/pitch));
    const bottom = Math.min(rows-1, Math.floor((Math.max(a.y,b.y) + radius)/pitch));
    for (let row=top; row<=bottom; row++) {
      for (let col=left; col<=right; col++) {
        const index = row*cols+col;
        if (!grid.clear[index]) continue;
        const x = col*pitch-a.x, y = row*pitch-a.y;
        const u = length2 ? clamp((x*dx + y*dy)/length2,0,1) : 1;
        const ox = x-u*dx, oy = y-u*dy, distance2 = ox*ox+oy*oy;
        if (distance2 >= radius2) continue;
        const variance = mix(a.variance,b.variance,u);
        const tail = ease(1-(head.arc-mix(a.arc,b.arc,u))/trailLength);
        const depth = tail * mix(a.strength,b.strength,u) * Math.exp(-distance2/(2*variance));
        if (depth > exposure[index]) exposure[index] = depth;
      }
    }
  }
}

function composeField(frame, samples, now, time, scroll, ink) {
  const grid = frame.grid, {warp, phase, exposure, clear, data} = grid;
  exposeTrail(grid, samples, now, frame.width < 650);
  const drift = time*.16 + scroll*.00030;
  const cycle = time*tau/6.8;
  for (let i=0; i<clear.length; i++) {
    if (!clear[i]) { data[i*2]=0; data[i*2+1]=0; continue; }
    const wave = .5 + .5*Math.sin(warp[i]+drift);
    const breath = .5 + .5*Math.sin(cycle+phase[i]);
    const ambient = ink * (.24+.76*wave) * (.23+.77*breath);
    const pressure = Math.sqrt(exposure[i]);
    const density = mix(.10+.38*ambient, .99, pressure);
    const opacity = mix(.05+.26*ambient, .53, exposure[i]);
    data[i*2] = Math.round(255*density);
    data[i*2+1] = Math.round(clear[i]*opacity);
  }
}

const vertex = `#version 300 es
out vec2 uv;
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(2. * p - 1., 0., 1.);
  uv = vec2(p.x, 1.-p.y);
}`;
const fragment = `#version 300 es
precision highp float;
precision highp int;
in vec2 uv;
uniform sampler2D field;
uniform vec2 viewport;
uniform float pitch, feather;
out vec4 pixel;
// A permanent rank per site lets the outside of a wake have fewer dots.
// Fade across its rank gradually so a dot never switches on between frames.
float siteRank(ivec2 cell) {
  uint h = uint(cell.x)*1664525u + uint(cell.y)*1013904223u + 2246822519u;
  h = (h ^ (h >> 16u))*2246822519u;
  return float((h ^ (h >> 13u)) & 255u)/255.;
}
void main() {
  vec2 p = uv * viewport;
  vec2 ink = texture(field, (p/pitch + .5)/vec2(textureSize(field,0))).rg;
  vec2 lattice = vec2(p.x+p.y,p.y-p.x)/${screenPeriod};
  vec2 site = floor(lattice+.5);
  float rank = siteRank(ivec2(site));
  float presence = smoothstep(rank-.15,rank+.15,ink.r);
  float distanceToDot = length(lattice-site)*${dotPitch.toFixed(8)};
  float radius = ${dotPitch.toFixed(8)}*(.092+.225*ink.r);
  float alpha = ink.g * presence * (1.-smoothstep(radius-feather,radius+feather,distanceToDot));
  vec3 color = vec3(${pigment.map(v=>v+'.').join(',')})/255.;
  pixel = vec4(color*alpha, alpha);
}`;

function createWebGLRenderer(gl) {
  const program = gl.createProgram(), texture = gl.createTexture();
  function dispose() { gl.deleteTexture(texture); gl.deleteProgram(program); }
  try {
    for (const [kind, source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]) {
      const shader = gl.createShader(kind);
      gl.shaderSource(shader,source); gl.compileShader(shader);
      gl.attachShader(program,shader); gl.deleteShader(shader);
    }
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program,gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);
    gl.bindTexture(gl.TEXTURE_2D,texture);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);
    for (const axis of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T]) gl.texParameteri(gl.TEXTURE_2D,axis,gl.CLAMP_TO_EDGE);
    for (const filter of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER]) gl.texParameteri(gl.TEXTURE_2D,filter,gl.LINEAR);
    const viewport = gl.getUniformLocation(program,'viewport');
    const pitch = gl.getUniformLocation(program,'pitch'), feather = gl.getUniformLocation(program,'feather');
    let currentGrid;
    return {
      draw(frame,enabled) {
        gl.viewport(0,0,gl.canvas.width,gl.canvas.height);
        if (!enabled) { gl.clear(gl.COLOR_BUFFER_BIT); return; }
        const grid = frame.grid;
        if (grid !== currentGrid) {
          gl.texImage2D(gl.TEXTURE_2D,0,gl.RG8,grid.cols,grid.rows,0,gl.RG,gl.UNSIGNED_BYTE,null);
          currentGrid = grid;
        }
        gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,grid.cols,grid.rows,gl.RG,gl.UNSIGNED_BYTE,grid.data);
        gl.uniform2f(viewport,frame.width,frame.height);
        gl.uniform1f(pitch,grid.pitch); gl.uniform1f(feather,.47/frame.dpr);
        gl.drawArrays(gl.TRIANGLES,0,3);
      }, dispose,
    };
  } catch (error) { dispose(); throw error; }
}

// Software rendering samples the same fixed lattice as the shader. Cache the
// site geometry and alpha curves, leaving just the changing field to interpolate.
function createCanvasRenderer(canvas) {
  const brush = canvas.getContext('2d');
  if (!brush) return null;
  let cached, pixels, distances, ranks, coverage, presence, columns, fractions, toneRow, opacityRow;

  function prepare(frame) {
    cached = frame;
    const {width,height,dpr,grid} = frame;
    const w = canvas.width, h = canvas.height;
    pixels = brush.createImageData(w,h);
    distances = new Uint8Array(w*h);
    ranks = new Uint8Array(w*h);
    columns = new Uint32Array(w);
    fractions = new Float32Array(w);
    toneRow = new Float32Array(grid.cols);
    opacityRow = new Float32Array(grid.cols);
    for (let x=0; x<w; x++) {
      const col = (x+.5)*width/(w*grid.pitch);
      columns[x] = Math.floor(col);
      fractions[x] = col-columns[x];
    }
    for (let y=0; y<h; y++) {
      const py = (y+.5)*height/h;
      for (let x=0; x<w; x++) {
        const px = (x+.5)*width/w, i = y*w+x;
        const u = (px+py)/screenPeriod, v = (py-px)/screenPeriod;
        const col = Math.floor(u+.5), row = Math.floor(v+.5);
        let hash = (Math.imul(col,1664525) + Math.imul(row,1013904223) + 2246822519) >>> 0;
        hash = Math.imul(hash ^ (hash >>> 16),2246822519);
        ranks[i] = (hash ^ (hash >>> 13)) & 255;
        distances[i] = Math.round(255*Math.SQRT2*Math.hypot(u-col,v-row));
        pixels.data[i*4] = pigment[0];
        pixels.data[i*4+1] = pigment[1];
        pixels.data[i*4+2] = pigment[2];
      }
    }
    const feather = .47/dpr;
    coverage = new Uint8Array(256*256);
    presence = new Uint8Array(256*256);
    for (let tone=0; tone<256; tone++) {
      const density = tone/255, radius = dotPitch*(.092+.225*density);
      for (let s=0; s<256; s++) {
        const k = tone*256+s, distance = (s/255)*dotPitch/Math.SQRT2;
        coverage[k] = Math.round(255*ease((radius+feather-distance)/(2*feather)));
        presence[k] = Math.round(255*ease((density-s/255+.15)/.30));
      }
    }
  }
  return {
    draw(frame,enabled) {
      if (!enabled) { brush.clearRect(0,0,canvas.width,canvas.height); return; }
      if (cached !== frame) prepare(frame);
      const {cols,pitch,data} = frame.grid, w=canvas.width, h=canvas.height, out=pixels.data;
      for (let y=0; y<h; y++) {
        const v = (y+.5)*frame.height/(h*pitch), row = Math.floor(v), f=v-row;
        for (let col=0; col<cols; col++) {
          const top = 2*(row*cols+col), bottom=top+2*cols;
          toneRow[col] = mix(data[top],data[bottom],f);
          opacityRow[col] = mix(data[top+1],data[bottom+1],f);
        }
        for (let x=0,i=y*w; x<w; x++,i++) {
          const col=columns[x], u=fractions[x];
          const tone = Math.round(mix(toneRow[col],toneRow[col+1],u))*256;
          const opacity = mix(opacityRow[col],opacityRow[col+1],u);
          out[i*4+3] = opacity*coverage[tone+distances[i]]*presence[tone+ranks[i]]/65025;
        }
      }
      brush.putImageData(pixels,0,0);
    },
  };
}

const css = 'canvas{display:block;position:absolute;inset:0;width:100%;height:100%;pointer-events:none}canvas[hidden]{display:none}';
const stylesheet = 'adoptedStyleSheets' in ShadowRoot.prototype ? new CSSStyleSheet() : null;
stylesheet?.replaceSync(css);

class WorkspaceField extends HTMLElement {
  static observedAttributes = ['data-scene'];
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    if (stylesheet) this.shadowRoot.adoptedStyleSheets = [stylesheet];
    this.layoutDirty = true;
    this.target = [0, 0];
    this.pointerUntil = 0;
    this.trail = [];
    this.stroke = 0;
    this.time = 0;
    this.scroll = this.targetScroll = 0;
    this.ink = this.dest = sceneInk.home;
    this.offsets = new WeakMap();
    this.visible = true;
  }
  addCanvas() {
    const canvas = document.createElement('canvas');
    if (!stylesheet) Object.assign(canvas.style, { position: 'absolute', inset: '0', width: '100%', height: '100%' });
    this.shadowRoot.append(canvas);
    return canvas;
  }
  connectedCallback() {
    this.setAttribute('aria-hidden', 'true');
    this.events = new AbortController();
    const options = {signal:this.events.signal};
    this.canvas = this.addCanvas();
    try {
      this.gl = this.canvas.getContext('webgl2', {
        alpha:true, antialias:false, depth:false, stencil:false, premultipliedAlpha:true, powerPreference:'low-power',
      });
    } catch { this.gl = null; }
    const prepare = () => {
      if (!this.gl || this.gl.isContextLost()) return;
      try { this.renderer = createWebGLRenderer(this.gl); } catch { this.renderer = null; }
    };
    prepare();
    this.canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault();
      this.renderer = null;
      this.resize();
    }, options);
    this.canvas.addEventListener('webglcontextrestored', () => { prepare(); this.resize(); }, options);
    this.preference = matchMedia('(prefers-reduced-motion: reduce)');
    this.preference.addEventListener('change', this.motion, options);
    this.settings = new MutationObserver(this.motion);
    this.settings.observe(document.documentElement, {attributes:true, attributeFilter:['data-motion']});
    this.contents = new MutationObserver(() => this.invalidateLayout());
    this.contents.observe(document.body, this.contentOptions);
    document.addEventListener('load', event => {
      if (event.target.matches?.('.grading-frame')) this.invalidateLayout();
    }, {...options, capture:true});
    document.fonts?.addEventListener('loadingdone', () => this.invalidateLayout(), options);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(this);
    this.layoutSize = new ResizeObserver(() => this.invalidateLayout());
    this.intersection = new IntersectionObserver(([entry]) => {
      this.visible = entry.isIntersecting;
      this.refresh();
    });
    this.intersection.observe(this);
    document.addEventListener('visibilitychange', () => {
      this.pointerUntil = 0;
      this.trail.length = 0;
      this.refresh();
    }, options);
    window.addEventListener('blur', () => {
      if (document.activeElement?.tagName !== 'IFRAME') this.clearPointer();
    }, options);
    const track = event => {
      if (event.pointerType !== 'touch') this.trackPointer(event.clientX, event.clientY);
    };
    for (const type of ['pointermove','pointerdown']) document.addEventListener(type, track, {...options, passive:true});
    document.addEventListener('pointerout', event => { if (!event.relatedTarget) this.clearPointer(); }, options);
    document.addEventListener('pointercancel', () => this.clearPointer(), options);
    document.addEventListener('scroll', event => {
      const element = event.target === document ? document.scrollingElement : event.target;
      if (element instanceof Element && !element.closest('textarea, dialog')) this.trackScroll(element.scrollTop, element);
    }, {...options, capture:true, passive:true});
    this.motion();
    this.resize();
  }
  contentOptions = {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['hidden','open']};
  trackPointer(clientX, clientY) {
    if (this.reduced || !this.frame) return;
    const {bounds} = this.frame;
    const x = clientX - bounds.left, y = clientY - bounds.top;
    if (x < 0 || y < 0 || x > bounds.width || y > bounds.height) return this.clearPointer();
    const now = performance.now();
    if (x === this.target[0] && y === this.target[1] && now < this.pointerUntil) return;
    const jump = Math.hypot(x - this.target[0], y - this.target[1]);
    // A genuine re-entry starts a new exposure. A same-origin frame boundary
    // can also send pointerout between two adjacent, continuous coordinates.
    if (!this.trail.length || this.lastInput == null || now-this.lastInput > 260 || jump > 360) {
      this.stroke++;
      this.trail.push({x,y,at:now,arc:0,started:now,speed:0,stroke:this.stroke});
    }
    this.lastInput = now;
    this.target[0] = x; this.target[1] = y;
    this.pointerUntil = now + 150;
    this.wake();
  }
  sampleTrail(now) {
    const last = this.trail.at(-1);
    if (!last || last.stroke !== this.stroke) return;
    // Sample the landing point itself. The delay comes from diffusion after
    // deposition, so fast motion cannot pull the dense centre off the cursor.
    const [x,y] = this.target;
    const distance = Math.hypot(x-last.x,y-last.y);
    if (distance < .8) return;
    const speed = mix(last.speed, Math.min(1,distance / Math.max(1,now-last.at)), .48);
    this.trail.push({x,y,at:now,arc:last.arc+distance,started:last.started,speed,stroke:this.stroke});
  }
  clearPointer() {
    this.pointerUntil = 0;
    this.wake();
  }
  primeScroll(source) {
    if (!source || !Number.isFinite(source.scrollTop)) return;
    this.offsets.set(source, source.scrollTop);
    this.invalidateLayout();
  }
  invalidateLayout() {
    this.layoutDirty = true;
    this.wake();
  }
  updateMask() {
    const {width, height, bounds, grid} = this.frame;
    const owner = this.ownerDocument;
    const frame = owner.querySelector('.grading-frame');
    const main = owner.getElementById('main');
    if (main !== this.layoutMain || frame !== this.layoutFrame) {
      this.layoutSize.disconnect();
      if (main) this.layoutSize.observe(main);
      if (frame) this.layoutSize.observe(frame);
      this.layoutMain = main;
      this.layoutFrame = frame;
    }
    const inner = frame?.contentDocument?.body;
    if (inner !== this.inner) {
      this.frameContents?.disconnect();
      this.inner = inner;
      if (inner) {
        this.frameContents = new MutationObserver(() => this.invalidateLayout());
        this.frameContents.observe(inner, this.contentOptions);
      }
    }
    grid.clear.fill(255);
    protectContent(grid, owner, -bounds.left, -bounds.top, width, height);
    if (inner) {
      const rect = frame.getBoundingClientRect();
      protectContent(grid, inner.ownerDocument, rect.left - bounds.left, rect.top - bounds.top, width, height);
    }
    this.layoutDirty = false;
  }
  trackScroll(offset, source = this) {
    if (!Number.isFinite(offset)) return;
    const previous = this.offsets.get(source) ?? 0;
    this.offsets.set(source, offset);
    if (!this.reduced && offset !== previous) {
      this.targetScroll += offset - previous;
      this.layoutDirty = true;
      this.wake();
    }
  }
  attributeChangedCallback() {
    this.dest = sceneInk[this.dataset.scene] ?? sceneInk.home;
    this.layoutDirty = true;
    this.wake();
  }
  motion = () => {
    this.reduced = this.preference.matches || document.documentElement.dataset.motion === 'reduce';
    this.pointerUntil = 0;
    this.trail.length = 0;
    this.ink = this.dest;
    this.scroll = this.targetScroll;
    this.refresh();
  };
  resize() {
    const width = this.clientWidth, height = this.clientHeight;
    if (!width || !height) {
      this.frame = null;
      this.refresh();
      return;
    }
    const dpr = Math.min(devicePixelRatio || 1, this.renderer ? 2 : 1.25, Math.sqrt((this.renderer ? 4000000 : 1200000) / (width * height)));
    const grid = halftoneGrid(width, height);
    this.frame = {width, height, dpr, grid, bounds:this.getBoundingClientRect()};
    this.layoutDirty = true;
    this.canvas.hidden = !this.renderer;
    if (!this.renderer && !this.still) {
      this.still = this.addCanvas();
      this.software = createCanvasRenderer(this.still);
    }
    if (this.still) this.still.hidden = Boolean(this.renderer);
    const target = this.renderer ? this.canvas : this.still;
    const w = Math.round(width * dpr), h = Math.round(height * dpr);
    if (target.width !== w || target.height !== h) { target.width = w; target.height = h; }
    this.refresh();
  }
  draw(now = performance.now()) {
    if (this.layoutDirty && !this.reduced) this.updateMask();
    if (!this.reduced) composeField(this.frame, this.trail, now, this.time, this.scroll, this.ink);
    (this.renderer || this.software)?.draw(this.frame, !this.reduced);
  }
  wake() {
    if (!this.frame || this.reduced || !this.visible || document.hidden || this.raf) return;
    clearTimeout(this.timer);
    this.raf = requestAnimationFrame(this.tick);
  }
  refresh() {
    clearTimeout(this.timer);
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.last = performance.now();
    if (!this.frame || !this.visible || document.hidden) return;
    this.draw();
    this.wake();
  }
  tick = now => {
    this.raf = 0;
    if (!this.frame || this.reduced || !this.visible || document.hidden) return;
    const dt = clamp((now - this.last) / 1000, 0, .3);
    this.last = now;
    this.time += dt;
    while (this.trail.length && now - this.trail[0].at >= trailLife) this.trail.shift();
    if (now < this.pointerUntil) this.sampleTrail(now);
    this.scroll = mix(this.scroll, this.targetScroll, 1 - Math.exp(-dt * 7));
    this.ink = mix(this.ink, this.dest, 1 - Math.exp(-dt * 6));
    this.draw(now);
    // The paper breathes on a slower clock until interaction wakes it.
    const active = this.trail.length || Math.abs(this.targetScroll - this.scroll) > 1;
    if (active) this.wake();
    else this.timer = setTimeout(() => this.wake(),60);
  };
  disconnectedCallback() {
    this.events.abort();
    this.settings.disconnect();
    this.contents.disconnect(); this.frameContents?.disconnect(); this.inner = null;
    this.observer.disconnect();
    this.layoutSize.disconnect();
    this.layoutMain = this.layoutFrame = null;
    this.intersection.disconnect();
    cancelAnimationFrame(this.raf);
    clearTimeout(this.timer);
    this.renderer?.dispose();
    this.gl?.getExtension('WEBGL_lose_context')?.loseContext();
    this.canvas.remove(); this.still?.remove();
    this.still = this.software = this.renderer = this.gl = this.frame = null;
    this.raf = 0;
    this.trail.length = 0;
    this.lastInput = null; this.visible = true;
  }
}
customElements.define('workspace-field', WorkspaceField);
