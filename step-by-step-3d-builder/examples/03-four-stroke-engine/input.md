# 例 3 输入：单缸四冲程发动机

- 描述：单缸四冲程发动机（活塞、连杆、曲轴、气门、凸轮轴）
- 真实资料网页：https://en.wikipedia.org/wiki/Four-stroke_engine
  - 抓取：HTML 256,020 字节 → 文字 28,811 字符，存为 `source.txt`
  - 命中：piston×34、valve×38、exhaust×33、crankshaft×9、camshaft×7、spark plug×2、connecting rod×3；"flywheel" 0 次（飞轮部件用 crankshaft 当依据词）
  - 曲柄半径 0.6、连杆长 2.2 等尺寸是我定的示意值

## 输出

`plan.json`、`assembly.txt`、`parts/*.json`（10 个）、`index.html`、`report.json`、`run_log.json`、`preview.png`。
活塞、连杆按曲柄滑块公式联动，气门按进气/排气冲程开合（`update` 字段里的脚本）。

## 耗时（当时用本机时钟 `date` 计时一次）

- `init` → 最终 `build` 成功：**约 174 秒**（含 plan 检查误报修复、3 轮自检失败修复）
- 脚本自己：浏览器自检 2.1 秒、截图 2.2 秒

（复测：2026-11-12 在 macOS + Python 3.9 + Chrome 上重新 fetch、build，部件数、自检通过数、成品体积、网页字符数、依据词命中次数都与上面一致；抓网页约 1.2～1.5 秒、浏览器自检约 2.3～2.6 秒，随机器和网速上下浮动。**"约 N 秒"的总用时是当时一次性手工计时，含大模型写 JSON 的时间，无法复现，每次都会不同。**）
