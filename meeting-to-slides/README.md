# meeting-to-slides：会议记录 → 汇报 PPT

把会议速记 / 转写稿，整理成 5–7 页商务版式 PPT，外加演讲提纲备忘。排版脚本离线运行，**不登录、不调用任何付费 API**；"提炼要点"这一步由 Claude Code 按 `SKILL.md` 做（也可以不用 Claude，只用脚本出规则草稿，见"限制"）。

## 三步上手

### 1. 装什么
需要 Python 3.8 以上。

**Mac**（终端）：
```bash
cd meeting-to-slides            # 就是这个 kit 文件夹（从 GitHub 下载后文件夹可能叫别的名字，进到有 README.md 和 scripts/ 的那一层即可）
python3 -m venv .venv && source .venv/bin/activate
pip install python-pptx        # 或 pip install -r requirements.txt
```
**Windows**（PowerShell）：
```powershell
cd meeting-to-slides
python -m venv .venv
.venv\Scripts\Activate.ps1      # 若提示脚本被禁止：Set-ExecutionPolicy -Scope Process RemoteSigned
pip install python-pptx
```
**先跑这条确认环境好了**（Windows 把 `python3` 换成 `python`）：
```bash
python3 scripts/make_presentation.py --selftest --out out_selftest
```
看到以 `OK` 开头的一行（如 `OK  5 页  用时 0.07s`；用时因机器而异，第一次运行可能要几秒）就行，命令结束码为 0。
下面逐页列表里出现 `!! 可能溢出` 是**正常的**：内置测试文字没精修过，指标卡说明偏长；这只是演示“长句会被提醒”，不代表环境有问题。然后删掉 `out_selftest` 文件夹。

### 2. 怎么放输入
- 把会议记录存成 **UTF-8 的 `.txt` 或 `.md`**，放哪都行（比如 `my_meeting.txt`）。PDF/Word 先复制成文本。
- 写法不限。能识别这几种发言人写法：`张三：…` / `Alice: …` / 单独一行 `姓名, 公司 – 职位` / Markdown `## 标题`。
- 想让要点更准：开头写一行 `# 会议标题`，数字保留单位（`15%`、`$12 million`、`86 元`）。

### 3. 怎么跑
**方式 A（推荐）：在 Claude Code 里用 Skill。** 把整个 kit 文件夹放进项目（或 `~/.claude/skills/meeting-to-slides/`），对 Claude 说：
> 用 meeting-to-slides，把 my_meeting.txt 做成给领导汇报的 PPT，中文。

Claude 会跑草稿 → 读原文精修 `outline.json` → 生成成品。

**方式 B：只用脚本（规则草稿，不需要 Claude）：**
```bash
python3 scripts/make_presentation.py my_meeting.txt --out out --title "本周跨部门例会"
```
输入文件名带空格或中文也可以，路径要加引号：`python3 scripts/make_presentation.py "我的 会议 记录.txt" --out out`。输入读不了、是空文件、是 PDF/Word、大纲 JSON 写坏了，都会给一行中文提示（不会出现 Python 堆栈）。

**改完大纲重新出 PPT：**
```bash
python3 scripts/make_presentation.py --outline out/my_meeting.outline.json --out out --name deck
```

## 输出在哪（`--out` 指定的文件夹，默认 `out/`）
| 文件 | 用途 |
|---|---|
| `<名>.pptx` | 成稿，16:9，标题放在真正的标题占位符里（PowerPoint 的大纲视图只读占位符文字；Mac / 网页版是否同样可用未验证），每页备注里有原话依据 |
| `<名>.notes.md` | 演讲提纲备忘（每页要点 + 可展开的原话） |
| `<名>.outline.json` | 大纲，可手改后重新生成（跑 `my_meeting.txt` 就得到 `my_meeting.outline.json`，名字跟输入文件走） |
| `<名>.report.html` | 逐页检查报告：重点高亮、字号、估算行数、是否可能溢出 |

**照提示改**：终端里标 `!! 可能溢出` 的那一页/那张指标卡，就是文字偏长；把对应条目缩短（指标卡 `label` 建议 ≤ 40 字），再用上面的 `--outline` 命令重新生成，该标记应当消失（用内置自测文字实测：缩短 3 张被标记的指标卡说明后，3 处 `!!` 变 0 处）。行数是估算，最终以 `report.html` / 实际打开为准。

可选：`python3 scripts/preview_pptx.py out/deck.pptx` 生成 `deck.preview.html`，没装 PowerPoint 也能在浏览器里看版式。

## 先看例子
`examples/` 里有 3 组真实输入和真实输出，都是公开的会议文本（下表“词”数 = `wc -w` 按空白分词的结果）：

| 目录 | 输入（公开来源） | 类型 |
|---|---|---|
| `examples/01/` | Rust 语言组 GATs 稳定化评审会纪要（GitHub 公开仓库），7122 词 | 功能评审 |
| `examples/02/` | RingCentral 2024 Q3 财报电话会讲稿（公司公开 PDF，已转文本），3530 词 | 季度复盘 |
| `examples/03/` | Rust 语言组 Return Type Notation 设计会纪要，5266 词 | 多人讨论评审 |

每个目录里：`input.*` 原文，`auto/` 是脚本规则草稿，`outline.json` 是精修后的大纲，`deck.pptx` 成稿。复现：
```bash
python3 scripts/make_presentation.py --outline examples/02/outline.json --out out_demo --name deck
```

## 限制（请先看）
- **脚本自己不理解语义**：规则草稿靠关键词和数字打分，会选错句子、截断半句（例子里 `examples/*/auto/` 就是未经精修的草稿）。要交付给领导的版本，请让 Claude 按 SKILL.md 精修大纲，或你自己改 `outline.json`。
- 规则内置英文和少量中文关键词；中文只做过一个很短的自编冒烟测试，没有在真实中文会议上系统验证。
- Windows 命令按常规写法给出，**作者没在 Windows 上实测**；Mac 命令已在干净副本里逐条跑通。
- 版式在浏览器预览和脚本的行数估算下检查过；**没有在真实 PowerPoint / Keynote 里逐页打开过**，字体建议安装 Calibri / 微软雅黑（没有时会自动替换，换行可能略有不同）。
- 输入太短（几行）会少于 5 页（自测：7 行的短会议只出 4 页，只有“关键事实”页能识别出数字，漏了不少要点），脚本会提示；太长（几万行）也能跑完（自测 3 万行约 1 秒），但草稿质量更差，建议先按议题拆开。
- 发言人只出现 1 次时可能认不出（例如只说了一次的“陈静：”）；英文/中文混写能跑，但规则草稿会把混合句当普通句子，最好让 Claude 精修。
- 只支持 UTF-8 文本，GB18030/GBK 的 txt 会自动尝试并提示；PDF/Word 要先转文本。
- 页数、每页条数是固定的商务模板（深蓝 + 橙色强调）；换配色改 `make_presentation.py` 顶部的 `NAVY / ACCENT`。
- 不做语音转写；语音要先用别的工具转成文字。
- **耗时口径**：脚本耗时是在作者 Mac（Python 3.9）上多次秒表所得，约 0.1 秒级，机器不同会不同；**Claude 精修大纲那一步没有计时，也没有“比手工省多少”的实测，不要引用这类比例。**
- 费用：脚本部分为 0 元；用 Claude 精修要消耗你自己的 Claude 额度/API，没有实测，具体看你的套餐和当时价格。
- 这套工具把“规则草稿”与“精修稿”分开：只有精修稿适合给领导看，它不是 PowerPoint 设计师或专业速记员的平替。
