# 参考图改版指令卡

**解决什么**：参考图找到了，但说不清它哪里好，也说不清自己的页面到底该改哪儿。

**谁做什么**（先看清这个分工，别把脚本当成会“看懂设计”的东西）：

| 环节 | 谁来做 | 产出 |
|---|---|---|
| 抓图、量尺寸、画红圈、生成对比表 | **脚本**（`run.mjs`） | 两张带编号红圈的截图 + `对比.md`（字号、间距、按钮样式并排的数字） |
| 判断参考页哪里好、对应到你页面的哪个区域、哪些地方不动、该怎么改 | **AI 助手或你自己** | `checklist.json`（改版清单）和 `patch.css`（对应的样式） |
| 把 `patch.css` 临时套到你的页面上，重新量**清单里配置过的数值项**，生成清单和指令卡 | **脚本**（`finish.mjs`） | `改后验收清单.md`、`改版清单.md`、`指令卡.html`、改前改后截图 |

脚本只负责“量”和“检查你写下的数字”；“位置对应”和“怎么改”是 AI 或人写的判断。`finish.mjs` 只会检查你在 `checklist.json` 的 `checks` 里写过的数值项，没写的它不会管，改得好不好看也要你自己看改后截图。

不用登录、不调付费 API、不装任何 npm 包。

## 一、三步上手

### 第 1 步：装什么

主流程是 **Mac**（作者在 Mac 上跑通的）。Windows 和 Edge 的路线**没有在 Windows 机器上实际运行过**，下表标了出来。

| 需要 | Mac（已跑通） | Windows（未实机验证） |
|---|---|---|
| Node.js **22 或更新** | 去 nodejs.org 下 LTS 安装包，或 `brew install node` | 去 nodejs.org 下 LTS 安装包，或在 PowerShell 里：`winget install --id OpenJS.NodeJS.LTS --exact`（包名 `OpenJS.NodeJS.LTS` 已对照 Node.js 官网的包管理器页面和 winget-pkgs 仓库确认存在，但没在 Windows 上执行过；装完要重开终端，再用 `node -v` 看版本） |
| Chrome（或 Edge） | 装 Chrome 最稳；Mac 上用的是 Chrome | Chrome 或 Edge 任一个。脚本会找 Edge 的默认安装路径，但没在 Windows 上试过；找不到就设 `CHROME_PATH`（见下） |
| 一个能看图、能写文件的 AI 助手（推荐 Claude Code） | 见下 | 见下 |

**没有 AI 助手也能用**：见「第 4 步」后面的“没有 AI 助手的最小例子”。

把 `kit/` 整个文件夹放到任意位置，终端 `cd` 进 `kit/`，**之后所有命令都在 `kit/` 里执行**。用 Claude Code 的话，就在这个终端里启动它（`claude`），它的工作目录就是 `kit/`，会读当前目录的 `SKILL.md`。

### 先确认环境（必跑）

```
node scripts/doctor.mjs
```

看到四个 ✅ 和“环境 OK”才继续。常见失败：
- `Node 需要 22 或更新` → 升级 Node（`node -v` 查版本）。
- `没找到 Chrome/Edge` → 装一个，或设环境变量指向它：Mac/Linux `export CHROME_PATH="/path/to/chrome"`；Windows PowerShell `$env:CHROME_PATH="C:\path\to\chrome.exe"`。

### 先看效果：两条路，别混

**路线 A：只想看成品（不联网、不跑任何命令）**

直接用浏览器打开随包提供的 `examples/01/output/指令卡.html`（Mac：`open examples/01/output/指令卡.html`；Windows：`start examples\01\output\指令卡.html`）。里面是红圈对照图、借鉴对应表、不动清单、按优先级的改版清单，以及改前改后截图。例子 02、03、04 同理。

**路线 B：想复验旧补丁（需要联网，约 33 秒）**

```
cp -R examples/01/output work/复验01
node scripts/finish.mjs work/复验01
```
（Windows PowerShell：`Copy-Item -Recurse examples\01\output work\复验01`。先复制一份再跑，免得覆盖随包的成品。）

这条命令**只做这几件事**：把 `checklist.json` 里的 `own_url`（这里是 htmx.org）**联网打开两次**——一次不套补丁、一次临时套上 `patch.css`——量清单里的数值项，然后重新生成 `改后验收清单.md`、`改版清单.md`、`指令卡.html` 和改前改后截图。

它**不会**重新打开参考页（Linear），也**不会**重新生成 `对比.md` 和红圈对照图（这些沿用复制过来的旧文件）。所以别以为这条命令把整组对照重做了一遍；整组重做要走下面的「第 3 步」。如果 htmx.org 改版了，有些项可能不再通过，那是页面变了，不是工具坏了。

