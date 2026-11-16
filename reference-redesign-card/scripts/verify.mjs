// 验收：把 checklist.json 里每条的 checks 在「改前」「套上 patch.css 后」各量一遍，输出 通过/没过。
// 用法：node scripts/verify.mjs checklist.json --patch patch.css --out 目录 [--md 验收.md]
// check 写法：{"selector":"h1","prop":"fontSize","op":">=","value":48,"note":"可选说明"}
//   prop：任意 computed style 名（fontSize / paddingTop / borderRadius / backgroundColor ...），或 rect.width / rect.height / rect.top / rect.bottom（整页坐标）
//   op：>= <= == != between（between 的 value 写 [最小,最大]）；字符串用 == / !=（颜色自动转 rgb 比较）
import fs from 'node:fs'; import path from 'node:path';
import { parseArgs, readJSON, openBrowser, gotoPage, evalJS, screenshot, sleep } from './lib.mjs';
const a = parseArgs(process.argv.slice(2)); const [cl] = a._; if (!cl) { console.error('缺 checklist.json'); process.exit(1); }
const L = readJSON(cl, 'checklist.json', '模板见 templates/checklist.template.json。');
for (const k of ['own_url', 'goal']) if (!L[k]) { console.error('❌ checklist.json 缺少 "' + k + '"，模板见 templates/checklist.template.json。'); process.exit(1); }
if (!Array.isArray(L.items) || !L.items.length) { console.error('❌ checklist.json 里 "items" 要是一个非空列表，模板见 templates/checklist.template.json。'); process.exit(1); } const out = a.out || '.'; fs.mkdirSync(out, { recursive: true });
const patch = a.patch ? fs.readFileSync(a.patch, 'utf8') : '';
const checks = []; (L.items || []).forEach(it => (it.checks || []).forEach((c, i) => checks.push({ id: it.id, title: it.title, i, ...c })));
checks.forEach(c => { if (typeof c.selector !== 'string' || typeof c.prop !== 'string' || !['>=','<=','==','!=','between'].includes(c.op) || c.value === undefined) { console.error(`❌ ${c.id} 的第 ${c.i + 1} 条 check 写得不完整：每条要有 selector、prop、op（>= <= == != between）、value。`); process.exit(1); } });
const READ = cs => `(() => { const out = []; for (const c of ${JSON.stringify(cs)}) { const el = document.querySelector(c.selector); if (!el) { out.push(null); continue; }
  if (c.prop.startsWith('rect.')) { const r = el.getBoundingClientRect(); const k = c.prop.slice(5); out.push(Math.round((k === 'top' ? r.top + scrollY : k === 'bottom' ? r.bottom + scrollY : r[k]) * 10) / 10); }
  else out.push(getComputedStyle(el)[c.prop]); } return out; })()`;
const num = v => typeof v === 'string' && /^-?[\d.]+(px)?$/.test(v.trim()) ? parseFloat(v) : v;
const judge = (c, v) => { if (v === null) return false; const x = num(v), t = c.value;
  switch (c.op) { case '>=': return +x >= t; case '<=': return +x <= t; case 'between': return +x >= t[0] && +x <= t[1]; case '!=': return String(x) !== String(t); default: return String(x) === String(t) || (typeof t === 'number' && Math.abs(+x - t) < 0.6); } };
async function pass(withPatch) {
  // 改前/改后各开一个全新浏览器：同一个浏览器里第二次打开会命中缓存，广告位等动态内容会不一样，量出来不可比
  const b = await openBrowser({ workDir: out, width: +a.width || 1440 });
  try {
  await gotoPage(b, L.own_url);
  await evalJS(b, `(async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,100));}scrollTo(0,0);})()`); await sleep(600);
  if (withPatch && patch) { await evalJS(b, `(()=>{const s=document.createElement('style');s.textContent=${JSON.stringify(patch)};document.head.appendChild(s);})()`); await sleep(500); }
  const vals = await evalJS(b, READ(checks));
  await screenshot(b, path.join(out, withPatch ? 'mine-after-top.png' : 'mine-before-top.png'));
  await screenshot(b, path.join(out, withPatch ? 'mine-after-full.png' : 'mine-before-full.png'), { full: true });
  return vals;
  } finally { await b.close(); }
}
let before, after;
try { before = await pass(false); after = await pass(true); } catch (e) { console.error('❌ 验收没跑完：' + e.message); process.exit(1); }
const cond = c => c.op === 'between' ? `${c.op} ${c.value.join('~')}` : `${c.op} ${c.value}`;
let md = `# 改后验收清单\n\n- 页面：${L.own_url}\n- 方式：在真实页面里套上 \`${a.patch ? path.basename(a.patch) : '(无 patch)'}\`，用浏览器重新量每条的「怎么看改对了」。**只在浏览器里临时套样式预览，没有改线上网站。**\n\n| 条目 | 检查 | 目标 | 改前 | 改后 | 结果 |\n|---|---|---|---|---|---|\n`;
let ok = 0, res = [];
checks.forEach((c, k) => { const p = judge(c, after[k]), p0 = judge(c, before[k]); if (p) ok++; res.push({ id: c.id, i: c.i, before: before[k], after: after[k], pass: p });
  md += `| ${c.id} ${c.title} | \`${c.selector}\` ${c.prop}${c.note ? '（' + c.note + '）' : ''} | ${cond(c)} | ${before[k] ?? '没找到'}${p0 ? ' ✔' : ''} | ${after[k] ?? '没找到'} | ${p ? '✅ 通过' : '❌ 没过'} |\n`; });
md += `\n**合计：${ok}/${checks.length} 项通过。** 看不出数字的条目（观感类）见改版清单里的「人工看」一栏，要自己对着 ${path.basename(path.join(out, 'mine-after-top.png'))} 看。\n\n![改前](mine-before-top.png)\n\n![改后](mine-after-top.png)\n`;
fs.writeFileSync(path.join(out, a.md || '验收.md'), md);
fs.writeFileSync(path.join(out, 'verify-result.json'), JSON.stringify(res, null, 1));
const bad = res.filter(r => !r.pass);
if (bad.length) { console.log('\n没过的项（改 patch.css 或检查选择器后重跑 finish）：'); bad.forEach(r => { const c = checks.find(k => k.id === r.id && k.i === r.i), t = typeof c.value === 'number' ? c.value : null, x = parseFloat(r.after);
  console.log(`  ❌ ${r.id}「${c.selector} ${c.prop}」目标 ${cond(c)}，改后 ${r.after ?? '没找到这个元素'}` + (r.after === null ? '→ 选择器在页面上选不中，先去 对比.md 里找对的选择器' : (t !== null && Number.isFinite(x) ? `，还差 ${Math.round(Math.abs(t - x) * 10) / 10}` : ''))); }); console.log(''); }
console.log(`验收：${ok}/${checks.length} 通过 → ${path.join(out, a.md || '验收.md')}`);
