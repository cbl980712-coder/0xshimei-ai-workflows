---
name: meeting-to-slides
description: 把杂乱的会议速记、语音转写稿或公开会议纪要，整理成 5-7 页向领导汇报的 .pptx（商务版式、重点高亮），并附演讲提纲备忘。用户说"把这份会议记录做成汇报 PPT""会后给领导出一套精炼幻灯片""转写稿提炼要点做 PPT"时使用。
---

# 会议文本 → 汇报 PPT（meeting-to-slides）

脚本 `scripts/make_presentation.py` 负责排版（python-pptx，离线、不调 API）；**语义判断由你（Claude）做**：脚本只给一份规则提取的草稿，质量不够直接交付，必须按下面第 3 步精修。

## 第 0 步：定下 Python 和路径（每次会话先做）
**不要直接用系统的 `python`/`python3`**（装依赖的是工具目录里的虚拟环境，Claude 的 shell 不继承用户终端里的 activate）。按顺序找：
1. 工具目录 = 本 SKILL.md 所在目录（用户在该目录启动 Claude，就是当前目录；若装成 Skill，是 `~/.claude/skills/meeting-to-slides/`）。
2. 解释器 `PY` = `<工具目录>/.venv/bin/python`（Windows：`<工具目录>\.venv\Scripts\python.exe`）。不存在就告诉用户按 README 第 1 步建环境，不要自己装到系统 Python。
3. 脚本 = `<工具目录>/scripts/make_presentation.py`；输入文件用**绝对路径**（用户说的 `my_meeting.txt` 先在当前目录找，找不到就问用户）；`--out` 也用用户当前目录下的 `out/`，不要写进 Skill 安装目录。
之后文中的 `python scripts/...` 都指 `$PY <工具目录>/scripts/...`。

首次确认环境：
```bash
$PY scripts/make_presentation.py --selftest --out out_selftest
```
看到以 `OK` 开头的一行即可，然后删掉 `out_selftest/`。报 `No module named pptx` 说明用错了解释器，换成上面的 `PY`。

> 报错说明：脚本遇到找不到文件/空文件/PDF/JSON 写坏等情况会打印一行“出错了：…”并以非 0 退出；把这行原样转告用户并按提示处理，不要自己猜着改原文。
> 编码：UTF-8 读不了会改按 GB18030 读并提示——这只说明能解码，不代表认对了编码；看到提示就抽看输出里的中文是否正常，乱码就让用户另存为 UTF-8，不要自己转码覆盖原文。Big5/Shift-JIS 等会被读成乱码而不报错；UTF-16/二进制只在带 BOM 或含空字节时明确拒绝，不要对用户承诺“一定会报错”。

## 数据边界（开工前先对用户说一句）
你读原文、写大纲，意味着会议全文已进入模型服务，不是只在本机。用户说内容敏感时，先问是否已替换成代号；不愿意就改走"只用脚本出草稿"，不要读全文。

## 第 1 步：放好输入
- 输入是 `.txt` / `.md` 纯文本。PDF、Word、字幕先转成文本再用（不要手改原文，原文是核对依据）。
- 发言人格式不限：`张三：…`、`Alice: …`、`姓名, 公司 – 职位` 单独一行、Markdown 标题都认。

## 第 2 步：跑出草稿
```bash
python scripts/make_presentation.py 会议.txt --out out --title "汇报标题"
```
得到 `out/<输入文件名>.outline.json`（草稿大纲，如输入 `会议.txt` 就是 `out/会议.outline.json`）和一份草稿 pptx。`--lang en` 让页面标题用英文。

## 第 3 步：精修大纲（你来做，这是核心）
1. **完整读一遍原文**，再读草稿 `outline.json`。
2. 重写（或改）`outline.json`，保持页数 **5–7 页**，推荐结构：
   封面 → 一句话结论与背景 → 核心指标 → 各方观点 → 风险与分歧 → 结论/决策 → 下一步与待办。
   没有数字就把"核心指标"换成"关键事实"（type 用 `bullets`）；没有待办就不做第 7 页。
3. 写法规矩：
   - 每页 ≤ 4 条 bullet；每条一句话，中文 ≤ 40 字 / 英文 ≤ 90 字符；开头给结论，不写"讨论了…"。
   - **每条的 `strong` 只放 1–2 个重点片段**（数字、结论词、负责人），必须是 `text` 里**原样出现**的子串，否则会被忽略并提示。
   - 指标卡：`value` ≤ 8 个字符（如 `$583M`、`+51%`），`label` ≤ 40 字，3–6 张。
   - 所有数字、人名、日期必须来自原文；原文没有的不要补。原文没写最终决定就写"纪要未记录最终结论"。
   - 输出语言跟随用户（原文是英文、用户要中文就翻译，保留专有名词和原文数字）。
   - `notes` 放原话依据或讲述提示，会进入 PPT 备注和 `notes.md`。
4. outline.json 结构：
```json
{"title": "…", "lang": "zh", "source": "来源说明", "words": 3530,
 "slides": [
  {"type": "cover", "title": "…", "subtitle": "发言人 / 来源", "notes": []},
  {"type": "bullets", "title": "页标题",
   "bullets": [{"text": "一句话要点 +56%", "strong": ["+56%"]}], "notes": ["原话依据"]},
  {"type": "metrics", "title": "核心指标",
   "metrics": [{"value": "$583M", "label": "订阅收入，同比 +10%"}],
   "takeaway": "一句话解读", "notes": []}
 ]}
```

## 第 4 步：生成成品
```bash
python scripts/make_presentation.py --outline out/会议.outline.json --out out --name deck
python scripts/preview_pptx.py out/deck.pptx        # 可选：没装 PowerPoint 也能看版式
```
得到：`deck.pptx`（成稿）、`deck.notes.md`（演讲提纲备忘）、`deck.report.html`（逐页检查报告）。

## 第 5 步：检查（不通过就回第 3 步改）
- 终端逐页打印字号和估算行数；出现 `!! 可能溢出` 就缩短那页文字。
- 打开 `deck.preview.html` 或 PowerPoint，逐页看：标题是否一行、有没有文字挤出框、重点颜色是否只出现在关键处。
- 回原文抽查 3 个数字，确认和幻灯片一致。
- 5 ≤ 页数 ≤ 7；封面标题不含文件名。

## 客户版（用户说要发给客户/外部时）
内部 `deck.pptx` 的备注里是原话依据，**不能外发**。先和用户确认哪些页/数字不能给对方看，改 `outline.json` 后：
```bash
$PY scripts/make_presentation.py --outline out/会议.outline.json --out out --name deck --client
```
得到 `out/deck.client.pptx`（无备注页/备注母版/批注、核心文档属性与 app.xml 的 Company/Manager 为空，脚本导出后逐项回读，不空就中止）。创建/修改时间是模板固定日期，未清；别的元数据没验证过，不要向用户多承诺。告诉用户：只发这一个文件；正文里的人名、数字、分歧仍在，需要他们逐页审。

## 交付
告诉用户：成稿路径、提纲备忘路径、哪些地方是你推断的、哪些原文没写；提醒内部版含原话备注，外发请用客户版。
