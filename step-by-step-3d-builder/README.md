# 分步 3D 建模工具包

一句话让 AI 写完整 3D 场景，常常报错、白屏、一团浆糊。这个包把它拆成：**部件树+坐标装配图 → 一次一个部件 → 逐个自检 → 自动组装**，
输出一个单文件网页：能拖拽旋转，点击高亮每个部件。

## 先看效果（不用装任何东西，有浏览器、能上网就行）
双击打开 `examples/01-animal-cell/index.html`（细胞）、`examples/02-watch-movement/index.html`（机芯）、`examples/03-four-stroke-engine/index.html`（发动机）、`examples/04-anglepoise-lamp/index.html`（台灯，最粗糙的一个）。
three.js 从 jsDelivr CDN 加载，首次打开需要联网。

## 三步上手

### 1. 装什么
- **Python 3.8+**（只用标准库，不用 pip install）
  - Mac：终端输入 `python3 -V`，没有就 `xcode-select --install`；或到 python.org 下载
  - Windows：到 python.org 安装，勾选 "Add python.exe to PATH"；之后命令里的 `python3` 换成 `python`（或 `py -3`）
- **Chrome 或 Edge**（本机已有即可；脚本自动找，找不到时设环境变量 `BROWSER_BIN` 指向它）
- **一个会写 JSON 的大模型**：Claude Code / Cursor（把本目录当 Skill 用，见 `SKILL.md`），或任意网页版聊天（手动复制 `prompts_3d_modular.md` 里的模板）

先跑这条，确认环境好了：
```bash
python3 step_by_step_3d_builder.py doctor
```
看到 `端到端  : ✓` 和 `环境OK` 才继续。

> 资料页怎么挑：要选**讲具体结构、有部件名**的页面。`fetch` 抓到的字符少于 5000 时会提示——Wikipedia 上像 `/wiki/Lamp` 这种总称词条常是消歧义页，里面没有部件名，换成更具体的页面（如本例的 Anglepoise_lamp）。

### 2. 怎么放输入
你的输入 = **一句话描述 + 一个真实的资料网页**（百科、产品说明页都行）。
```bash
python3 step_by_step_3d_builder.py init my3d/lamp "台灯结构（底座、弹簧、灯臂、反光罩、灯泡）" --url "https://en.wikipedia.org/wiki/Anglepoise_lamp"
python3 step_by_step_3d_builder.py fetch my3d/lamp
python3 step_by_step_3d_builder.py prompt decompose my3d/lamp      # 把输出贴给大模型，得到 plan.json 内容，存到 my3d/lamp/plan.json
python3 step_by_step_3d_builder.py check my3d/lamp                 # 检查并打印坐标装配图
```
然后循环（每个部件一次）：
```bash
python3 step_by_step_3d_builder.py status my3d/lamp                # 下一个该写谁
python3 step_by_step_3d_builder.py prompt part my3d/lamp <id>      # 贴给大模型，结果存成 my3d/lamp/parts/<id>.json
python3 step_by_step_3d_builder.py test my3d/lamp --only <id>      # 不通过就 prompt fix 再来
```
用 Claude Code / Cursor 时，直接说"按 SKILL.md 帮我做一个 XX 的 3D 模型"，它会替你跑完上面所有步骤。
`plan.json` 和 `parts/*.json` 的字段格式：看 `examples/*/plan.json` 和 `examples/*/parts/*.json`，照抄改就行。

### 3. 怎么跑 & 输出在哪
```bash
python3 step_by_step_3d_builder.py build my3d/lamp --screenshot my3d/lamp/preview.png
```
- 成品：`my3d/lamp/index.html`（单文件，双击打开）
- 自检报告：`report.json`；耗时：`run_log.json`；坐标装配图：`assembly.txt`
- 有部件没通过时不输出 HTML（想先看看就加 `--allow-fail`，出错的部件会显示红色线框占位）

### 出错了怎么办
- 所有命令都会用中文提示原因；`check` 的"放不进父部件 / bound 太大"类提示都带数值，照提示缩小该部件的 bound、把它的坐标移近父部件中心（或把父部件的 bound 调大）再跑一次，百分比会下降（实测台灯例子：反光罩 147% → 113% → 104% → 通过）。
- `test` 报"比自己声明的 bound 大"：用 `prompt fix 目录 <id>` 取修复提示词，只改那一个部件。
- 带 ⚠/`!` 的"同级包围盒重叠"只是提醒，不影响 build。
- `status` 里 ✓ 只代表部件文件存在且格式对，几何是否合格要跑 `test`。

## 文件说明
| 文件 | 作用 |
|---|---|
| `step_by_step_3d_builder.py` | 命令行：doctor / init / fetch / prompt / check / status / test / build |
| `viewer_template.html` | 成品网页的模板（Three.js + 轨道控制器 + 点击高亮 + 逐部件自检） |
| `prompts_3d_modular.md` | 三个提示词模板：拆解 / 单部件 / 修复 |
| `SKILL.md` | 给 Claude Code / Cursor 用的 Skill |
| `examples/` | 4 组真实例子：输入、中间文件、成品、报告、耗时（04 是验收时照本 README 现做的台灯，形状粗糙，见其 input.md） |

## 自检到底查了什么
每个部件挂进场景后，在无头浏览器里检查：构建是否抛错（语法错误只影响这个部件）；顶点是否有 NaN；实际尺寸是否超出声明的 `bound`
（会运动的部件按 6 个时间点采样）；是否跑出父部件范围；紧凑的同级部件包围盒是否大幅重叠（只警告）；依赖的部件是否已先挂载。

## 限制（请先读）
- **脚本不调用大模型**。"写每个部件的 JSON"这一步要你自己（或 Claude Code / Cursor）来做；脚本负责检查、组装、报告。
- three.js 通过 CDN 加载（版本固定 0.160.0），成品网页**首次打开需要联网**；`doctor` 和 `test` 也需要。
- 自检是几何层面的：能发现"超出范围、没生成、写错尺寸、语法错"，**发现不了"形状不像"**——最后仍要人看一眼。
- 动画只是示意（齿轮转速按齿数比算，但没有精确啮合相位；发动机用曲柄滑块公式，但不是真实工况）。
- 部件形状库有限（球、盒、柱、锥、环、胶囊、管、齿轮、散布）；更复杂的要用 `code` 写 Three.js。
- 自带 Python 3.9 + Chrome（macOS）上测通；Windows / Linux 的浏览器路径查找写了但**没有实机测过**。
- 文档里所有"手工需要多久、成本多少"的数字都是估算或假设（"约 161 秒"之类的用时是当时手工计时一次、含大模型写 JSON 的时间，别人跑会不同），见上一级目录的 `MONEY.md` / `REPORT.md`。
