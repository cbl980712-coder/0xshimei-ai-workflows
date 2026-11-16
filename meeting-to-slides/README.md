# meeting-to-slides：会议记录 → 汇报 PPT

把会议速记 / 转写稿，整理成 5–7 页商务版式 PPT，外加演讲提纲备忘。排版脚本离线运行，**不登录、不调用任何付费 API**；"提炼要点"这一步由 Claude Code 按 `SKILL.md` 做（也可以不用 Claude，只用脚本出规则草稿，见"限制"）。**注意：让 Claude 精修时，会议全文会发给模型服务，不是只留在本机，见下面"数据边界"。**

## 先看这三件事（数据、客户版、编码）
1. **数据边界**：排版脚本全程离线（源码里没有任何联网代码），但"提炼要点"这一步如果让 Claude Code 做，**它读到的会议全文会发给 Claude 的模型服务**——"文件在本机"不等于"全文只留在本机"。会议里有客户名、报价、人事、未公开财务时：先把这些替换成代号再给 Claude；或者只用方式 B（纯脚本、不接触任何模型），接受草稿质量低。你所在机构有数据规定的，以规定为准。
2. **含备注的 PPTX 不是外发版**：`<名>.pptx` 的每页备注里放着原话依据（谁说了什么），`notes.md`、`outline.json`、`report.html` 也含原话。这些是**内部核对用**。要发给客户/外部，必须走下面"客户版"步骤。
3. **编码**：推荐 UTF-8。读取失败时脚本会自动改用 GB18030（兼容 GBK）再试，并打印一行提示；两种都读不出来才会报错。转换办法见下面第 2 步。

## 从下载到出成品（推荐路线）

### 0. 下载并找到工具目录
1. 打开仓库主页 `https://github.com/cbl980712-coder/0xshimei-ai-workflows`，点绿色 **Code → Download ZIP**（或直接下载 `https://github.com/cbl980712-coder/0xshimei-ai-workflows/archive/refs/heads/main.zip`）。**这个 ZIP 是整个仓库**（约 30 MB，包含其他工具），不是单个工具包。
2. 解压后，工具在 **`0xshimei-ai-workflows-main/meeting-to-slides/`** 这一层——里面直接能看到 `README.md`、`SKILL.md`、`scripts/`、`examples/`。下面所有命令都在这一层执行。
3. 用 Finder / 资源管理器双击解压最省事。若命令行 `unzip` 报"Illegal byte sequence"，那是仓库里**其他**工具的中文文件夹名引起的，和本工具无关；只解压本工具即可：`unzip main.zip "*/meeting-to-slides/*" -d 解压目录`。
4. 仓库页面上的子目录页（`…/tree/main/meeting-to-slides`）只是浏览页，不是下载入口。

### 1. 装环境（只做一次）
需要 Python 3.8 以上。**在工具目录里**建虚拟环境（环境就在这个目录的 `.venv` 里，后面 Claude 也要用它）：

**Mac**（终端）：
```bash
cd 解压目录/0xshimei-ai-workflows-main/meeting-to-slides
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
**Windows**（PowerShell）：
```powershell
cd 解压目录\0xshimei-ai-workflows-main\meeting-to-slides
python -m venv .venv
.venv\Scripts\Activate.ps1      # 若提示脚本被禁止：Set-ExecutionPolicy -Scope Process RemoteSigned
pip install -r requirements.txt
```
**先跑这条确认环境好了**（直接指定虚拟环境里的 Python，Claude 之后也用同一个写法；Windows 用 `.venv\Scripts\python.exe`）：
```bash
.venv/bin/python scripts/make_presentation.py --selftest --out out_selftest
```
看到以 `OK` 开头的一行（如 `OK  5 页  用时 0.07s`）就行，命令结束码为 0。下面逐页列表里出现 `!! 可能溢出` 是**正常的**：内置测试文字没精修过，指标卡说明偏长，只是演示"长句会被提醒"。然后删掉 `out_selftest` 文件夹。

### 2. 放好输入
- 把会议记录存成 **UTF-8 的 `.txt` 或 `.md`**，**直接放进工具目录**（和 `README.md` 同一层），比如 `my_meeting.txt`。放别处也行，但之后给 Claude 的就是绝对路径。PDF/Word 先复制成文本。
- 编码：UTF-8 最稳。若是 GBK/GB2312 的老 txt，脚本会自动按 GB18030 读并提示"不是 UTF-8"；如果提示后字是乱码，或报"不是文本文件"，说明编码另有来源（如 UTF-16）——用记事本/文本编辑器**另存为 UTF-8**，或在 Mac 终端：`iconv -f GB18030 -t UTF-8 旧.txt > my_meeting.txt`。
- 写法不限。能识别这几种发言人写法：`张三：…` / `Alice: …` / 单独一行 `姓名, 公司 – 职位` / Markdown `## 标题`。开头写一行 `# 会议标题`、数字保留单位（`15%`、`$12 million`、`86 元`）更准。

