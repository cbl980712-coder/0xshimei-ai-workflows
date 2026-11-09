# 录屏转图文教程（step-card-kit）

输入一段软件操作录屏（或一组连续截图），自动切出 4~6 张关键画面，让 Claude 看图写「动作名称 + 详细说明」，套模板得到一个图文对齐的 HTML 教程。全程在本机，不登录、不调付费接口（写说明这一步用你已经在用的 Claude Code）。

## 三步上手

**1. 装什么**
- Python 3.8+（macOS 自带的 3.9 就行）
- `pip3 install pillow numpy`
- 输入是视频时才需要 ffmpeg（macOS：`brew install ffmpeg`）；输入是截图文件夹则不需要
- Windows：到 python.org 装 Python，到 ffmpeg.org 下载 ffmpeg 并加入 PATH，下面命令里的 `python3` 换成 `python`
- 下载这个文件夹（GitHub 页面绿色的 Code → Download ZIP，解压），把 `screen-to-tutorial` 文件夹改名为 `kit`，放到你的工作目录里，下面的命令都在工作目录里运行
- 想让 Claude Code 自动照流程做：把它放到 `~/.claude/skills/step-card-tutorial/`（或项目的 `.claude/skills/step-card-tutorial/`），里面的 `SKILL.md` 就是技能

**2. 怎么放输入**
- 录屏：一个 mp4/mov/webm，建议 10~60 秒、一个任务一段，操作时每一步停顿约 1 秒再点下一步，鼠标指针保持录进去
- 截图：新建文件夹，按操作顺序放 png/jpg，文件名排序后就是操作顺序（`01.png`、`02.png` …）

**3. 怎么跑**
```bash
# ① 切关键帧（几秒）
python3 kit/video_step_splitter.py extract 你的录屏.mp4 -o work/
# ② 让 Claude 看 work/contact_sheet.jpg 和 work/frames/，写 work/steps.json
#    在 Claude Code 里说：「用 step-card-tutorial 处理 work/，软件是 XXX，任务是 YYY」
#    不用 Claude Code：按 kit/给AI对话的提示词.md 贴给任何能看图的 AI，回来的 JSON 存成 work/steps.json
#    或者手动：复制 work/steps.draft.json 填 title / desc（格式见 SKILL.md 第 3 步）
# ③ 出 HTML
python3 kit/video_step_splitter.py render work/steps.json -o work/tutorial.html --embed
```
双击 `work/tutorial.html` 即可查看；`--embed` 得到的是单个文件，可直接发给同事。

## 不想用 Claude Code？
照 `给AI对话的提示词.md` 做：上传 `contact_sheet.jpg`，贴提示词和 `steps.draft.json`，把 AI 回的 JSON 存成 `work/steps.json`，再跑第 ③ 步。ChatGPT、Claude 网页版、豆包等能看图的都行。

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | Claude Code 技能：每一步怎么做、怎么写、怎么自检 |
| `video_step_splitter.py` | `extract` 切关键帧；`render` 填模板 |
| `step_card_template.html` | 卡片样式（响应式、深色模式、点击放大、可打印），可自己改 |
| `给AI对话的提示词.md` | 不用 Claude Code 时，贴给网页版 AI 写步骤说明的提示词 |

## 常用参数（extract）
| 参数 | 默认 | 什么时候调 |
|---|---|---|
| `--min-steps / --max-steps` | 4 / 6 | 想要更多/更少步骤。步骤少于下限会自动提高灵敏度重试 |
| `--threshold` | 0.0015 | 屏幕变化面积占比达到多少才算一步。漏步调小，多步调大 |
| `--pixel-diff` | 14 | 淡色高亮（选中行）看不到时调小到 8~10 |
| `--merge-gap` | 2.0 | 打字被拆成两步时调大；0 = 关闭合并 |
| `--settle` | 2 | 进度条/动画被当成一步时调大到 3~4 |
| `--fps` | 5 | 操作很快的录屏用 8~10 |

## 已知局限
- 只能判断"画面变了"，不知道变化的含义，语义全靠 Claude 看图；Claude 看不清的小字会不确定
- 很小的变化（只有几个字符变了、复选框打勾）要靠调低 `--threshold`
- 全屏视频、满屏动画、带实时刷新图表的页面会产生误报
- 鼠标指针是按"小色块"过滤的，指针特别大（辅助功能放大）时需要调大 `--cursor-size`
- 截图文件夹模式下 `time` 显示的是图片序号，不是秒数
