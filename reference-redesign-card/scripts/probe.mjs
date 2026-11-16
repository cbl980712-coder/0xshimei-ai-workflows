// 打开页面（网址 / 本地 html / 图片），截图 + 量出留白、标题层级、按钮样式，可画编号圈。
// 用法：
//   node scripts/probe.mjs <网址|本地html|图片> --out <目录> --name <名字> [--marks marks.json] [--patch patch.css] [--width 1440]
// marks.json：[{"label":"1","selector":"h1"}, {"label":"2","box":[x,y,宽,高]}]  （box 用整页坐标，图片模式只能用 box）
import fs from 'node:fs'; import path from 'node:path';
import { parseArgs, readJSON, openBrowser, gotoPage, evalJS, screenshot, toURL, sleep } from './lib.mjs';

export const METRICS = String.raw`(() => {
  const W = innerWidth, H = innerHeight;
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05; };
  const absTop = el => Math.round(el.getBoundingClientRect().top + scrollY);
  const sel = el => { if (el.id) return '#' + CSS.escape(el.id); const p = []; let e = el;
    while (e && e.nodeType === 1 && e !== document.body && p.length < 4) {
      let s = e.tagName.toLowerCase(); const c = [...(e.classList||[])].filter(x => !/^\d|[:\/\[\]]/.test(x)).slice(0, 2);
      if (c.length) s += '.' + c.map(x => CSS.escape(x)).join('.');
      const sib = e.parentElement && [...e.parentElement.children].filter(x => x.tagName === e.tagName);
      if (sib && sib.length > 1 && !c.length) s += ':nth-of-type(' + (sib.indexOf(e) + 1) + ')';
      p.unshift(s); e = e.parentElement; if (e && e.id) { p.unshift('#' + CSS.escape(e.id)); break; } }
    return p.join(' > '); };
  const txt = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50);
  const px = v => parseFloat(v) || 0;
  // 正文字号：按文字量加权最常见的字号
  const wts = {}; const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = walker.nextNode())) { const t = n.textContent.trim(); if (t.length < 2 || !n.parentElement || !vis(n.parentElement)) continue;
    const fs = Math.round(px(getComputedStyle(n.parentElement).fontSize)); wts[fs] = (wts[fs] || 0) + t.length; }
  const body = +Object.entries(wts).sort((a, b) => b[1] - a[1])[0]?.[0] || 16;
  const heads = [...document.querySelectorAll('h1,h2,h3,h4')].filter(vis).slice(0, 40).map(h => { const s = getComputedStyle(h);
    return { tag: h.tagName, text: txt(h), sel: sel(h), fontSize: px(s.fontSize), weight: s.fontWeight, lineHeight: s.lineHeight, color: s.color,
      top: absTop(h), marginTop: px(s.marginTop), marginBottom: px(s.marginBottom), width: Math.round(h.getBoundingClientRect().width), aboveFold: absTop(h) < H }; });
  // 按钮：a/button 里有底色或边框的
  const btns = [...document.querySelectorAll('a,button,[role=button],input[type=submit]')].filter(vis).map(b => { const s = getComputedStyle(b), r = b.getBoundingClientRect();
    const bg = s.backgroundColor, hasBg = !/rgba\(0, 0, 0, 0\)|transparent/.test(bg), hasBd = px(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none';
    return { text: txt(b), sel: sel(b), bg, color: s.color, border: hasBd ? s.borderTopWidth + ' ' + s.borderTopColor : 'none', radius: s.borderRadius,
      padding: s.paddingTop + ' ' + s.paddingRight, fontSize: px(s.fontSize), weight: s.fontWeight, w: Math.round(r.width), h: Math.round(r.height), top: absTop(b), left: Math.round(r.left),
      solid: hasBg, outlined: !hasBg && hasBd, aboveFold: absTop(b) < H, inNav: !!b.closest('nav,header') }; })
    .filter(b => (b.solid || b.outlined) && b.h >= 24 && b.text && b.top >= 0 && b.left >= 0 && !/^(skip|跳到)/i.test(b.text)).slice(0, 30);
  const secEls = [...document.querySelectorAll('main > *, body > section, body > div > section, section')].filter(vis).filter(e => e.getBoundingClientRect().height > 100);
  const seen = new Set(); const sections = [];
  secEls.forEach(e => { if (secEls.some(o => o !== e && o.contains(e) && sections.length > 10)) return; if (seen.has(e)) return; seen.add(e); const s = getComputedStyle(e), r = e.getBoundingClientRect();
    sections.push({ sel: sel(e), top: absTop(e), height: Math.round(r.height), padTop: px(s.paddingTop), padBottom: px(s.paddingBottom), bg: s.backgroundColor }); });
  sections.sort((a, b) => a.top - b.top);
  const pads = sections.map(s => Math.max(s.padTop, 0)).filter(x => x > 0).sort((a, b) => a - b);
  // 第一屏里文字块之间的纵向间距
  const blocks = [...document.querySelectorAll('h1,h2,h3,p,ul,ol,a,button,img,form,pre')].filter(vis).map(e => e.getBoundingClientRect()).filter(r => r.top + scrollY < H * 1.6 && r.width > 40)
    .map(r => [r.top + scrollY, r.bottom + scrollY]).sort((a, b) => a[0] - b[0]);
  const gaps = []; let end = -1; blocks.forEach(([t, b]) => { if (end >= 0 && t - end > 8) gaps.push(Math.round(t - end)); end = Math.max(end, b); });
  const p0 = [...document.querySelectorAll('p,li')].filter(vis).find(p => txt(p).length > 40);
  const mw = [...document.querySelectorAll('main,article,section,div')].filter(vis).map(e => e.getBoundingClientRect().width).filter(w => w < W - 10).sort((a, b) => b - a)[0] || 0;
  const imgs = [...document.querySelectorAll('img,video,svg,canvas,picture')].filter(vis).filter(e => e.getBoundingClientRect().width > 120);
  const nav = document.querySelector('nav,header');
  const bs = getComputedStyle(document.body);
  return { url: location.href, title: document.title, viewport: [W, H], docHeight: document.documentElement.scrollHeight,
    body: { fontSize: body, fontFamily: bs.fontFamily.slice(0, 80), color: bs.color, bg: bs.backgroundColor, lineHeight: bs.lineHeight },
    textBlockWidth: p0 ? Math.round(p0.getBoundingClientRect().width) : null, textBlockFont: p0 ? px(getComputedStyle(p0).fontSize) : null,
    widestContainer: Math.round(mw), navHeight: nav ? Math.round(nav.getBoundingClientRect().height) : 0,
    headings: heads, h1Ratio: heads.find(h => h.tag === 'H1' && h.aboveFold) ? +(heads.find(h => h.tag === 'H1' && h.aboveFold).fontSize / body).toFixed(2) : null,
    headingLevels: [...new Set(heads.map(h => h.tag))], distinctHeadingSizes: [...new Set(heads.map(h => h.fontSize))].sort((a, b) => b - a),
    buttons: btns, primaryCTA: btns.find(b => b.solid && !b.inNav && b.aboveFold) || btns.find(b => b.solid) || null,
    ctaAboveFold: btns.filter(b => b.aboveFold && !b.inNav).length,
    sections, medianSectionPadTop: pads.length ? pads[Math.floor(pads.length / 2)] : null,
    firstScreenGaps: gaps, medianFirstScreenGap: gaps.length ? [...gaps].sort((a, b) => a - b)[Math.floor(gaps.length / 2)] : null,
    mediaCount: imgs.length, mediaAboveFold: imgs.filter(e => absTop(e) < H).length };
})()`;

