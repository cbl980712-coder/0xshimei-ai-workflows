// 第三步一条命令：套 patch.css 验收 + 生成改版清单.md 和 指令卡.html。
// 用法：node scripts/finish.mjs <目录>   （目录里要有 checklist.json，可选 patch.css）
import { spawnSync } from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
const dir = process.argv[2]; const here = path.dirname(fileURLToPath(import.meta.url));
if (!dir || !fs.existsSync(path.join(dir, 'checklist.json'))) { console.error('用法：node scripts/finish.mjs <目录>（目录里需要 checklist.json）'); process.exit(1); }
const run = (s, args) => { const r = spawnSync(process.execPath, [path.join(here, s), ...args], { stdio: 'inherit' }); if (r.status) process.exit(r.status); };
const patch = path.join(dir, 'patch.css');
run('verify.mjs', [path.join(dir, 'checklist.json'), '--out', dir, '--md', '改后验收清单.md', ...(fs.existsSync(patch) ? ['--patch', patch] : [])]);
run('render.mjs', [path.join(dir, 'checklist.json'), '--out', dir, '--md', '改版清单.md', '--html', '指令卡.html']);
