# 例 2 输入：机械腕表机芯

- 描述：机械腕表机芯（发条盒、齿轮系、擒纵机构、摆轮游丝）
- 真实资料网页：https://en.wikipedia.org/wiki/Watch
  - 抓取：HTML 650,306 字节 → 文字 79,120 字符，存为 `source.txt`
  - 命中：mainspring×6、escapement×11、balance wheel×14、jewel×11、crown×12、hairspring×1、pallet×1
  - 注意：该页没有 "barrel / mainplate / pinion" 这些词，所以发条盒、主夹板用 mainspring、plate 当依据词；齿数、模数、中心距是我按齿轮啮合公式自己定的，**不是**网页给的数据

## 输出

`plan.json`、`assembly.txt`、`parts/*.json`（11 个）、`index.html`（成品）、`report.json`、`run_log.json`、`preview.png`，含义同例 1。

## 耗时（当时用本机时钟 `date` 计时一次）

- `init` → 最终 `build` 成功：**约 158 秒**（含第一次 `fetch` 因网址写错 404、1 次自检失败修复）
- 脚本自己：浏览器自检 2.2 秒、截图 1.9 秒

（复测：2026-11-12 在 macOS + Python 3.9 + Chrome 上重新 fetch、build，部件数、自检通过数、成品体积、网页字符数、依据词命中次数都与上面一致；抓网页约 1.2～1.5 秒、浏览器自检约 2.3～2.6 秒，随机器和网速上下浮动。**"约 N 秒"的总用时是当时一次性手工计时，含大模型写 JSON 的时间，无法复现，每次都会不同。**）
