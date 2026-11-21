import { chmod, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { gradingModels, recommendedChatIds } from '../../web/grading-models.mjs';
import { cloudOrigin, cloudRequest, readCloudAccount } from './cloud-account.mjs';
import { DEFAULT_MAIN_MODEL_ID } from '../experiment-models.mjs';
import { localModelCatalog } from '../pi-model-route.mjs';
import { fail } from './store.mjs';
import { discoverModels } from './discover-models.mjs';

export const protocols = ['openai-completions', 'openai-responses', 'anthropic-messages', 'google-generative-ai'];

function endpoint(value) {
  let url;
  try { url = new URL(value); } catch { fail(false, '请输入完整的 API 基础网址。'); }
  const local = ['127.0.0.1', '[::1]', 'localhost'].includes(url.hostname);
  fail((url.protocol === 'https:' || (local && url.protocol === 'http:')) && !url.username && !url.password && !url.search && !url.hash,
    'API 网址需使用 HTTPS 或本机 HTTP，且不能包含凭据、查询参数或片段。');
  return url.href.replace(/\/+$/, '');
}

export class ModelConnections {
  constructor(directory, { model = DEFAULT_MAIN_MODEL_ID, configured, cloudUrl } = {}) {
    this.path = join(directory, '.model-connections.json');
    this.model = model; this.configured = configured ?? (() => Boolean(process.env.OPENROUTER_API_KEY));
    this.cloudUrl = cloudOrigin(cloudUrl);
    this.googleLaunch = randomUUID();
    this.data = { defaultId:null, connections:[] };
    this.queue = Promise.resolve();
  }
  async init() {
    try { this.data = JSON.parse(await readFile(this.path, 'utf8')); await chmod(this.path, 0o600); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    return this;
  }
  profiles() {
    return this.data.connections.map(({id, name, api, baseUrl, modelId, inputRate, outputRate}) =>
      ({id, name, api, baseUrl, modelId, inputRate, outputRate}));
  }
  get cloud() { return this.data.cloud?.origin === this.cloudUrl ? this.data.cloud : null; }
  accountView() {
    const account = this.cloud;
    return {origin:this.cloudUrl, googleLaunch:this.googleLaunch, mode:this.data.mode || 'local', user:account?.user || null,
      credits:account?.credits || null, hasLocalKey:Boolean(this.data.routerKey || this.configured()), hasSavedKey:Boolean(this.data.routerKey)};
  }
  catalog() {
    const cloudMode = this.data.mode === 'cloud';
    const ready = cloudMode ? this.cloud?.credits.status === 'available' : Boolean(this.data.routerKey || this.configured());
    const builtins = gradingModels.filter(m=>!cloudMode || recommendedChatIds.includes(m.id))
      .map(model => ({...model,provider:cloudMode?'GradeOS Cloud':'OpenRouter', ready}));
    if (!cloudMode && !builtins.some(v=>v.id===this.model)) builtins.push({id:this.model,name:this.model,provider:'OpenRouter',efforts:['low'],ready});
    const profiles = cloudMode ? [] : this.profiles();
    const options = [...profiles.map(p => ({
      id:p.id, name:p.modelId, provider:p.name, efforts:['off'], ready:true
    })), ...builtins];
    const pinned = this.data.pinned || recommendedChatIds;
    const chatIds = [...recommendedChatIds.filter(id=>pinned.includes(id)), ...profiles.map(p=>p.id)];
    const preferred = (cloudMode ? this.data.cloudDefault : this.data.defaultId) || this.model;
    return {defaultId:chatIds.includes(preferred) ? preferred : chatIds[0], options, chatIds};
  }
  resolve(selection) {
    const catalog = this.catalog();
    const id = selection || catalog.defaultId;
    fail(catalog.options.some(row => row.id === id), '该模型不在当前连接中，请重新选择。', 422);
    if (this.data.mode === 'cloud' || (this.data.routerKey && !id.startsWith('connection:'))) {
      const cloud = this.data.mode === 'cloud';
      const apiKey = cloud ? this.cloud?.session : this.data.routerKey;
      const reason = !cloud ? undefined : !this.cloud ? '请登录 GradeOS Cloud 教师账号。'
        : this.cloud.credits.status === 'unavailable' ? '请在账号设置中刷新 Cloud 额度。'
        : this.cloud.credits.status !== 'available' ? '此账号暂无可用 Cloud 额度，可联系管理员开通或选择自带 API。' : undefined;
      return {modelId:id, ready:catalog.options.find(row=>row.id===id).ready,
        reason,
        connection:apiKey ? {kind:'openrouter', api:'openai-completions', modelId:id, apiKey,
          baseUrl:cloud ? this.cloudUrl+'/api/desktop/v1' : 'https://openrouter.ai/api/v1'} : null};
    }
    const match = this.data.connections.find(row => row.id === id);
    if (match) return {modelId:match.modelId, connection:{...match}, ready:true};
    return {modelId:id, connection:null, ready:this.configured()};
  }
  mutate(change) {
    const save = this.queue.then(async () => {
      const next = structuredClone(this.data);
      await change(next);
      if (JSON.stringify(next) === JSON.stringify(this.data)) return false;
      const tmp = this.path + '.' + randomUUID();
      try {
        await writeFile(tmp, JSON.stringify(next), {flag:'wx',mode:0o600});
        await rename(tmp, this.path);
      } finally { await rm(tmp, {force:true}); }
      this.data = next;
      return true;
    });
    this.queue = save.catch(()=>{});
    return save;
  }
  async signIn({login, password}) {
    fail(typeof login === 'string' && login.trim() && typeof password === 'string' && password, '请填写教师登录名和密码。');
    this.browserLogin = null;
    return this.mutate(async data => {
      const session = await cloudRequest({origin:this.cloudUrl}, 'session', {login:login.trim(),password}, {login:true});
      await this.acceptCloudSession(data, session);
    });
  }
  async acceptCloudSession(data, session) {
    const account = { origin:this.cloudUrl, session };
    try { data.cloud = await readCloudAccount(account); }
    catch (error) { await cloudRequest(account, 'logout', {}).catch(()=>{}); throw error; }
    if (this.cloud) await cloudRequest(this.cloud, 'logout', {}).catch(()=>{});
    data.mode = 'cloud';
    this.googleLaunch = randomUUID();
  }
  async openQuickLogin(launch, port) {
    fail(launch === this.googleLaunch, '这个登录入口已失效，请从工作台重新打开。', 410);
    const attempt = {browser:randomUUID()};
    this.browserLogin = attempt;
    const remote = await cloudRequest({origin:this.cloudUrl}, 'desktop/login/start', {returnPort:port});
    fail(this.browserLogin === attempt, '这次登录已取消。', 410);
    fail(remote.returnPort === port && typeof remote.verifier === 'string' && /^[\da-f-]{36}$/i.test(remote.id) &&
      Date.parse(remote.expires) > Date.now(), '此 Cloud 服务暂不支持快捷登录，请使用账号密码。', 502);
    Object.assign(attempt, {id:remote.id, verifier:remote.verifier, expires:Date.parse(remote.expires)});
    return {browser:attempt.browser, url:this.cloudUrl + '/google.html#workbench=' + remote.id + '&quick=1'};
  }
  async startBrowserLogin() {
    const attempt = await cloudRequest({origin:this.cloudUrl}, 'desktop/login/start', {});
    const expires = Date.parse(attempt.expires);
    fail(typeof attempt.id === 'string' && /^[\da-f-]{36}$/i.test(attempt.id) &&
      /^\d{6}$/.test(attempt.code) && typeof attempt.verifier === 'string' && expires > Date.now(),
      'Cloud 登录回执无效。', 502);
    this.browserLogin = {id:attempt.id, verifier:attempt.verifier, expires};
    return {id:attempt.id, code:attempt.code, expires,
      url:this.cloudUrl + '/google.html#workbench=' + attempt.id};
  }
  pollBrowserLogin(id, handoff) {
    return this.mutate(async data => {
      const attempt = this.browserLogin;
      fail(attempt && attempt.id === id && attempt.expires > Date.now(), '登录已失效，请重新开始。', 410);
      if (attempt.browser || handoff) {
        fail(attempt.browser && handoff?.browser === attempt.browser && typeof handoff.ticket === 'string' &&
          /^[\w-]{40}$/.test(handoff.ticket), '请在发起登录的浏览器中返回工作台。', 403);
      }
      const session = await cloudRequest({origin:this.cloudUrl}, 'desktop/login/claim',
        {id, verifier:attempt.verifier, ...(handoff ? {ticket:handoff.ticket} : {})}, {login:'workspace'});
      if (!session) return;
      if (attempt !== this.browserLogin) {
        await cloudRequest({origin:this.cloudUrl, session}, 'logout', {}).catch(()=>{});
        fail(false, '登录已取消。', 410);
      }
      this.browserLogin = null;
      await this.acceptCloudSession(data, session);
    });
  }
  cancelBrowserLogin(id) {
    if (this.browserLogin?.id === id) this.browserLogin = null;
  }
  refreshCloud() {
    return this.mutate(async data => {
      if (!this.cloud) return;
      try { data.cloud = await readCloudAccount(this.cloud); }
      catch (error) {
        if (![401,403].includes(error.status)) throw error;
        delete data.cloud;
      }
    });
  }
  signOut() {
    this.browserLogin = null;
    this.googleLaunch = randomUUID();
    return this.mutate(async data => {
      if (this.cloud) await cloudRequest(this.cloud, 'logout', {}).catch(()=>{});
      delete data.cloud;
    });
  }
  selectClass(classId) {
    return this.mutate(async data => {
      const account = this.cloud;
      fail(account, '请先登录 GradeOS Cloud。', 401);
      fail(account.classes.some(c=>c.id===classId), '请选择自己管理的班级。');
      const {code} = await cloudRequest(account, 'classes/'+encodeURIComponent(classId)+'/pair', {});
      const paired = await cloudRequest({origin:account.origin}, 'pair', {code});
      fail(paired.classroom?.id === classId && typeof paired.token === 'string' && paired.token, '班级连接回执无效。', 502);
      data.cloud.classConnection = {url:account.origin, token:paired.token, classroom:paired.classroom};
    });
  }
  setMode(mode) {
    return this.mutate(data => {
      fail(['local','cloud'].includes(mode), '请选择模型费用来源。');
      fail(mode !== 'cloud' || this.cloud, '请先登录 GradeOS Cloud。', 401);
      data.mode = mode;
    });
  }
  setRouterKey(apiKey) {
    return this.mutate(data => {
      fail(typeof apiKey === 'string' && apiKey.length <= 8192 && !/\s/.test(apiKey), 'API Key 格式无效。');
      data.routerKey = apiKey;
    });
  }
  setPinned(ids) {
    return this.mutate(data => {
      fail(Array.isArray(ids) && ids.length >= 1 && ids.length <= recommendedChatIds.length &&
        ids.every(id=>recommendedChatIds.includes(id)) && new Set(ids).size === ids.length, '请至少选择一个推荐模型。');
      data.pinned = ids;
    });
  }
  credentials(body, data = this.data) {
    const previous = body.id && data.connections.find(row => row.id === body.id);
    fail(!body.id || previous, '连接已移除。', 404);
    const {api} = body;
    fail(protocols.includes(api), '请选择支持的 API 协议。');
    const baseUrl = endpoint(body.baseUrl);
    fail(body.apiKey == null || typeof body.apiKey === 'string' && body.apiKey.length <= 8192 && !/[\r\n]/.test(body.apiKey), 'API Key 格式无效。');
    const retained = previous && previous.api === api && previous.baseUrl === baseUrl ? previous.apiKey : '';
    const apiKey = body.apiKey?.trim() || retained;
    fail(apiKey, '请填写此 API 网址的密钥。更换网址或协议时需重新输入。');
    return {previous, api, baseUrl, apiKey};
  }
  discover(body) {
    return discoverModels(this.credentials(body));
  }
  save(body) {
    return this.mutate(data => {
      const { previous, api, baseUrl, apiKey } = this.credentials(body, data);
      const modelId = typeof body.modelId === 'string' && body.modelId.trim();
      const name = typeof body.name === 'string' && body.name.trim() || new URL(baseUrl).hostname;
      fail(modelId && modelId.length <= 240 && !/\s/.test(modelId) && name.length <= 100, '请填写有效的模型 ID 和连接名称。');
      const rate = (value, fallback) => {
        const n = value === undefined || value === '' ? fallback : Number(value);
        fail(Number.isFinite(n) && n >= 0 && n <= 10000, '请输入有效的每百万 token 预算费率。'); return n;
      };
      const sameModel = previous && previous.baseUrl === baseUrl && previous.api === api && previous.modelId === modelId;
      const known = localModelCatalog(baseUrl).find(row=>row.id===modelId);
      const entry = {id:sameModel ? previous.id : 'connection:' + randomUUID(), name, api, baseUrl, modelId, apiKey,
        inputRate:rate(body.inputRate, (sameModel ? previous.inputRate : null) ?? known?.cost.input ?? 5), outputRate:rate(body.outputRate,(sameModel ? previous.outputRate : null) ?? known?.cost.output ?? 25)};
      if (previous) data.connections[data.connections.indexOf(previous)] = entry;
      else data.connections.push(entry);
      if (previous && data.defaultId === previous.id || body.makeDefault === true || (!previous && !data.defaultId && !this.configured())) data.defaultId = entry.id;
    });
  }
  remove(id) {
    return this.mutate(data => {
      fail(data.connections.some(row=>row.id===id), '连接不存在。', 404);
      data.connections = data.connections.filter(row=>row.id!==id);
      if (data.defaultId === id) data.defaultId = null;
    });
  }
  setDefault(id) {
    return this.mutate(data => {
      fail(this.catalog().chatIds.includes(id) || (data.mode !== 'cloud' && id === this.model), '连接不存在。', 404);
      data[data.mode === 'cloud' ? 'cloudDefault' : 'defaultId'] = id === this.model ? null : id;
    });
  }
}