### 3. 让 Claude Code 做（推荐）
有两种用法，**选一种**：

**用法 A：不安装，在工具目录里启动，让 Claude 读 SKILL.md。**
```bash
cd 解压目录/0xshimei-ai-workflows-main/meeting-to-slides    # 启动目录必须是这一层
claude
```
进去后对 Claude 说（原样可用）：
> 先读 SKILL.md，按它的步骤把 my_meeting.txt 做成给领导汇报的 PPT，中文。运行脚本一律用 `.venv/bin/python`（Windows 用 `.venv\Scripts\python.exe`），不要用系统的 python3。

**用法 B：安装成 Skill，在任何目录都能调用。** 把整个工具目录（含已建好的 `.venv`）复制到 `~/.claude/skills/meeting-to-slides/`，**重启** Claude Code，在放着会议记录的目录里启动，说：
> 用 meeting-to-slides，把 ./my_meeting.txt 做成给领导汇报的 PPT，中文。

此时脚本在 `~/.claude/skills/meeting-to-slides/scripts/`，Python 是 `~/.claude/skills/meeting-to-slides/.venv/bin/python`，输入文件是你当前目录里的文件（SKILL.md 已写明用绝对路径）。如果复制后 `.venv` 不能用（虚拟环境搬家会失效），在新位置重做第 1 步。

**为什么要强调虚拟环境**：你在终端 `source .venv/bin/activate` 只对那个终端窗口有效；Claude 执行命令时是新的 shell，不继承它，会用系统 Python 然后报 `No module named pptx`。所以让它直接调 `.venv/bin/python`。若真遇到这个报错，对 Claude 说"用 `.venv/bin/python` 重跑"。

Claude 会：跑草稿 → 读原文精修 `outline.json` → 生成成品，最后告诉你文件路径。**这一步里原文会发给模型，见上面"数据边界"。**

### 4. 不用 Claude：只用脚本（规则草稿）
```bash
.venv/bin/python scripts/make_presentation.py my_meeting.txt --out out --title "本周跨部门例会"
```
输入文件名带空格或中文也可以，路径要加引号。输入读不了、是空文件、是 PDF/Word、大纲 JSON 写坏了，都会给一行中文提示（不会出现 Python 堆栈）。草稿质量低，不建议直接交给领导。

**改完大纲重新出 PPT：**
```bash
.venv/bin/python scripts/make_presentation.py --outline out/my_meeting.outline.json --out out --name deck
```

### 5. 要发给客户/外部：出客户版
内部版（`deck.pptx`）每页备注里有原话依据。外发前：
1. 打开 `out/my_meeting.outline.json`，先**删掉或改写**不该给对方看的内容：内部人名/评价、"风险与分歧"页、预算与报价、未公开数字。（`notes` 字段不用管，客户版不会带。）
2. 出客户版：
```bash
.venv/bin/python scripts/make_presentation.py --outline out/my_meeting.outline.json --out out --name deck --client
```
得到 `out/deck.client.pptx`：**没有逐页备注**，作者等文档属性清空；脚本会回读核对"备注 0 条"。这个命令不会生成 notes.md / report.html。
3. **只发 `deck.client.pptx`**。不要发 `deck.pptx`、`*.notes.md`、`*.outline.json`、`*.report.html`。
4. 逐页读一遍正文再发：客户版只去掉备注，**正文里写进去的人名、数字、分歧、决定都还在**，哪些能给对方看，要你自己判断。
5. 从 PowerPoint 另存为/导出 PDF 时，勾选不含备注页（或直接发 PDF 的"幻灯片"版）。

## 输出在哪（`--out` 指定的文件夹，默认 `out/`）
| 文件 | 用途 |
|---|---|
| `<名>.pptx` | 成稿，16:9，标题放在真正的标题占位符里（PowerPoint 的大纲视图只读占位符文字；Mac / 网页版是否同样可用未验证），每页备注里有原话依据 |
| `<名>.notes.md` | 演讲提纲备忘（每页要点 + 可展开的原话） |
| `<名>.outline.json` | 大纲，可手改后重新生成（跑 `my_meeting.txt` 就得到 `my_meeting.outline.json`，名字跟输入文件走） |
| `<名>.report.html` | 逐页检查报告：重点高亮、字号、估算行数、是否可能溢出 |