### 第 2 步：放你的输入

在 `kit/` 里新建 `work/我的页面/` 文件夹（例子用 `work/01/`），准备：

1. 你的页面网址（本地 html 文件路径、或截图 png/jpg 也行，截图的限制见下面「截图模式」）
2. 参考页网址（或截图）
3. 一句话页面目标：谁来、几秒内要做成什么。例：`第一次来的开发者 10 秒内知道它是什么、点哪里开始用`
4. 想借鉴什么：留白 / 标题层级 / 按钮样式

圈选文件（可选，建议写）：`我的圈.json`（圈你自己页面上的位置）和 `参考圈.json`（圈参考页上想借鉴的位置）。格式：

```json
[{"label":"1 标题","selector":"h1"},
 {"label":"2 留白","box":[60,73,900,195]}]
```
`selector` 是 CSS 选择器（浏览器里右键“检查”可得）；`box` 是 `[x, y, 宽, 高]`，整页坐标。不知道选择器？先不写，第一次跑完看 `对比.md` 里的标题、按钮表，里面有每个元素的选择器，再补上重跑。

### 第 3 步：跑（量两个页面）

下面是一组**能直接复制的 htmx（我的页面）／Linear（参考页）命令**，都在 `kit/` 里执行。

**① 首次运行：不带圈选参数**

```
node scripts/run.mjs --own https://htmx.org/ --ref https://linear.app/ --out work/01
```
约 52 秒。得到 `work/01/` 里的截图和 `对比.md`。打开 `对比.md` 的标题表、按钮表，里面有每个元素的选择器。

**② 保存两份圈选文件**（已填好，路径必须是下面这两个）

`work/01/我的圈.json`（htmx，我的页面）：
```json
[{"label":"1 标题","selector":".dark-hero .main sub i"},
 {"label":"2 留白","selector":".dark-hero"},
 {"label":"3 按钮","selector":".top-nav a[href='/docs/']"},
 {"label":"4 新闻框","selector":"main.c.content .alert"}]
```

`work/01/参考圈.json`（Linear，参考页）：
```json
[{"label":"1 标题","selector":"h1"},
 {"label":"2 留白","box":[60,73,900,195]},
 {"label":"3 按钮","selector":"header a[href='/signup'], nav a[href*='signup']"}]
```
懒得手抄就直接复制随包的同内容文件（Mac/Linux）：
```
cp examples/01/input/mine-marks.json work/01/我的圈.json
cp examples/01/input/ref-marks.json work/01/参考圈.json
```
（Windows PowerShell：`Copy-Item examples\01\input\mine-marks.json work\01\我的圈.json`，另一份同理。）

**③ 完整重跑（带圈）**

```
node scripts/run.mjs --own https://htmx.org/ --ref https://linear.app/ --out work/01 --own-marks work/01/我的圈.json --ref-marks work/01/参考圈.json
```
得到两张带编号红圈的截图（`ref-marked-top.png`、`mine-marked-top.png`）和 `对比.md`（量出来的字号、间距、按钮并排）。网速、页面大小不同会有出入，很长的页面可能到 1 分钟以上。

**换成你自己的项目时**，把网址、输出目录和两个圈选文件路径**全都加上英文双引号**（路径里有空格或中文时必须加，没有也建议加）：

```
node scripts/run.mjs --own "https://你的页面/" --ref "https://参考页/" --out "work/我的页面" --own-marks "work/我的页面/我的圈.json" --ref-marks "work/我的页面/参考圈.json"
```
网址里带 `&`、`?` 的，不加引号终端会把它截断，所以网址更要加引号。

### 第 4 步：让 AI 写清单，再验收

在 `kit/` 里启动 Claude Code（`claude`），然后对它说（网址和目标换成你的）：

> 按当前目录的 SKILL.md，用 work/01 里的材料，帮我出参考图改版指令卡。页面目标：第一次来的开发者 10 秒内看懂 htmx 是什么、该点哪里开始用；想借鉴：标题层级、按钮样式、留白。请把 checklist.json 和 patch.css 写到 work/01/ 里。

自己的项目：把 `work/01` 换成 `work/我的页面`，AI 写出的文件就在 `work/我的页面/checklist.json` 和 `work/我的页面/patch.css`。示例的成品清单可以对照看：`examples/01/output/checklist.json`、`examples/01/output/patch.css`。

然后跑：

