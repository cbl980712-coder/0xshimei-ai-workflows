// 第三步一条命令：只重新打开「你的页面」（own_url）两次——改前量一遍、套 patch.css 后量一遍；不会重新打开参考页，也不重生成 对比.md / 红圈图。
// 套 patch.css 验收 + 生成改版清单.md 和 指令卡.html。
// 用法：node scripts/finish.mjs <目录>   （目录里要有 checklist.json，可选 patch.css）
import { spawnSync } from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
const dir = process.argv[2]; const here = path.dirname(fileURLToPath(import.meta.url));
if (!dir || !fs.existsSync(path.join(dir, 'checklist.json'))) { console.error('用法：node scripts/finish.mjs <目录>（目录里需要 checklist.json）'); process.exit(1); }
const run = (s, args) => { const r = spawnSync(process.execPath, [path.join(here, s), ...args], { stdio: 'inherit' }); if (r.status) process.exit(r.status); };
const patch = path.join(dir, 'patch.css');
// 自己的页面只有截图时：图片上套不了 CSS，也量不了样式，所以不验收，只出清单和指令卡。
let ownUrl = ''; try { ownUrl = String(JSON.parse(fs.readFileSync(path.join(dir, 'checklist.json'), 'utf8')).own_url || ''); } catch {}
const ownIsImage = /\.(png|jpe?g|webp|gif)$/i.test(ownUrl) && !/^https?:/i.test(ownUrl);
if (ownIsImage) console.log('ℹ️ checklist.json 里的 own_url 是图片：不能套 CSS、没有改后实测值，跳过验收，只生成 改版清单.md 和 指令卡.html。');
else run('verify.mjs', [path.join(dir, 'checklist.json'), '--out', dir, '--md', '改后验收清单.md', ...(fs.existsSync(patch) ? ['--patch', patch] : [])]);
run('render.mjs', [path.join(dir, 'checklist.json'), '--out', dir, '--md', '改版清单.md', '--html', '指令卡.html']);