**照提示改**：终端里标 `!! 可能溢出` 的那一页/那张指标卡，就是文字偏长；把对应条目缩短（指标卡 `label` 建议 ≤ 40 字），再用上面的 `--outline` 命令重新生成，该标记应当消失（用内置自测文字实测：缩短 3 张被标记的指标卡说明后，3 处 `!!` 变 0 处）。行数是估算，最终以 `report.html` / 实际打开为准。

可选：`.venv/bin/python scripts/preview_pptx.py out/deck.pptx` 生成 `deck.preview.html`，没装 PowerPoint 也能在浏览器里看版式。

## 先看例子
`examples/` 里有 4 组输入和输出：01–03 是英文公开会议文本（下表“词”数 = `wc -w` 按空白分词的结果），**04 是中文纪要**（作者为本工具包编写的虚构示例，人名机构数字均为虚构，可自由公开）：

| 目录 | 输入（公开来源） | 类型 |
|---|---|---|
| `examples/01/` | Rust 语言组 GATs 稳定化评审会纪要（GitHub 公开仓库），7122 词 | 功能评审 |
| `examples/02/` | RingCentral 2024 Q3 财报电话会讲稿（公司公开 PDF，已转文本），3530 词 | 季度复盘 |
| `examples/03/` | Rust 语言组 Return Type Notation 设计会纪要，5266 词 | 多人讨论评审 |
| `examples/04/` | 中文：社区图书馆「周末共读」十月复盘会纪要（虚构），约 860 个汉字 | 项目复盘 |

每个目录里：`input.*` 原文，`auto/` 是脚本规则草稿，`outline.json` 是精修后的大纲，`deck.pptx` 成稿（04 另有 `deck.client.pptx`，即第 5 步的客户版：无备注）。复现：
```bash
.venv/bin/python scripts/make_presentation.py --outline examples/02/outline.json --out out_demo --name deck
```

## 限制（请先看）
- **脚本自己不理解语义**：规则草稿靠关键词和数字打分，会选错句子、截断半句（例子里 `examples/*/auto/` 就是未经精修的草稿）。要交付给领导的版本，请让 Claude 按 SKILL.md 精修大纲，或你自己改 `outline.json`。
- 规则内置英文和少量中文关键词；中文有 `examples/04/` 一份完整走过推荐路线的虚构纪要，外加几个很短的自编冒烟测试，没有在大量真实中文会议上系统验证。
- Windows 命令按常规写法给出，**作者没在 Windows 上实测**；Mac 命令已在干净副本里逐条跑通。
- 版式在浏览器预览和脚本的行数估算下检查过；**没有在真实 PowerPoint / Keynote 里逐页打开过**（作者尝试用 Mac 上的 Keynote 打开，当次环境没能打开文档，核对只靠 `preview_pptx.py` 的浏览器预览和 python-pptx 回读；请你第一次用时自己翻一遍），字体建议安装 Calibri / 微软雅黑（没有时会自动替换，换行可能略有不同）。
- 输入太短（几行）会少于 5 页（自测：同一份 7 行短会议，不加 `--title` 出 4 页，加 `--title "…"` 出 5 页（多一页“背景与议题”）；两次输入完全相同，只差这个参数。只有“关键事实”页能识别出数字，漏了不少要点），脚本会提示；太长（几万行）也能跑完（自测 3 万行约 1 秒），但草稿质量更差，建议先按议题拆开。
- 发言人只出现 1 次时可能认不出（例如只说了一次的“陈静：”）；英文/中文混写能跑，但规则草稿会把混合句当普通句子，最好让 Claude 精修。
- 编码：推荐 UTF-8；UTF-8 读不了会自动改用 GB18030（兼容 GBK）并提示；两种都不行（如 UTF-16、二进制）会报错，处理办法见第 2 步。PDF/Word 要先转文本。
- 页数、每页条数是固定的商务模板（深蓝 + 橙色强调）；换配色改 `make_presentation.py` 顶部的 `NAVY / ACCENT`。
- 不做语音转写；语音要先用别的工具转成文字。
- **耗时口径**：脚本耗时是在作者 Mac（Python 3.9）上多次秒表所得，约 0.1 秒级，机器不同会不同；**Claude 精修大纲那一步没有计时，也没有“比手工省多少”的实测，不要引用这类比例。**
- 费用：脚本部分为 0 元；用 Claude 精修要消耗你自己的 Claude 额度/API，没有实测，具体看你的套餐和当时价格。
- 这套工具把“规则草稿”与“精修稿”分开：只有精修稿适合给领导看，它不是 PowerPoint 设计师或专业速记员的平替。