const MARK_JS = marks => `(() => { const marks = ${JSON.stringify(marks)}; const out = [];
  marks.forEach((m, i) => { let r; if (m.selector) { const e = document.querySelector(m.selector); if (!e) { out.push('未找到 ' + m.selector); return; } const b = e.getBoundingClientRect(); r = { x: b.left + scrollX, y: b.top + scrollY, w: b.width, h: b.height }; }
    else r = { x: m.box[0], y: m.box[1], w: m.box[2], h: m.box[3] };
    const d = document.createElement('div'); d.style.cssText = 'position:absolute;z-index:2147483647;pointer-events:none;border:3px solid #e11d48;border-radius:10px;box-shadow:0 0 0 2px #fff;left:' + (r.x - 4) + 'px;top:' + (r.y - 4) + 'px;width:' + (r.w + 8) + 'px;height:' + (r.h + 8) + 'px';
    const t = document.createElement('div'); t.textContent = m.label || (i + 1); t.style.cssText = 'position:absolute;left:-3px;top:-14px;transform:translateY(-50%);background:#e11d48;color:#fff;font:700 15px/1 system-ui;padding:5px 8px;border-radius:999px;white-space:nowrap;box-shadow:0 0 0 2px #fff';
    if (r.y < 40) { t.style.top = '100%'; t.style.marginTop = '16px'; } d.appendChild(t); document.body.appendChild(d); }); return out; })()`;

