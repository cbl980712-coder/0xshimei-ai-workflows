# 分步 3D 建模工具包

一句话让 AI 写完整 3D 场景，常常报错、白屏、一团浆糊。这个包把它拆成：**部件树+坐标装配图 → 一次一个部件 → 逐个自检 → 自动组装**，
输出一个单文件网页：能拖拽旋转，点击高亮每个部件。

## 先看目录：你应该在哪里敲命令
下载（git clone 或 zip 解压）后会得到一个文件夹，**不管它叫什么名字**（`step-by-step-3d-builder`、带 `-main` 后缀、或者别的），都不影响使用。
**下面把它叫「工具包目录」：进入直接放着 `step_by_step_3d_builder.py` 和 `README.md` 的那一层，后面所有命令都在这一层执行。** 如果你打开文件夹只看到另一个文件夹，再点进去一层，直到能看到这两个文件为止。

```
（你的文件夹，名字不限）/          ← 工具包目录：终端先 cd 到这里，本文所有命令都从这里执行
├── README.md
├── SKILL.md                      ← 给 Claude Code / Cursor 用，路径就是 ./SKILL.md
├── step_by_step_3d_builder.py    ← 命令行脚本
├── viewer_template.html
├── prompts_3d_modular.md         ← 网页版聊天用的提示词模板
├── examples/                     ← 4 个现成例子（每个都有 index.html）
└── my3d/                         ← 你自己的项目放这里（第一次 init 时自动创建）
```
本文所有命令都写成 `python3 step_by_step_3d_builder.py ...`，项目目录都写成 `my3d/xxx`（相对工具包目录）。

## 先看效果（不用装任何东西，有浏览器、能上网就行）
双击打开 `examples/01-animal-cell/index.html`（细胞）、`examples/02-watch-movement/index.html`（机芯）、`examples/03-four-stroke-engine/index.html`（发动机）、`examples/04-anglepoise-lamp/index.html`（台灯，最粗糙的一个）。
**注意：成品只有一个 HTML 文件，不等于可以离线用。** three.js 从 jsDelivr CDN 加载，每次打开页面都需要能访问网络（首次打开和之后都一样，没做离线内联）。

## 三步上手

### 0. 先选你怎么用（脚本本身不会调用 AI）

`step_by_step_3d_builder.py` **不调用任何大模型**，它只做：抓资料、检查、自检、组装。「写 JSON」这一步必须由大模型完成，有两种方式：

| 方式 | 谁写 JSON | 谁保存文件、跑脚本 | 适合 |
|---|---|---|---|
| A. Claude Code / Cursor | 它按 `SKILL.md` 自己写 | 它替你保存、替你跑命令 | 会用这类工具的人 |
| B. 网页版聊天（ChatGPT / Claude / Gemini 网页等） | 你把脚本打印的提示词复制过去，模型回一段 JSON | **你自己**复制、保存成文件、敲命令 | 其他人；下面第 2 步有逐步示范 |

费用：Python 脚本不需要装任何第三方库，也不收费；但 Claude Code、Cursor 和各家大模型可能占用你的订阅额度或产生 API 费用，「只用标准库」不等于整个流程免费。

### 1. 装什么
- **Python 3**（只用标准库，不用 pip install）。已验证：macOS + Python 3.9.6 + Chrome；其他系统和版本**暂未验证**，见文末「限制」。
  - Mac：终端输入 `python3 -V`，没有就 `xcode-select --install`；或到 python.org 下载
  - Windows（**仅供参考，未实测**）：到 python.org 安装，勾选 "Add python.exe to PATH"；之后命令里的 `python3` 换成 `python`（或 `py -3`）
- **Chrome**（已验证）。Edge 等其他 Chromium 浏览器脚本也会去找，但**没实测**；找不到时设环境变量 `BROWSER_BIN` 指向浏览器程序
- **一个会写 JSON 的大模型**：见上面「先选你怎么用」

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
（命令后面 `#` 开头的是注释，不要一起敲进去。）
然后循环（每个部件一次）：
```bash
python3 step_by_step_3d_builder.py status my3d/lamp                # 下一个该写谁
python3 step_by_step_3d_builder.py prompt part my3d/lamp <id>      # 贴给大模型，结果存成 my3d/lamp/parts/<id>.json
python3 step_by_step_3d_builder.py test my3d/lamp --only <id>      # 不通过就 prompt fix 再来
```
用方式 A（Claude Code / Cursor）时，对它说"按 ./SKILL.md 帮我做一个 XX 的 3D 模型"，由**它**写 JSON 并执行上面这些命令；脚本自己不会去调用它。
`plan.json` 和 `parts/*.json` 的字段格式：看 `examples/*/plan.json` 和 `examples/*/parts/*.json`，照抄改就行。

#### 方式 B 逐步示范：网页版聊天用户怎么保存 JSON（用台灯例子，所有命令在工具包目录执行）
1. **建项目、抓资料**：跑上面的 `init` 和 `fetch`。此时 `my3d/lamp/` 文件夹已经有了。
2. **拿拆解提示词**：跑 `prompt decompose my3d/lamp`，把终端打印出来的整段文字全部复制，粘贴到网页版聊天里发送。
3. **保存 plan.json**：模型会回一段 JSON。只复制 JSON 本身（从第一个 `{` 到最后一个 `}`），用**纯文本编辑器**（Mac 的 VS Code / 文本编辑里选「纯文本」；Windows 记事本）新建文件，保存为 `my3d/lamp/plan.json`（就在第 1 步生成的文件夹里，编码选 UTF-8）。
   **保存后先核对路径**：如果之后运行 `check` 提示「plan.json 里没有 parts」或找不到 plan.json（`init` 已经建了一个空的 plan.json 占位，所以你的内容可能存到了别处），先看文件是不是真的在 `my3d/lamp/` 这个文件夹里（不是桌面、下载文件夹，也不是工具包目录本身），再看文件名有没有被编辑器自动加上 `.txt` 后缀（实际变成 `plan.json.txt`；Windows 默认隐藏扩展名，要在资源管理器里打开「文件扩展名」才看得见）。
