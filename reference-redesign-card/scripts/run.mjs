// 第一步一条命令：量我的页 + 量参考页 + 出对比表。
// 用法：node scripts/run.mjs --own <我的网址|截图> --ref <参考网址|截图> --out <输出目录> [--own-marks 我的圈.json] [--ref-marks 参考圈.json]
import { spawnSync } from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
import { parseArgs } from './lib.mjs';
const a = parseArgs(process.argv.slice(2)); const here = path.dirname(fileURLToPath(import.meta.url));
if (!a.own || !a.ref || !a.out) { console.error('用法：node scripts/run.mjs --own <网址> --ref <网址> --out <目录> [--own-marks f.json] [--ref-marks f.json]'); process.exit(1); }
fs.mkdirSync(a.out, { recursive: true });
const t0 = Date.now();
const go = (target, name, marks) => spawnSync(process.execPath, [path.join(here, 'probe.mjs'), target, '--out', a.out, '--name', name, ...(marks ? ['--marks', marks] : [])], { stdio: 'inherit' });
const r1 = go(a.ref, 'ref', a['ref-marks']), r2 = go(a.own, 'mine', a['own-marks']);
if (r1.status || r2.status) { console.error(`\n没做完：${r1.status ? '参考页' : ''}${r1.status && r2.status ? '和' : ''}${r2.status ? '我的页' : ''}没量成功，原因见上面 ❌ 那行。改好再重跑。`); process.exit(1); }
const refJ = path.join(a.out, 'ref.json'), mineJ = path.join(a.out, 'mine.json');
if (fs.existsSync(refJ) && fs.existsSync(mineJ)) {
  const r = spawnSync(process.execPath, [path.join(here, 'compare.mjs'), refJ, mineJ], { encoding: 'utf8' });
  fs.writeFileSync(path.join(a.out, '对比.md'), r.stdout); console.log('✅ 对比表 → ' + path.join(a.out, '对比.md'));
} else console.log('（参考或我的是图片，没有量测数据，只出了截图；对比交给 Claude 看图）');
console.log(`第一步完成，用时 ${((Date.now() - t0) / 1000).toFixed(0)} 秒。下一步：让 Claude Code 按 SKILL.md 写 ${path.join(a.out, 'checklist.json')} 和 patch.css。`);