export async function run(args) {
  const [target] = args._; if (!target) throw new Error('缺少目标：网址 / html / 图片');
  const isUrl = /^(https?|file|data):/.test(target);
  if (!isUrl && !fs.existsSync(target)) throw new Error(`找不到文件：${target}。请检查路径（路径里有空格要用引号括起来），或者直接给 https:// 开头的网址。`);
  if (!isUrl && fs.statSync(target).size === 0) throw new Error(`文件是空的：${target}。`);
  if (/\.(png|jpe?g|webp|gif)$/i.test(target) && !isUrl) { const h = fs.readFileSync(target).subarray(0, 12); const ok = (h[0]===0x89&&h[1]===0x50) || (h[0]===0xff&&h[1]===0xd8) || h.toString('latin1',0,4)==='RIFF' || h.toString('latin1',0,3)==='GIF'; if (!ok) throw new Error(`${target} 不是有效的图片（文件头不对）。请重新截一张 png 或 jpg。`); }
  if (args.marks === true || (args.marks && !fs.existsSync(args.marks))) throw new Error(`找不到圈选文件：${args.marks}。不想圈就去掉 --marks / --own-marks / --ref-marks 参数。`);
  let marks0 = null;
  if (args.marks) {
    marks0 = readJSON(args.marks, '圈选文件', '格式见 templates/marks.example.json。');
    if (!Array.isArray(marks0) || !marks0.length || marks0.some(m => !m || typeof m !== 'object' || (typeof m.selector !== 'string' && !(Array.isArray(m.box) && m.box.length === 4 && m.box.every(Number.isFinite)))))
      throw new Error(`圈选文件 ${args.marks} 的格式不对：应是一个列表，每项要有 "selector"（CSS 选择器字符串）或 "box"（[x, y, 宽, 高] 四个数字）。例：[{"label":"1 标题","selector":"h1"}]`);
  }
  const out = args.out || 'out'; const name = args.name || 'page'; const width = +args.width || 1440;
  fs.mkdirSync(out, { recursive: true });
  const t0 = Date.now();
  const b = await openBrowser({ workDir: out, width, height: +args.height || 900 });
  try {
    const isImg = /\.(png|jpe?g|webp|gif)$/i.test(target) && !/^https?:/.test(target);
    let url = toURL(target), metrics = null;
    if (isImg) {
      const ext = path.extname(target).slice(1).replace('jpg', 'jpeg');
      const data = fs.readFileSync(target).toString('base64');
      url = 'data:text/html;charset=utf-8,' + encodeURIComponent(`<body style="margin:0"><img src="data:image/${ext};base64,${data}" style="display:block;max-width:${width}px">`);
    }
    await gotoPage(b, url);
    if (!isImg) {
      // 滚一遍触发懒加载，再回顶
      await evalJS(b, `(async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}scrollTo(0,0);})()`);
      await sleep(800);
      if (args.patch) { const css = fs.readFileSync(args.patch, 'utf8'); await evalJS(b, `(()=>{const s=document.createElement('style');s.id='__patch';s.textContent=${JSON.stringify(css)};document.head.appendChild(s);})()`); await sleep(400); }
      metrics = await evalJS(b, METRICS);
      if (!(await evalJS(b, `(document.body.innerText || '').trim().length > 5 || document.querySelectorAll('img,video,canvas,svg').length > 0`))) throw new Error('页面打开了但里面几乎没有内容（可能是空白页、需要登录，或被反爬拦住）。换个能公开访问的页面，或改给截图。');
      fs.writeFileSync(path.join(out, name + '.json'), JSON.stringify(metrics, null, 1));
    }
    await screenshot(b, path.join(out, name + '-top.png'));
    await screenshot(b, path.join(out, name + '-full.png'), { full: true });
    if (args.marks) {
      const marks = marks0;
      const miss = await evalJS(b, MARK_JS(marks));
      if (miss.length) console.log('⚠️ ' + miss.join('；'));
      await screenshot(b, path.join(out, name + '-marked.png'), { full: true });
      await screenshot(b, path.join(out, name + '-marked-top.png'));
    }
    console.log(`✅ ${name}: ${((Date.now() - t0) / 1000).toFixed(1)} 秒 → ${out}/` + (metrics ? `（${(() => { const h = metrics.headings.find(h=>h.tag==='H1'&&h.aboveFold); return h ? '首屏 H1 ' + h.fontSize + 'px' : '首屏没有 H1'; })()}，正文 ${metrics.body.fontSize}px，首屏按钮 ${metrics.ctaAboveFold}）` : ''));
  } finally { await b.close(); }
}
if (import.meta.url === 'file://' + process.argv[1] || process.argv[1]?.endsWith('probe.mjs')) run(parseArgs(process.argv.slice(2))).catch(e => { console.error('❌ ' + e.message); process.exit(1); });
