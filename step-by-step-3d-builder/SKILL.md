---
name: step-by-step-3d-builder
description: 把"一句话描述的复杂 3D 对象"（动物细胞、机械表机芯、发动机…）拆成部件树，逐个部件生成并在无头浏览器里自检，最后组装成单文件 Three.js 网页（可拖拽旋转、点击高亮部件）。用户说"用 Three.js 做个 3D 模型/互动科普组件"、"AI 一次写完 3D 场景总是报错/白屏/一团糟"时使用。
---

# 分步建模 Skill

核心原则：**永远不要一次写完整个场景。** 先定装配图（不写几何），再一次只写一个部件，每写一个就自检。
所有命令在本目录（有 `step_by_step_3d_builder.py` 的地方）运行，Python 3.8+，需要本机有 Chrome 或 Edge。`DIR` = 项目目录，例如 `my3d/cell`。

## 第 0 步：确认环境
```bash
python3 step_by_step_3d_builder.py doctor      # Windows 用 python 或 py -3
```
必须看到"端到端 ✓"。没有就按提示装 Chrome/Edge，或设 `BROWSER_BIN`。

## 第 1 步：建目录并抓真实资料
```bash
python3 step_by_step_3d_builder.py init DIR "用户的一句话描述" --url "<一个真实的百科/说明页网址>"
python3 step_by_step_3d_builder.py fetch DIR     # 得到 DIR/source.txt；抓不到就让用户把正文存成 source.txt
```
资料是用来防止"编部件"的：每个部件都要能在 source.txt 里找到依据词。

## 第 2 步：拆解 = 写 plan.json（不写任何几何）
```bash
python3 step_by_step_3d_builder.py prompt decompose DIR      # 打印拆解提示词，你自己按它写 DIR/plan.json
```
plan.json 里每个部件：`id / name / parent / position(相对父部件) / bound / depends_on / source_terms / desc`。
规则：8～14 个部件；外壳放第一个；子部件必须放得进父部件的 bound；会运动的部件 position 填行程中点、bound 包住整个行程；
bound 可以是数字（球）或 `[rx,ry,rz]`（椭球）；`inside:"xz"` 表示只要求水平投影在父部件内；`inside:false` 表示可以在外面。
```bash
python3 step_by_step_3d_builder.py check DIR   # 检查树/环/依赖/装配冲突/依据词，并打印坐标装配图
```
`check` 不过不许往下走。

## 第 3 步：循环——一次一个部件
```bash
python3 step_by_step_3d_builder.py status DIR              # 告诉你下一个该写谁
python3 step_by_step_3d_builder.py prompt part DIR <id>    # 该部件的提示词（已带位置、bound、容器规则、已完成部件）
```
把结果写成 `DIR/parts/<id>.json`（只含 shapes / code / anim / update，**不要写 position 和 bound**），然后：
```bash
python3 step_by_step_3d_builder.py test DIR --only <id>
```
- 通过 → 下一个部件。
- 不通过 → `prompt fix DIR <id>` 取修复提示词，只改报错的地方，再 `test`。不要去改别的部件。
常见报错含义：
- "比自己声明的 bound 大"：尺寸/坐标写错，或运动行程、轴长没算进 bound。
- "跑出父部件范围"：位置放错，或父部件 bound 太小。
- "构建失败: …"：code 语法/运行错误，只影响这个部件（页面里用红色线框占位，不会整页崩）。
- "几何里出现 NaN"：某个尺寸参数缺失。

shapes 可用：sphere box cylinder cone torus capsule tube gear scatter；复杂形状用 `code`（函数体，参数 `(THREE, ctx)`，返回 Object3D，
随机用 `ctx.rngFrom(seed)`，不要 Math.random）；自定义运动用 `update`（参数 `(node, t, ctx)`）。完整说明见 `prompts_3d_modular.md` 模板 2。

## 第 4 步：组装
```bash
python3 step_by_step_3d_builder.py build DIR --screenshot DIR/preview.png
```
全部通过才会输出 `DIR/index.html`（单文件，three.js 走 CDN，首次打开需联网）。`--allow-fail` 可在有未通过部件时强行输出。
最后把 `report.json` 里的通过数、`run_log.json` 里的耗时告诉用户，并用无头浏览器或真实浏览器点开 index.html 确认能点击高亮。

## 不要做的事
- 不要一次写多个部件再统一测试。
- 不要为了让自检通过而把 bound 随手改大——先确认是不是形状真的画错了。
- 不要编 source_terms：资料里没有的词，不要写进去充数。
