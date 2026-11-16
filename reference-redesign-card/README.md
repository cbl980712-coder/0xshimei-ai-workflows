# 参考图改版指令卡

**解决什么**：参考图找到了，但说不清它哪里好，也说不清自己的页面到底该改哪儿。
**做什么**：你给「自己的页面 + 页面目标 + 参考页」并圈出想借鉴的位置 → 工具把参考页的留白、标题层级、按钮样式**量成数字**，对应到你页面的具体区域，标明哪些地方不动 → 输出按优先级排的改版清单（每条：改哪里、怎么改、怎么看改对了），并在浏览器里临时套上样式**自动验收**。

不用登录、不调付费 API、不装任何 npm 包。

## 一、三步上手

### 第 1 步：装什么

| 需要 | Mac | Windows |
|---|---|---|
| Node.js **22 或更新** | 去 nodejs.org 下 LTS 安装包，或 `brew install node` | 去 nodejs.org 下 LTS 安装包，或 `winget install OpenJS.NodeJS.LTS` |
| Chrome 或 Edge（任一个） | 一般已有 | Edge 系统自带 |
| 一个能看图、能写文件的 AI 助手（推荐 Claude Code，让它按 `SKILL.md` 干活） | 见下 | 见下 |

AI 助手只负责「看图 + 写清单」那一步。没有的话也能用：自己照 `templates/checklist.template.json` 手写清单，其余步骤都是脚本。

把 `kit/` 整个文件夹放到任意位置，终端进入 `kit/`。Claude Code 用户：`SKILL.md` 复制到 `~/.claude/skills/reference-redesign-card/SKILL.md`（Windows：`%USERPROFILE%\.claude\skills\...`），scripts、templates 文件夹一起放进去；或者不安装，直接对 Claude Code 说“按 kit/SKILL.md 做”。

### 先确认环境（必跑）

```
node scripts/doctor.mjs
```

看到四个 ✅ 和“环境 OK”才继续。常见失败：
- `Node 需要 22 或更新` → 升级 Node（`node -v` 查版本）。
- `没找到 Chrome/Edge` → 装一个，或设环境变量指向它：Mac/Linux `export CHROME_PATH="/path/to/chrome"`；Windows PowerShell `$env:CHROME_PATH="C:\path\to\chrome.exe"`。

### 先跑例子看效果（需要联网，自测实际 33 秒）

```
node scripts/finish.mjs examples/01/output
```

会重新打开 htmx.org 量一遍，输出 `指令卡.html`、`改版清单.md`、`改后验收清单.md`。用浏览器打开 `examples/01/output/指令卡.html` 就是成品的样子。例子 02、03、04 同理（04 是自测时新编的输入，含一次“没过→照提示改→通过”）。

### 第 2 步：放你的输入

在 `kit/` 里新建 `work/我的页面/` 文件夹，准备：

1. 你的页面网址（本地 html 文件路径、或截图 png/jpg 也行）
2. 参考页网址（或截图）
3. 一句话页面目标：谁来、几秒内要做成什么。例：`第一次来的开发者 10 秒内知道它是什么、点哪里开始用`
4. 想借鉴什么：留白 / 标题层级 / 按钮样式

圈选文件（可选，建议写）`我的圈.json` / `参考圈.json`，格式见 `templates/marks.example.json`：

```json
[{"label":"1 标题","selector":"h1"},
 {"label":"2 留白","box":[60,73,900,195]}]
```
`selector` 是 CSS 选择器（浏览器里右键“检查”可得）；`box` 是 `[x, y, 宽, 高]`，整页坐标，截图输入时只能用 box。不知道选择器？先不写，第一次跑完看 `对比.md` 里的标题、按钮表，里面有每个元素的选择器，再补上重跑。

### 第 3 步：跑

```
node scripts/run.mjs --own https://你的页面/ --ref https://参考页/ --out work/我的页面 --own-marks work/我的页面/我的圈.json --ref-marks work/我的页面/参考圈.json
```
自测实际 52～53 秒（网速、页面大小不同会有出入，很长的页面可能到 1 分钟以上），得到两张带编号红圈的截图（`ref-marked-top.png`、`mine-marked-top.png`）和 `对比.md`（量出来的字号、间距、按钮并排）。

然后对 AI 助手说：

> 按 kit/SKILL.md，用 work/我的页面 里的材料，帮我出参考图改版指令卡。页面目标：……；想借鉴：……

它会写出 `work/我的页面/checklist.json` 和 `patch.css`，再跑：

