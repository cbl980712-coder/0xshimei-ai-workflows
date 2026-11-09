# AI 实测工作流合集

我在 X（@0xshimei）上写过的 AI 实测文章里用到的工具，整套放在这里，下载就能用。每个文件夹都是独立的，里面的 README 写了从零开始怎么装、怎么跑、会得到什么。

| 文件夹 | 做什么 | 需要什么 |
|---|---|---|
| [`screen-to-tutorial`](screen-to-tutorial/) | 一段软件操作录屏 → 自动切出每一步的画面 → AI 写动作和说明 → 一个图文教程 HTML，可直接发给别人 | Python 3.8+、Pillow、numpy、ffmpeg |
| [`ashare-watcher`](ashare-watcher/) | 海外 AI 交易教程用的平台国内用不了，换成国内免登录的 A 股行情：信号、回测、模拟盘、盯盘提醒 | 只要 Python 3.8+，不用装包 |
| [`video-prompt-guard`](video-prompt-guard/) | AI 视频生成前先检查分镜：哪些镜头容易崩、怎么拆怎么改，写好首尾帧提示词，算修改前后的预估成本；也能当 Claude Code Skill 用 | 只要 Python 3.8+，不用装包 |
| [`claude-fable-vs-opus`](claude-fable-vs-opus/) | Claude Fable 5.2 和 Opus 5.5 用同一句话各做的两个币圈小工具：合约仓位计算器、K 线回放练习器，附实测用时花费和截图 | 浏览器打开就能用 |

## 怎么下载

页面右上角绿色的 **Code → Download ZIP**，解压后进到你要用的那个文件夹，照里面的 README 做。

会用 git 的话：

```bash
git clone https://github.com/<你的用户名>/0xshimei-ai-workflows.git
```

## 说明

- 每个工具发布前都在一台全新的电脑环境里，照 README 从安装开始完整跑过一遍。
- `ashare-watcher` 只是技术演示，不构成投资建议，不连接任何券商、不会真实下单。
- 遇到问题欢迎提 Issue，写清楚系统、Python 版本和完整报错。

MIT 协议，随便用、随便改。