```
node scripts/finish.mjs work/01
```
自己的项目就是 `node scripts/finish.mjs "work/我的页面"`。约 33 秒。它会逐项检查 `checklist.json` 里配置的数值项；没过的项会直接打印“目标、改后值、还差多少”，改 `patch.css` 再跑一遍即可。数值项全过以后，还要自己对着 `mine-after-top.png` 看一眼。

### 没有 AI 助手的最小例子

下面手写一条，从“选一项”走到“跑出验收”，一共 4 步，也是在 `kit/` 里执行：

1. **从 `对比.md` 选一项。** 打开 `examples/01/output/对比.md`：参考页（Linear）的章节标题 H2 是 48px，我的页（htmx）的章节标题 H2 只有 24px。就选“章节标题偏小”这一项。（你自己的项目：对着你自己的 `work/我的页面/对比.md` 选。）
2. **填 `checklist.json`。** 复制随包的最小清单，它已经填好了这一项（`borrow` 一条、`keep` 两条、`items` 一条，`checks` 要求 `main.c.content > h2` 的 `fontSize >= 32`）：
   ```
   mkdir -p work/最小例子
   cp templates/checklist.minimal.json work/最小例子/checklist.json
   ```
   （Windows PowerShell：`New-Item -ItemType Directory -Force work\最小例子`，`Copy-Item templates\checklist.minimal.json work\最小例子\checklist.json`。）换成自己的项目时，要改的是 `own_url`、`goal`、`borrow`、`keep`，以及 `items` 里的 `where`、`change`、`css`、`checks`（`selector` 填 `对比.md` 里抄来的选择器，`value` 填你定的目标数字）。其余字段的含义见 `templates/checklist.template.json`。
3. **写对应的 `patch.css`。** 同样复制现成的（内容只有一行 `main.c.content > h2 { font-size: 32px; }`）：
   ```
   cp templates/patch.minimal.css work/最小例子/patch.css
   ```
4. **运行：**
   ```
   node scripts/finish.mjs work/最小例子
   ```
   预期看到“验收：1/1 通过”，并生成 `work/最小例子/改后验收清单.md`、`改版清单.md`、`指令卡.html`。这个最小例子没有红圈图（没跑 `run.mjs` 圈选），所以 `指令卡.html` 里只有文字（改前改后截图在 `改后验收清单.md` 和同目录的 png 里）。

## 二、截图模式：哪一侧传图片，哪一侧就只能目测

图片没有网页样式可量，所以**哪一侧传的是图片，那一侧就只能用 `box` 圈选，不能量浏览器样式**。三种情况：

| 你的输入 | 能做 | 不能做 |
|---|---|---|
| **参考页是截图，自己的页面能打开**（网址或本地 html） | 参考页用 `box` 圈选；自己的页面照常量（有 `mine.json`）；自己的页面能套 `patch.css`，`finish.mjs` 能完整验收、出改后截图。参考页的尺寸是**目测**，写进清单时要标“目测” | 不会自动生成 `对比.md`（它需要两边都有量测数据）；参考页的数字没有实测值，阈值只能写你自己定的目标 |
| **自己的页面只有截图**（参考页是网址或截图都一样） | 自己的页面用 `box` 圈选，出带红圈的对照截图；`checklist.json` 的 `own_url` 写截图路径、`checks` 留空或不写，`finish.mjs` 会跳过验收，**只生成 `改版清单.md` 和 `指令卡.html`**（里面有红圈对照图、借鉴对应表、不动清单、改法清单） | **不能对图片套 CSS，不会有 `mine-after-top.png`，也没有“改后实测值”**；清单里的 `css` 只是文字建议，没有被验证过 |
| 两边都是截图 | 同上一行：只出红圈图、清单和指令卡 | 同上，所有数字都是目测 |

截图的 `box` 坐标是图片像素（图片宽度超过 1440 会被缩到 1440 宽，坐标按缩后的算）。

## 三、输出在哪（都在你的 `--out` 目录里）

| 文件 | 是什么 |
|---|---|
| `指令卡.html` | 给人看的成品：红圈对照图 + 借鉴对应表 + 不动清单 + 按优先级的改版清单（跑过验收的带“实测达标”标记）+ 改前改后截图 |
| `改版清单.md` | 同样的清单内容，纯文本，可贴给设计师或别的 AI |
| `改后验收清单.md` | 每条“怎么看改对了”里**配置过的数值项**的改前／改后实测值，通过／没过 |
| `对比.md` | 参考页和你的页面量出来的数字（由 `run.mjs` 生成） |
| `ref-marked-top.png` / `mine-marked-top.png` | 带编号红圈的首屏截图（量测阶段拍的，**没套补丁**） |
| `mine-before-top.png` | `finish.mjs` 验收时拍的、没套补丁的首屏 |
| `mine-after-top.png` | `finish.mjs` 临时套上 `patch.css` 后拍的首屏，**检查视觉效果就看这张** |
| `patch.css` | 清单里的样式合集。要试它：用 `finish.mjs` 临时套用，或把这段 CSS 放进你本地的样式表里试 |

