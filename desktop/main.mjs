import { app, BrowserWindow, dialog, shell } from 'electron';
import { fork } from 'node:child_process';
import { join } from 'node:path';

app.setName('GradeOS');
const webPreferences = { sandbox: true, contextIsolation: true, nodeIntegration: false };
let service, origin, mainWindow, quitting = false;

function showWorkspace() {
  if (!origin || quitting) return;
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = new BrowserWindow({ title: 'GradeOS', width: 1280, height: 850,
      minWidth: 760, minHeight: 560, backgroundColor: '#ffffff', webPreferences });
    mainWindow.loadURL(origin).catch(error => {
      if (!quitting) dialog.showErrorBox('无法打开 GradeOS', error.message);
    });
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function workspaceLink(url) {
  return Boolean(origin) && URL.canParse(url) && new URL(url).origin === origin;
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', showWorkspace);
  app.on('activate', showWorkspace);
  app.on('web-contents-created', (_event, contents) => {
    contents.on('will-navigate', (event, url) => {
      if (!workspaceLink(url)) event.preventDefault();
    });
    contents.setWindowOpenHandler(({ url }) => {
      if (workspaceLink(url) && /^\/auth\/google\/start\/[a-f0-9-]{36}$/.test(new URL(url).pathname)) {
        shell.openExternal(url).catch(error => dialog.showErrorBox('无法打开系统浏览器', error.message));
        return { action:'deny' };
      }
      if (workspaceLink(url)) return { action: 'allow', overrideBrowserWindowOptions: { webPreferences } };
      if (URL.canParse(url) && new URL(url).protocol === 'https:') {
        dialog.showMessageBox({ type: 'question', message: '在浏览器中打开此网站？',
          detail: new URL(url).origin, buttons: ['取消', '打开'], cancelId: 0, defaultId: 0 })
          .then(({ response }) => response === 1 && shell.openExternal(url)).catch(console.error);
      }
      return { action: 'deny' };
    });
  });
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
  // Wait for the editor windows to finish closing before shutting down their service.
  app.on('will-quit', event => {
    if (!service) return;
    event.preventDefault();
    if (quitting) return;
    quitting = true;
    if (service.connected) service.disconnect();
    const deadline = setTimeout(() => service?.kill('SIGKILL'), 15000);
    deadline.unref();
  });

  app.whenReady().then(() => {
    const workspace = join(app.getPath('userData'), 'workspace');
    service = fork(join(app.getAppPath(), 'desktop', 'service.mjs'), [workspace], {
      execPath: process.execPath, execArgv: [], windowsHide: true,
      env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' },
      stdio: ['ignore', 'inherit', 'inherit', 'ipc'],
    });
    let failure;
    service.on('message', message => {
      if (message.signedIn) showWorkspace();
      if (message.error) failure = message.error;
      if (Number.isInteger(message.port) && !quitting) {
        origin = `http://127.0.0.1:${message.port}`;
        showWorkspace();
      }
    });
    function serviceStopped() {
      if (!service) return;
      service = null;
      if (quitting) return app.exit(0);
      dialog.showErrorBox('GradeOS 工作台已停止', failure || '请重新打开应用。工作区保存在本机。');
      app.exit(1);
    }
    service.once('exit', serviceStopped);
    service.on('error', error => {
      failure = error.message;
      if (!service?.pid) serviceStopped();
    });
  }).catch(error => { dialog.showErrorBox('GradeOS 启动失败', error.message); app.quit(); });
}
