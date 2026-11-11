# 例 4 输入：Anglepoise 台灯（验收时照 README 现做）

- 描述：台灯结构（底座、弹簧、灯臂、反光罩、灯泡）
- 真实资料网页：https://en.wikipedia.org/wiki/Anglepoise_lamp（HTML 161,309 字节 → 文字 10,509 字符，见 `source.meta.json`）
- 命令：README 第 2、3 步原样（init → fetch → prompt decompose → check → 逐个 prompt part / test → build）
- 部件 JSON 由验收员手写（脚本不调大模型）。8 个部件，自检 8/8，3 条"包围盒重叠"提醒，成品 27 KB。
- 过程里真实出现的报错：`check` 报 4 处"放不进底座"，按提示缩小/移近后通过；反光罩第一次 `test` 报"比声明的 bound 大 112%"，把半径 0.8 改 0.7 后通过。
- **这个例子的缺点**：几何自检通过，但打开 `preview.png` 能看到上臂和下臂没有接上、弹簧和配重位置随意——这正是 README"限制"里说的"自检发现不了形状不像"。想要好看的请参考例 1～3。
