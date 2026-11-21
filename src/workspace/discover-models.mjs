import { fail, WorkspaceError } from './store.mjs';

const unavailable = '无法读取这个服务的模型列表，仍可手动填写模型 ID。';

export async function discoverModels({api, baseUrl, apiKey}) {
  const google = api === 'google-generative-ai', anthropic = api === 'anthropic-messages';
  const root = new URL(baseUrl);
  let path = root.pathname.replace(/\/+$/, '');
  if (anthropic && !path.endsWith('/v1')) path += '/v1';
  if (google && !/\/v\d+[a-z]*$/.test(path)) path += '/v1beta';
  root.pathname = path + '/models';
  const headers = {accept:'application/json'};
  if (google) { headers['x-goog-api-key'] = apiKey; root.searchParams.set('pageSize','1000'); }
  else if (anthropic) { headers['x-api-key'] = apiKey; headers['anthropic-version'] = '2023-06-01'; root.searchParams.set('limit','1000'); }
  else headers.authorization = 'Bearer ' + apiKey;

  const ids = new Set(), cursors = new Set(), signal = AbortSignal.timeout(10000);
  let bytes = 0;
  try {
    for (;;) {
      const response = await fetch(root, {headers, redirect:'error', signal});
      if (!response.ok) {
        await response.body?.cancel();
        fail(false, response.status === 401 || response.status === 403
          ? '服务商未授权读取模型，请检查密钥或手动填写模型 ID。' : unavailable, 502);
      }
      const chunks = [];
      for await (const chunk of response.body) {
        bytes += chunk.length;
        fail(bytes <= 8 * 1024 * 1024, unavailable, 502);
        chunks.push(chunk);
      }
      const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      const rows = google ? data.models : data.data;
      fail(Array.isArray(rows), unavailable, 502);
      for (const row of rows) {
        if (google && Array.isArray(row?.supportedGenerationMethods) && !row.supportedGenerationMethods.includes('generateContent')) continue;
        const rawId = google ? row?.name : row?.id;
        if (typeof rawId !== 'string') continue;
        const id = google ? rawId.replace(/^models\//,'') : rawId;
        if (id.length > 0 && id.length <= 240 && !/[\x00-\x20\x7f]/.test(id) && !id.includes(apiKey)) ids.add(id);
      }
      const cursor = google ? data.nextPageToken : anthropic && data.has_more ? data.last_id : null;
      if (!cursor) break;
      fail(typeof cursor === 'string' && cursor.length <= 4096 && !cursor.includes(apiKey) && !cursors.has(cursor) && cursors.size < 12, unavailable, 502);
      cursors.add(cursor);
      root.searchParams.set(google ? 'pageToken' : 'after_id', cursor);
    }
  } catch (error) {
    if (error instanceof WorkspaceError) throw error;
    fail(false, unavailable, 502);
  }
  return { models:[...ids].sort() };
}