4. **检查**：跑 `check my3d/lamp`。报冲突就按提示改（可以把报错发回模型让它改 plan.json，再覆盖保存）；通过后继续。想看保存成功后 plan.json 长什么样，对照 `examples/04-anglepoise-lamp/plan.json`。
5. **看该写谁**：跑 `status my3d/lamp`，它会列出部件 ID（台灯例子是 `base`、`springs`、`lower_arm`、`upper_arm`、`balance_weight`、`socket`、`reflector`、`bulb`）和下一个该写的。
6. **逐个部件**：跑 `prompt part my3d/lamp base`（`base` 换成 status 给的 ID），复制整段发给模型，把返回的 JSON 保存为 `my3d/lamp/parts/base.json`（`parts` 文件夹 `init` 时已建好）。格式参照 `examples/04-anglepoise-lamp/parts/base.json`。
7. **测这一个，并看进度**：每生成一个部件，先跑 `test my3d/lamp --only base`（`base` 换成这个部件的 ID），再跑 `status my3d/lamp` 看进度。**注意：`status` 的 ✓ 只代表文件存在且是合法 JSON，不代表几何检查通过**——几何是否合格只看 `test` 的结果。通过就回到第 5 步写下一个；等所有部件的文件都准备好、并且**逐个通过了 `test`**，再执行 `build`。
8. **这一个生成失败了**：`test` 报错时跑 `prompt fix my3d/lamp base`，把整段发给模型，拿到新 JSON 后**直接覆盖** `my3d/lamp/parts/base.json`（只覆盖这个文件），再 `test` 一次。不用动别的部件。

保存 JSON 的三条硬规矩：
- 文件内容必须是**合法 JSON**。模型回复里常带 ```` ```json ```` 和 ```` ``` ```` 这两行代码围栏，**不要一起复制进文件**；前后的解释文字也不要。
- **不能只改扩展名**：把 `.txt`、`.docx`、网页另存的文件直接改名成 `.json` 是无效的，里面必须真的只有 JSON 文本。
- 文件名必须和 ID 完全一致（`parts/base.json`，不是 `parts/base (1).json`）。格式不对时脚本会用中文报行号和列号；`status` 里的 ✓ 只代表文件存在且是合法 JSON，不代表几何合格。

### 3. 怎么跑 & 输出在哪
```bash
python3 step_by_step_3d_builder.py build my3d/lamp --screenshot my3d/lamp/preview.png
```
- 成品：`my3d/lamp/index.html`（单文件，双击打开；仍需联网加载 three.js，见上文）
- 自检报告：`report.json`；耗时：`run_log.json`；坐标装配图：`assembly.txt`
- **自检通过 ≠ 模型长得对。** `build` 末尾会再提醒一次：几何自检只查尺寸和范围，不查连接关系和整体形状，请打开成品人工看一眼。
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

## 反面案例：台灯（自检 8/8 通过，但上下灯臂没接上）
`examples/04-anglepoise-lamp/` 是照本 README 现做的，8 个部件全部通过自检，`build` 也成功了；但打开 `index.html` 或 `preview.png` 会看到上臂和下臂**没有接在一起**，弹簧、配重的位置也很随意。
原因：自检只检查每个部件的尺寸、有没有跑出范围，**不会检查两个部件之间有没有连上**。目前没有可靠的自动办法发现这类问题，所以这个例子故意保留，提醒你：自检全绿之后，仍要自己看成品。想看做得像样的，参考例 1～3。

## 自检到底查了什么
每个部件挂进场景后，在无头浏览器里检查：构建是否抛错（语法错误只影响这个部件）；顶点是否有 NaN；实际尺寸是否超出声明的 `bound`
（会运动的部件按 6 个时间点采样）；是否跑出父部件范围；紧凑的同级部件包围盒是否大幅重叠（只警告）；依赖的部件是否已先挂载。

## 限制（请先读）
- **脚本不调用大模型**。"写每个部件的 JSON"这一步要你自己（或 Claude Code / Cursor）来做；脚本负责检查、组装、报告。
- three.js 通过 CDN 加载（版本固定 0.160.0）：成品网页**每次打开都依赖网络**，"单文件"不等于"离线可用"；`doctor` 和 `test` 也需要联网。
- 自检是几何层面的：能发现"超出范围、没生成、写错尺寸、语法错"，**发现不了"形状不像"**——最后仍要人看一眼。
- 动画只是示意（齿轮转速按齿数比算，但没有精确啮合相位；发动机用曲柄滑块公式，但不是真实工况）。
- 部件形状库有限（球、盒、柱、锥、环、胶囊、管、齿轮、散布）；更复杂的要用 `code` 写 Three.js。
- **已验证环境：macOS + Python 3.9.6 + Chrome。其他系统（Windows、Linux）及 Python 版本（如 3.8、3.12）暂未验证。** 代码里写了 Edge 和各系统的浏览器路径查找，只是代码里有，不代表在这些环境通过了验收；Windows 的安装说明仅供参考。
- 工具链有费用的部分是大模型（订阅额度或 API），不是这个脚本；脚本只用标准库。
- 文档里所有"手工需要多久、成本多少"的数字都是估算或假设（"约 161 秒"之类的用时是当时手工计时一次、含大模型写 JSON 的时间，别人跑会不同），见上一级目录的 `MONEY.md` / `REPORT.md`。
