import { fail } from './store.mjs';

export const defaultCloudUrl = 'https://portal-production-3d81c998.up.railway.app';
export function cloudOrigin(value = process.env.GRADEOS_CLOUD_URL || defaultCloudUrl) {
  const url = new URL(value);
  fail((url.protocol === 'https:' || (url.protocol === 'http:' && ['localhost','127.0.0.1','[::1]'].includes(url.hostname)))
    && !url.username && !url.password && url.href === url.origin + '/', 'Cloud 地址需为 HTTPS 或本机服务地址。');
  return url.origin;
}

export async function cloudRequest(account, path, body, {login = false} = {}) {
  let response;
  try {
    response = await fetch(account.origin + '/api/' + path, {method:body === undefined ? 'GET' : 'POST',
      signal:AbortSignal.timeout(18000), redirect:'error', headers:{
        ...(account.session ? {Cookie:'gradeos_session=' + account.session} : {}),
        ...(body === undefined ? {} : {'Content-Type':'application/json'})},
      body:body === undefined ? undefined : JSON.stringify(body)});
  } catch { fail(false, '无法连接 GradeOS Cloud，请检查网络后重试。', 503); }
  const data = await response.json().catch(() => null);
  fail(response.ok && data, typeof data?.error === 'string' ? data.error : 'Cloud 服务暂时不可用。', response.ok ? 502 : response.status);
  if (!login) return data;
  if (login === 'workspace' && data.status === 'pending') return null;
  if (login === 'workspace') fail(data.status === 'approved', 'Cloud 登录回执无效。', 502);
  const session = response.headers.getSetCookie().map(cookie => /^gradeos_session=([A-Za-z0-9_-]+);/.exec(cookie)?.[1]).find(Boolean);
  fail(session, 'Cloud 登录回执无效。', 502);
  return session;
}

export async function readCloudAccount(account) {
  const {user} = await cloudRequest(account, 'me');
  fail(user, '登录已过期，请重新登录 GradeOS Cloud。', 401);
  fail(user.role === 'teacher', '请使用 GradeOS Cloud 教师账号登录。', 403);
  const [classes, credits] = await Promise.all([
    cloudRequest(account, 'classes'),
    cloudRequest(account, 'desktop/credits').catch(error => {
      if ([401,403].includes(error.status)) throw error;
      return {status:'unavailable'};
    }),
  ]);
  fail(Array.isArray(classes), 'Cloud 班级名册暂时不可用。', 502);
  const measured = ['available','empty','unfunded'].includes(credits.status) && credits.currency === 'USD'
    && Number.isFinite(credits.remaining) && credits.remaining >= 0;
  return {...account, user:{id:user.id, name:user.name}, classes:classes.map(({id,name})=>({id,name})),
    credits:measured ? {status:credits.status, remaining:credits.remaining, currency:'USD'} : {status:'unavailable'},
    classConnection:classes.some(row=>row.id===account.classConnection?.classroom.id) ? account.classConnection : null};
}
