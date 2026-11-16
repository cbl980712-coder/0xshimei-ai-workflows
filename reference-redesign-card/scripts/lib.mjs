// 共用：找 Chrome/Edge、用 CDP 控制（只用 Node 22+ 自带的 WebSocket，不用 npm install）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export function findChrome() {
  const c = [process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge'];
  return c.find(p => p && fs.existsSync(p)) || null;
}

export function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const k = argv[i].slice(2);
      const v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
      a[k] = v;
    } else a._.push(argv[i]);
  }
  return a;
}

export const sleep = ms => new Promise(r => setTimeout(r, ms));

// 打开一个无头浏览器，返回 {send, on, close}；profile 目录放在 workDir 里，用完删除
export async function openBrowser({ workDir, width = 1440, height = 900 }) {
  if (typeof WebSocket === 'undefined') throw new Error('需要 Node 22 或更新版本（自带 WebSocket）。当前 ' + process.version);
  const chrome = findChrome();
  if (!chrome) throw new Error('没找到 Chrome 或 Edge。装一个，或设环境变量 CHROME_PATH 指向它。');
  const prof = path.join(workDir, '.chrome-profile-' + process.pid);
  fs.mkdirSync(prof, { recursive: true });
  const proc = spawn(chrome, ['--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + prof,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--force-device-scale-factor=1',
    '--use-angle=swiftshader', '--enable-unsafe-swiftshader', `--window-size=${width},${height}`, 'about:blank'],
    { stdio: 'ignore' });
  const portFile = path.join(prof, 'DevToolsActivePort');
  for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) await sleep(100);
  if (!fs.existsSync(portFile)) { proc.kill(); throw new Error('Chrome 没起来'); }
  const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  const page = targets.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pending = new Map(); const handlers = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(m.error.message)) : p.res(m.result); }
    else handlers.forEach(h => h(m));
  };
  const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
  const close = async () => {
    try { ws.close(); } catch {}
    proc.kill();
    await sleep(300);
    try { fs.rmSync(prof, { recursive: true, force: true }); } catch {}
  };
  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
  return { send, on: h => handlers.push(h), close, chrome };
}

export async function gotoPage(b, url, settle = 1500) {
  let loaded; const p = new Promise(r => loaded = r);
  b.on(m => { if (m.method === 'Page.loadEventFired') loaded(); });
  const nav = await b.send('Page.navigate', { url });
  if (nav.errorText) throw new Error('打不开这个页面（' + nav.errorText.replace('net::', '') + '）。请检查网址是否拼对、网络是否正常、文件路径是否存在。');
  await Promise.race([p, sleep(25000)]);
  await sleep(settle);
}

export async function evalJS(b, expr) {
  const r = await b.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
}

export async function screenshot(b, file, { full = false, maxH = 7000 } = {}) {
  let params = { format: 'png' };
  if (full) {
    const h = Math.min(await evalJS(b, 'Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)'), maxH);
    const w = await evalJS(b, 'document.documentElement.clientWidth');
    params = { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: h, scale: 1 } };
  }
  const r = await b.send('Page.captureScreenshot', params);
  fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
}

export function toURL(s) {
  if (/^https?:|^file:|^data:/.test(s)) return s;
  return 'file://' + path.resolve(s).split(path.sep).map(encodeURIComponent).join('/').replace(/^\/\//, '/');
}

// 读 JSON 文件；文件不存在 / 空 / 写错格式时给人话提示（不抛堆栈）
function fail(m) { console.error('❌ ' + m); process.exit(1); }
export function readJSON(file, what, hint = '') {
  if (!fs.existsSync(file)) fail(`找不到${what}：${file}。请检查路径（路径里有空格要用引号括起来）。`);
  const t = fs.readFileSync(file, 'utf8').trim();
  if (!t) fail(`${what}是空文件：${file}。${hint}`);
  try { return JSON.parse(t); } catch (e) { fail(`${what}不是合法的 JSON：${file}（${e.message}）。常见原因：少逗号、中文引号“”、最后一项多了逗号。${hint}`); }
}
