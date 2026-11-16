// checklist.json → 改版清单.md + 指令卡.html（单文件，图片用相对路径）
// 用法：node scripts/render.mjs checklist.json --out 目录 [--md 改版清单.md] [--html 指令卡.html] [--imgbase 图片所在相对目录]
import fs from 'node:fs'; import path from 'node:path'; import { parseArgs, readJSON } from './lib.mjs';
const a = parseArgs(process.argv.slice(2)); const [cl] = a._; if (!cl) { console.error('缺 checklist.json'); process.exit(1); }
const L = readJSON(cl, 'checklist.json', '模板见 templates/checklist.template.json。');
for (const k of ['own_url', 'goal']) if (!L[k]) { console.error('❌ checklist.json 缺少 "' + k + '"，模板见 templates/checklist.template.json。'); process.exit(1); }
if (!Array.isArray(L.items) || !L.items.length) { console.error('❌ checklist.json 里 "items" 要是一个非空列表，模板见 templates/checklist.template.json。'); process.exit(1); } const out = a.out || '.';
const vr = fs.existsSync(path.join(out, 'verify-result.json')) ? JSON.parse(fs.readFileSync(path.join(out, 'verify-result.json'), 'utf8')) : [];
const base = a.imgbase ? String(a.imgbase).replace(/\/?$/, '/') : '';
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const status = id => { const r = vr.filter(x => x.id === id); return r.length ? (r.every(x => x.pass) ? 'pass' : 'fail') : ''; };
const items = [...L.items].sort((x, y) => x.priority.localeCompare(y.priority));
const PN = { P0: '先改（影响最大）', P1: '再改', P2: '有空再改' };
// ---- Markdown
let md = `# ${L.title}\n\n- 我的页面：${L.own_url}\n- 参考页面：${L.ref_url}\n- 页面目标：${L.goal}\n- 生成日期：${L.date}\n\n`;
md += `## 一、想借鉴的 → 对应到我页面的哪里\n\n| 编号 | 类型 | 参考图里的位置 | 好在哪 | 对应我页面的区域 |\n|---|---|---|---|---|\n`;
L.borrow.forEach(b => md += `| ${b.id} | ${b.aspect} | ${b.ref_where} | ${b.why_good} | ${b.mine_where}（\`${b.mine_selector}\`） |\n`);
md += `\n## 二、这些地方不动\n\n` + L.keep.map(k => `- **${k.where}**：${k.why}`).join('\n') + '\n';
if (L.not_borrow?.length) md += `\n不借鉴（参考页有，但不适合我的目标）：\n\n` + L.not_borrow.map(x => `- ${x}`).join('\n') + '\n';
md += `\n## 三、改版清单（按优先级）\n`;
items.forEach(it => { md += `\n### ${it.id}　${it.title}　〔${it.priority}·${PN[it.priority] || ''}〕\n\n- **改哪里**：${it.where}\n- **怎么改**：${it.change}\n` + (it.css ? `- **参考样式**：\n\n\`\`\`css\n${it.css}\n\`\`\`\n\n` : '') + `- **怎么看改对了**：${it.how_to_check}\n- 来自借鉴点：${it.borrow}\n`; });
fs.writeFileSync(path.join(out, a.md || '改版清单.md'), md);
// ---- HTML
const img = (src, cap) => src ? `<figure><img src="${esc(base + src)}" alt="${esc(cap)}"><figcaption>${esc(cap)}</figcaption></figure>` : '';
const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(L.title)}</title>
<style>:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mut:#5d6572;--line:#e3e6eb;--acc:#e11d48;--ok:#15803d;--bad:#b91c1c}
@media(prefers-color-scheme:dark){:root{--bg:#101216;--card:#181b21;--ink:#eceef2;--mut:#9aa3b2;--line:#2a2f38;--acc:#fb7185;--ok:#4ade80;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:1000px;margin:0 auto;padding:32px 16px 80px}h1{font-size:28px;margin:0 0 8px}h2{font-size:20px;margin:40px 0 12px}
.meta{color:var(--mut);font-size:14px}.meta a{color:inherit}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
table{width:100%;border-collapse:collapse;font-size:14px;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--mut);font-weight:600}
code,pre{font:13px/1.5 ui-monospace,Menlo,Consolas,monospace}pre{background:var(--bg);padding:10px 12px;border-radius:8px;overflow:auto;margin:8px 0}
.pri{display:inline-block;font-size:12px;font-weight:700;color:#fff;background:var(--acc);border-radius:999px;padding:1px 10px;margin-right:8px}.P1{background:#d97706}.P2{background:#64748b}
.it h3{margin:0 0 8px;font-size:17px}.it dl{margin:0;display:grid;grid-template-columns:96px 1fr;gap:6px 12px}.it dt{color:var(--mut);font-size:14px}.it dd{margin:0}
.badge{font-size:12px;font-weight:700;margin-left:8px}.pass{color:var(--ok)}.fail{color:var(--bad)}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0}figure img{width:100%;border:1px solid var(--line);border-radius:8px;display:block}figcaption{font-size:13px;color:var(--mut);margin-top:4px}
@media(max-width:700px){.imgs{grid-template-columns:1fr}.it dl{grid-template-columns:1fr}table{display:block;overflow-x:auto}}</style></head><body><main>
<h1>${esc(L.title)}</h1><div class="meta">我的页面 <a href="${esc(L.own_url)}">${esc(L.own_url)}</a> · 参考 <a href="${esc(L.ref_url)}">${esc(L.ref_url)}</a> · ${esc(L.date)}</div>
<div class="card"><b>页面目标：</b>${esc(L.goal)}</div>
<div class="imgs">${img(L.images?.ref, '参考页（红圈 = 想借鉴的位置）')}${img(L.images?.mine, '我的页（红圈 = 对应的区域）')}</div>
<h2>一、想借鉴的 → 对应我页面的哪里</h2><table><tr><th>编号</th><th>类型</th><th>参考图里的位置</th><th>好在哪</th><th>对应我页面的区域</th></tr>
${L.borrow.map(b => `<tr><td>${esc(b.id)}</td><td>${esc(b.aspect)}</td><td>${esc(b.ref_where)}</td><td>${esc(b.why_good)}</td><td>${esc(b.mine_where)}<br><code>${esc(b.mine_selector)}</code></td></tr>`).join('')}</table>
<h2>二、这些地方不动</h2><div class="card"><ul>${L.keep.map(k => `<li><b>${esc(k.where)}</b>：${esc(k.why)}</li>`).join('')}</ul>${L.not_borrow?.length ? `<p class="meta">不借鉴：</p><ul>${L.not_borrow.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}</div>
<h2>三、改版清单（按优先级）</h2>
${items.map(it => { const s = status(it.id); return `<div class="card it"><h3><span class="pri ${it.priority}">${it.priority}</span>${esc(it.id)} ${esc(it.title)}${s ? `<span class="badge ${s}">${s === 'pass' ? '✅ 实测已达标' : '❌ 实测未达标'}</span>` : ''}</h3><dl>
<dt>改哪里</dt><dd>${esc(it.where)}</dd><dt>怎么改</dt><dd>${esc(it.change)}${it.css ? `<pre>${esc(it.css)}</pre>` : ''}</dd><dt>怎么看改对了</dt><dd>${esc(it.how_to_check)}</dd><dt>借鉴点</dt><dd>${esc(it.borrow)}</dd></dl></div>`; }).join('')}
${L.images?.after ? `<h2>四、套上改动后的样子（浏览器临时预览）</h2><div class="imgs">${img(L.images.mine_top, '改前')}${img(L.images.after, '改后')}</div>` : ''}
</main></body></html>`;
fs.writeFileSync(path.join(out, a.html || '指令卡.html'), html);
console.log('生成：' + path.join(out, a.md || '改版清单.md') + ' 和 ' + path.join(out, a.html || '指令卡.html'));
