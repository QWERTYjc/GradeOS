function returnPage(title, detail) {
  const text = detail.replace(/[&<>]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;'})[character]);
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>${title} · GradeOS Cloud</title><link rel="stylesheet" href="/brand.css"><link rel="stylesheet" href="/account-login.css"></head>
    <body class="auth-return"><main><div class="auth-wordmark"><span class="gradeos-wordmark">Grade<span>OS</span></span> <small>Cloud</small></div>
    <h1>${title}</h1><p>${text}</p><a href="/#settings">返回工作台</a></main></body></html>`;
}

// Only these two top-level browser navigations cross the workbench's origin boundary.
export async function googleNavigation({url, req, res, port, connections, complete}) {
  const start = /^\/auth\/google\/start\/([a-f0-9-]{36})$/.exec(url.pathname);
  if (req.method !== 'GET' || (!start && url.pathname !== '/auth/google/return')) return false;
  res.setHeader('Content-Security-Policy', "default-src 'none'; style-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'");
  const cookie = 'gradeos_google_return_' + port;
  try {
    if (req.headers['sec-fetch-mode'] && req.headers['sec-fetch-mode'] !== 'navigate')
      throw Object.assign(Error('请在浏览器中打开登录入口。'), {status:403});
    if (start) {
      // Canonicalize before setting the browser cookie, including when the editor uses localhost.
      if (req.headers.host !== '127.0.0.1:' + port) {
        res.writeHead(303, {Location:'http://127.0.0.1:' + port + url.pathname});
      } else {
        const {browser, url:cloud} = await connections.openQuickLogin(start[1], port);
        res.writeHead(303, {Location:cloud, 'Set-Cookie':cookie + '=' + browser + '; HttpOnly; SameSite=Lax; Path=/auth/google/return; Max-Age=600'});
      }
      res.end();
      return true;
    }
    const browser = (req.headers.cookie || '').split(';').map(v => v.trim()).find(v => v.startsWith(cookie + '='))?.slice(cookie.length + 1);
    const changed = await connections.pollBrowserLogin(url.searchParams.get('id'), {browser, ticket:url.searchParams.get('ticket')});
    if (!changed) throw Object.assign(Error('登录尚未完成，请从工作台重新打开。'), {status:409});
    await complete();
    res.setHeader('Set-Cookie', cookie + '=; HttpOnly; SameSite=Lax; Path=/auth/google/return; Max-Age=0');
    res.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
    res.end(returnPage('已登录 GradeOS', '现在可以关闭此页，回到工作台继续使用。'));
  } catch (error) {
    res.writeHead(error.status || 500, {'Content-Type':'text/html; charset=utf-8'});
    res.end(returnPage('登录未完成', error.status ? error.message : '暂时无法登录，请回到工作台重试。'));
  }
  return true;
}
