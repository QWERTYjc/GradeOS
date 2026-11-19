const esc = (v) =>
  String(v ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const conn = document.querySelector('#connection'),
  host = document.querySelector('#publisher'),
  msg = document.querySelector('#message');
let token,
  local,
  students = [],
  exam,
  taskId = new URLSearchParams(location.search).get('task') || '',
  preview,
  input,
  busy = false;
async function api(path, body) {
  const res = await fetch('/api/cloud/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Workspace-Token': token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw Error(data.error || '请求失败。');
  return data;
}
const option = (value, label, selected) =>
  `<option value="${esc(value)}" ${selected ? 'selected' : ''}>${esc(label)}</option>`;
function pairForm() {
  return '<form id="pair" class="pair"><label>工作台配对信息<input name="pairing" type="password" autocomplete="off" required></label><p class="muted">在云端教师门户打开班级，选择「连接本地工作台」。</p><button type="submit">连接班级</button></form>';
}
function savedGroup(id) {
  return exam.papers?.find((p) => p.paperId === id);
}
function task() {
  return local.tasks.find((t) => t.id === taskId);
}
function bindingsForm() {
  const t = task();
  if (!t) return '';
  const rows = t.groups
    .map((g) => {
      const old = savedGroup(g.id);
      return `<div class="row" data-group="${esc(g.id)}"><strong>${esc(g.label)}</strong><label>收件学生<select name="student" aria-label="${esc(g.label)}的收件学生" ${exam.active ? 'disabled' : ''}>${option('', '不发布这份答卷', !old)}${students.map((s) => option(s.id, s.number + ' · ' + s.name, old?.studentId === s.id)).join('')}</select></label><label>给学生的评语<input name="note" maxlength="4000" value="${esc(old?.note || '')}" placeholder="选填"></label></div>`;
    })
    .join('');
  return `<form id="mapping"><div class="fields"><label>考试名称<input name="title" value="${esc(exam.title || t.title)}" required maxlength="120"></label><label>考试日期<input type="date" name="date" value="${esc(exam.papers?.[0]?.date || t.date || new Date().toLocaleDateString('en-CA'))}" required></label></div><h2>答卷与收件人</h2>${rows}<button class="primary" type="submit">预览学生可见内容</button></form><div id="preview"></div>`;
}
async function refresh() {
  preview = input = null;
  local = await api('status');
  taskId = local.tasks.some((t) => t.id === taskId) ? taskId : local.tasks[0]?.id || '';
  conn.innerHTML = local.classroom
    ? `<p>已连接 <strong>${esc(local.classroom.name)}</strong> · <a href="${esc(local.origin)}" target="_blank" rel="noreferrer">打开云端</a></p><details><summary>更换班级连接</summary>${pairForm()}</details>`
    : pairForm();
  if (!local.classroom) {
    host.innerHTML = '';
    return;
  }
  if (!taskId) {
    host.innerHTML = '<p class="muted">完成一个批改批次后，即可在这里分发结果。</p>';
    return;
  }
  const selector = `<label class="exam">本地批改批次<select id="tasks">${local.tasks.map((t) => option(t.id, t.title, t.id === taskId)).join('')}</select></label>`;
  host.innerHTML = selector;
  if (task().queued) {
    host.insertAdjacentHTML(
      'beforeend',
      '<h2>有一份发布等待云端回执</h2><p>重传将使用之前确认的内容。</p><div class="actions"><button class="primary" data-act="retry">重试已确认的发布</button><button data-act="discard">取消本地重传</button></div>',
    );
    return;
  }
  const [roster, remote] = await Promise.all([api('roster'), api('exam/' + taskId)]);
  students = roster.students;
  exam = remote;
  host.insertAdjacentHTML(
    'beforeend',
    '<p class="muted">' +
      (exam.version
        ? '云端第 ' + exam.version + ' 版 · ' + (exam.active ? '已发布' : '已撤回')
        : '首次发布') +
      '</p>' +
      bindingsForm(),
  );
}
function readForm(form) {
  return {
    title: form.elements.title.value,
    date: form.elements.date.value,
    baseVersion: exam.version,
    bindings: [...form.querySelectorAll('[data-group]')]
      .filter((el) => el.querySelector('select').value)
      .map((el) => ({
        paperId: el.dataset.group,
        studentId: el.querySelector('select').value,
        note: el.querySelector('input').value,
      })),
  };
}
function renderPreview() {
  const p = preview.payload;
  const papers = p.papers
    .map((paper) => {
      const recipient = students.find((s) => s.id === paper.studentId),
        label = task().groups.find((g) => g.id === paper.paperId)?.label;
      return `<section><h3 class="recipient">${esc(label)} → ${esc(recipient?.number)} · ${esc(recipient?.name)}</h3><ul>${paper.points.map((r) => `<li><span>${esc(r.question)} · ${esc(r.point)}</span><strong>${r.state === 'feedback' ? '定性反馈' : r.state === 'pending' ? '待定' : esc(r.score)}${r.max == null ? '' : ' / ' + esc(r.max)}</strong></li>`).join('')}</ul>${paper.note ? '<p class="note">' + esc(paper.note) + '</p>' : ''}</section>`;
    })
    .join('');
  const el = document.querySelector('#preview');
  el.innerHTML = `<h2>发布预览</h2><p>${esc(p.title)} · ${esc(p.date)} · ${p.papers.length} 名收件人</p>${papers}<div class="actions"><button class="primary" data-act="publish">${exam.active ? '确认同步更正' : '确认发布'}</button></div>`;
  el.scrollIntoView({ block: 'nearest' });
}
async function work(action) {
  if (busy) return;
  busy = true;
  document.body.setAttribute('aria-busy', 'true');
  try {
    await action();
  } catch (e) {
    msg.textContent = e.message;
    msg.scrollIntoView({ block: 'nearest' });
  } finally {
    busy = false;
    document.body.removeAttribute('aria-busy');
  }
}
document.addEventListener('submit', (event) => {
  event.preventDefault();
  const form = event.target;
  work(async () => {
    if (form.id === 'pair') {
      await api('pair', { pairing: form.elements.pairing.value.trim() });
      msg.textContent = '已连接班级。';
      await refresh();
    }
    if (form.id === 'mapping') {
      input = readForm(form);
      preview = await api('preview/' + taskId, input);
      renderPreview();
    }
  });
});
document.addEventListener('input', (event) => {
  if (event.target.closest('#mapping')) {
    preview = null;
    document.querySelector('#preview').replaceChildren();
  }
});
document.addEventListener('change', (event) => {
  if (event.target.id === 'tasks') {
    taskId = event.target.value;
    msg.textContent = '';
    work(refresh);
  }
});
document.addEventListener('click', (event) => {
  const action = event.target.closest('[data-act]')?.dataset.act;
  if (!action) return;
  work(async () => {
    if (action === 'discard') {
      if (!confirm('取消待重传的发布？云端已接收的版本会保留。')) return;
      await api('discard/' + taskId, {});
      msg.textContent = '已取消本地重传。';
    } else {
      try {
        const receipt = await api(
          action + '/' + taskId,
          action === 'retry' ? {} : { ...input, signature: preview.signature },
        );
        msg.textContent = '发布成功 · 云端第 ' + receipt.version + ' 版';
      } catch (error) {
        await refresh();
        throw error;
      }
    }
    await refresh();
    msg.scrollIntoView({ block: 'nearest' });
  });
});
await work(async () => {
  token = (await (await fetch('/api/state')).json()).token;
  await refresh();
});
