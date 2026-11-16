// 先跑这个：确认 Node、浏览器、截图都正常。 用法：node scripts/doctor.mjs
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
import { findChrome, openBrowser, gotoPage, evalJS, screenshot } from './lib.mjs';
const ok = (m) => console.log('✅ ' + m), bad = (m) => { console.log('❌ ' + m); process.exitCode = 1; };
const major = +process.versions.node.split('.')[0];
major >= 22 ? ok('Node ' + process.version) : bad('Node 需要 22 或更新，当前 ' + process.version);
const c = findChrome(); c ? ok('浏览器：' + c) : bad('没找到 Chrome/Edge（可设 CHROME_PATH）');
if (!process.exitCode) {
  const work = fs.mkdtempSync(path.join(process.cwd(), '.doctor-'));
  try {
    const b = await openBrowser({ workDir: work });
    await gotoPage(b, 'data:text/html,<h1 id=t style="font-size:40px">hello</h1>', 200);
    const fs_ = await evalJS(b, 'getComputedStyle(document.getElementById("t")).fontSize');
    fs_ === '40px' ? ok('能打开页面并读到样式') : bad('读样式异常：' + fs_);
    const f = path.join(work, 't.png'); await screenshot(b, f);
    fs.statSync(f).size > 500 ? ok('能截图') : bad('截图为空');
    await b.close();
  } catch (e) { bad(e.message); }
  fs.rmSync(work, { recursive: true, force: true });
}
console.log(process.exitCode ? '\n环境没准备好，按上面 ❌ 处理后重跑。' : '\n环境 OK，可以跑 probe 了。');