```
node scripts/finish.mjs work/我的页面
```
自测实际 33 秒。全部自动验收；没过的项会直接打印“目标、改后值、还差多少”，改 `patch.css` 再跑一遍即可。

## 二、输出在哪（都在你的 `--out` 目录里）

| 文件 | 是什么 |
|---|---|
| `指令卡.html` | 成品：红圈对照图 + 借鉴对应表 + 不动清单 + 按优先级的改版清单（带实测达标标记） |
| `改版清单.md` | 同样内容的纯文本，可贴给设计师或别的 AI |
| `改后验收清单.md` | 每条“怎么看改对了”的改前/改后实测值，通过/没过 |
| `patch.css` | 清单里的样式合集，可直接在浏览器控制台或你的样式表里试 |
| `对比.md` | 参考页和你的页面量出来的数字 |
| `mine-before-top.png` / `mine-after-top.png` | 改前、套样式后的首屏（临时预览，**没有改你的线上网站**） |

## 三、限制（先看这里，省得踩坑）

- **网页会变**：例子里的数字是 2026-11 量的；你重跑例子 01 会重新打开线上的 htmx.org、linear.app，页面改版后数字可能不同（`finish.mjs` 重跑例子只是复验原来的 patch，不一定还全过）。
- **需要联网**（本地 html 文件和截图除外）。

- **只量桌面宽度（默认 1440×900 的首屏和整页）**，没量手机宽度；可加 `--width 390` 单独跑一遍手机宽。
- **量出来的是浏览器算的样式，判断“该不该借”是 AI 的判断**。清单里的数字是事实，“为什么好”是推断。
- **验收只能验“数字有没有改到位”**，好不好看要你自己看 `mine-after-top.png`（例子 02 里就出现过数字全过、画面居中被改歪的情况，见 REPORT）。
- 参考页或你的页面是**图片**时没有量测数据，只能看图，所有数字都是目测。
- 需要登录才能看到的页面抓不到；有强反爬或要求先点同意弹窗的页面，截图里可能只有弹窗。页面有动态广告位时，每次打开高度可能不同（例子 03 就有一个 90px 的广告位），验收因此每次用全新浏览器量。
- 滚动动画、懒加载内容靠“自动滚一遍”触发，最长整页截图限 7000px 高。
- 站点原样式优先级高时，补丁要写得更“具体”才压得过（见 SKILL.md 第 4 步）。
- 这个工具只改样式预览，不改你网站的源码；“彻底改法”（要加 HTML 元素）清单里会单独写，但不验收。
- 例子里的“我的页面”其实是别人的公开网站（htmx、Django、JSONLint），是拿来当“自己的页面”演示的，里面的改版建议不代表这些站点真的该这么改。

## 出错时看这里

| 提示 | 怎么办 |
|---|---|
| `找不到文件` / `找不到圈选文件` | 路径写错；路径里有空格或中文要用英文引号括起来：`--own "work/我的 页面/a.html"` |
| `…不是合法的 JSON` / `是空文件` | 圈选文件或 checklist.json 写错：检查逗号、引号（要英文 `"`），格式照 `templates/` 里的文件 |
| `圈选文件…格式不对` | 每一项要有 `selector` 或 `box`（四个数字） |
| `打不开这个页面` | 网址拼错、没网，或站点拒绝无头浏览器 |
| `页面打开了但里面几乎没有内容` | 空白页、要登录或被反爬拦住；改给截图（png/jpg） |
| `⚠️ 未找到 xxx` | 圈选的选择器在页面上选不中，红圈没画；去 `对比.md` 的标题、按钮表里抄选择器 |
| `首屏没有H1` | 不是错误：这个页面首屏里没有 H1 标签（例如用图片当标题），对比表里对应格子是 `—` |
| 验收 `❌` | 看打印出的“还差多少”，改 `patch.css`（或选择器）后重跑 `finish.mjs` |

## 四、文件说明

```
SKILL.md                      给 Claude Code 的工作流（核心）
scripts/doctor.mjs            环境自检
scripts/run.mjs               第 1 步：量两个页面 + 对比表
scripts/probe.mjs             单个页面的量测与截图（run 调用它）
scripts/compare.mjs           对比表生成
scripts/verify.mjs            套 patch.css 验收
scripts/render.mjs            清单 → md + html
scripts/finish.mjs            第 3 步：验收 + 出成品
scripts/lib.mjs               共用（找浏览器、控制浏览器）
templates/                    checklist 模板、圈选示例
examples/01..04/              四个真实例子：input/ 输入，output/ 真实输出
```
