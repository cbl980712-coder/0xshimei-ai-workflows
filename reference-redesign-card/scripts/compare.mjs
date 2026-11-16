// 把「参考页」和「我的页」的量测结果并排，算出差距。用法：node scripts/compare.mjs ref.json mine.json > 对比.md
import fs from 'node:fs';
const [rf, mf] = process.argv.slice(2); if (!rf || !mf) { console.error('用法：node scripts/compare.mjs 参考.json 我的.json'); process.exit(1); }
const R = JSON.parse(fs.readFileSync(rf, 'utf8')), M = JSON.parse(fs.readFileSync(mf, 'utf8'));
const h1 = m => m.headings.find(h => h.tag === 'H1' && h.aboveFold);  // 只算首屏里的 H1（页面下方的 H1 不算）
const rows = [];
const row = (k, f, unit = '', ratio = true) => { const a = f(R), b = f(M); let d = '';
  if (ratio && typeof a === 'number' && typeof b === 'number' && b) d = (a / b).toFixed(2) + '×'; rows.push([k, a ?? '—', b ?? '—', d]); };
row('首屏 H1 字号(px)', m => h1(m)?.fontSize);
row('H1 ÷ 正文字号', m => h1(m) ? +(h1(m).fontSize / m.body.fontSize).toFixed(2) : null);
row('正文字号(px)', m => m.body.fontSize);
row('标题档位数（不同字号个数）', m => m.distinctHeadingSizes.length);
row('标题字号从大到小', m => m.distinctHeadingSizes.join(' / '), '', false);
row('正文段落行宽(px)', m => m.textBlockWidth);
row('页面最宽内容容器(px)', m => m.widestContainer);
row('首屏内块间纵向间距·中位(px)', m => m.medianFirstScreenGap);
row('各区块上内边距·中位(px)', m => m.medianSectionPadTop);
row('首屏按钮数（不含导航）', m => m.ctaAboveFold);
row('首屏主按钮文案', m => m.primaryCTA?.text, '', false);
row('主按钮底色', m => m.primaryCTA?.bg, '', false);
row('主按钮圆角', m => m.primaryCTA?.radius, '', false);
row('主按钮高度(px)', m => m.primaryCTA?.h);
row('主按钮字号(px)', m => m.primaryCTA?.fontSize);
row('主按钮 内边距', m => m.primaryCTA?.padding, '', false);
row('导航高度(px)', m => m.navHeight);
row('首屏大图/视频数', m => m.mediaAboveFold);
row('整页高度(px)', m => m.docHeight);
let o = `# 量测对比（自动生成）\n\n- 参考页：${R.url}（${R.title}）\n- 我的页：${M.url}（${M.title}）\n- 视口：${R.viewport.join('×')}。数字是浏览器实际算出来的样式，不是目测。\n\n| 指标 | 参考 | 我的 | 参考÷我的 |\n|---|---|---|---|\n`;
rows.forEach(r => o += `| ${r.join(' | ')} |\n`);
const list = (m, t) => `\n## ${t}：标题（前 12 个）\n\n| 标签 | 字号 | 字重 | 离页面顶 | 文字 | 选择器 |\n|---|---|---|---|---|---|\n` + m.headings.slice(0, 12).map(h => `| ${h.tag} | ${h.fontSize} | ${h.weight} | ${h.top} | ${h.text.replace(/\|/g, '/')} | \`${h.sel}\` |`).join('\n')
  + `\n\n## ${t}：按钮（前 8 个）\n\n| 文案 | 底色 | 圆角 | 高×宽 | 字号 | 首屏 | 选择器 |\n|---|---|---|---|---|---|---|\n` + m.buttons.slice(0, 8).map(b => `| ${b.text.replace(/\|/g, '/')} | ${b.solid ? b.bg : '描边 ' + b.border} | ${b.radius} | ${b.h}×${b.w} | ${b.fontSize} | ${b.aboveFold ? '是' : '否'} | \`${b.sel}\` |`).join('\n') + '\n';
o += list(R, '参考页') + list(M, '我的页');
console.log(o);