所有套样式都只发生在浏览器预览里，**没有改你的线上网站**。

## 四、限制（先看这里，省得踩坑）

- **网页会变**：例子里的数字是 2026-11 量的；你重跑例子会重新打开线上的 htmx.org，页面改版后数字可能不同，不一定还全过。
- **需要联网**（本地 html 文件和截图除外）。
- **例子的数字来自不同次抓取**：同一个例子里，旧的 `checklist.json`、`对比.md`、`改后验收清单.md` 可能是不同时间抓的，数字有零点几到几 px 的出入，页面有动态广告位时更明显。每个例子的 `timing.md` 末尾写了哪份文件是哪次抓的，以及发布前改过哪几处。
- **只量桌面宽度（默认 1440×900 的首屏和整页）**，没量手机宽度；可加 `--width 390` 单独跑一遍手机宽。
- **量出来的是浏览器算的样式，判断“该不该借”是 AI 的判断**。清单里的数字是事实，“为什么好”是推断。
- **`finish.mjs` 只检查清单里配置的数值项**，视觉效果仍要自己看改后截图（例子 02 里就出现过数字全过、画面居中被改歪的情况，见 `examples/02/timing.md`）。
- 需要登录才能看到的页面抓不到；有强反爬或要求先点同意弹窗的页面，截图里可能只有弹窗。页面有动态广告位时，每次打开高度可能不同（例子 03 就有一个 90px 的广告位），验收因此每次用全新浏览器量。
- 滚动动画、懒加载内容靠“自动滚一遍”触发，最长整页截图限 7000px 高。
- 站点原样式优先级高时，补丁要写得更“具体”才压得过（见 SKILL.md 第 4 步）。
- 这个工具只改样式预览，不改你网站的源码；“彻底改法”（要加 HTML 元素）清单里会单独写，但不验收。
- 例子里的“我的页面”其实是别人的公开网站（htmx、Django、JSONLint、Flask），是拿来当“自己的页面”演示的，里面的改版建议不代表这些站点真的该这么改。
- 工具截图带软件渲染的 WebGL（`--use-angle=swiftshader`），普通页面不受影响；如果你的页面是 3D／Canvas 页面，需要浏览器支持 WebGL，截完图请检查画面是不是纯黑／空白，再决定要不要当配图。

## 出错时看这里

| 提示 | 怎么办 |
|---|---|
| `找不到文件` / `找不到圈选文件` | 路径写错；路径里有空格或中文要用英文引号括起来：`--own "work/我的 页面/a.html"` |
| `…不是合法的 JSON` / `是空文件` | 圈选文件或 checklist.json 写错：检查逗号、引号（要英文 `"`），格式照 `templates/` 里的文件 |
| `圈选文件…格式不对` | 每一项要有 `selector` 或 `box`（四个数字） |
| `打不开这个页面` | 网址拼错、没网，或站点拒绝无头浏览器 |
| `页面打开了但里面几乎没有内容` | 空白页、要登录或被反爬拦住；改给截图（png/jpg） |
| `⚠️ 未找到 xxx` | 圈选的选择器在页面上选不中，红圈没画；去 `对比.md` 的标题、按钮表里抄选择器；图片那一侧只能用 `box` |
| `首屏没有H1` | 不是错误：这个页面首屏里没有 H1 标签（例如用图片当标题），对比表里对应格子是 `—` |
| 验收 `❌` | 看打印出的“还差多少”，改 `patch.css`（或选择器）后重跑 `finish.mjs` |
| `ℹ️ … own_url 是图片：…跳过验收` | 不是错误：自己的页面是截图，按上面「截图模式」只出清单和指令卡 |

## 五、文件说明

```
SKILL.md                      给 Claude Code 的工作流（核心）
scripts/doctor.mjs            环境自检
scripts/run.mjs               第 3 步：量两个页面 + 对比表
scripts/probe.mjs             单个页面的量测与截图（run 调用它）
scripts/compare.mjs           对比表生成
scripts/verify.mjs            套 patch.css 验收（finish 调用它）
scripts/render.mjs            清单 → md + html
scripts/finish.mjs            第 4 步：验收 + 出成品
scripts/lib.mjs               共用（找浏览器、控制浏览器）
templates/                    checklist 模板、最小清单+补丁、圈选示例
examples/01..04/              四个真实例子：input/ 输入，output/ 真实输出
```
