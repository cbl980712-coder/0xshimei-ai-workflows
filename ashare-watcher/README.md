# A 股盯盘 + 回测 + 模拟盘（国内网络直连版）

很多热门的 AI 交易教程用的是 GMGN、Alpaca、币安、IBKR、TradingView 这类海外平台，国内读者照着做，第一步就卡住。
这个工具照着那些教程的思路，做了一套**国内能直接跑的 A 股版本**：拿行情 → 算信号 → 回测 → 模拟盘 → 盯盘提醒。

> 说清楚它是什么：它不是 GMGN 的替代品。GMGN 看的是链上代币，这里看的是 A 股和 ETF，只保留了「盯异动、按规则买卖、先模拟再说」这套做法。
> 仅为技术演示，不构成投资建议。脚本不连接任何券商，不会真实下单。

## 你会得到什么

跑完一条命令，`out/` 文件夹里有：

| 文件 | 内容 |
|---|---|
| `report.md` | 海外平台 → 国内替代的对照表、每只标的的最新信号、近一年回测结果 |
| `ledger.csv` | 模拟盘每一笔买卖：日期、价格、股数、手续费、剩余资金 |
| `signals.json` | 最新信号，方便别的程序读 |
| `watch_config.json` | 盯盘用的配置（标的、均线、RSI 参数） |
| `data/*.csv` | 拿到的行情，下次没网时自动用 |

回测按 A 股规则算：100 股整手、佣金万 2.5（最低 5 元）、卖出印花税万 5；当天收盘出信号、第二天开盘成交，当天买的最早第二天才能卖（T+1）；开盘涨停不买、跌停不卖，涨跌幅按板块算（主板 10%，创业板和科创板 20%，北交所 30%）。

## 第 1 步：准备环境

只要 Python 3.8 或更新的版本，**不用装任何包**，也不用注册、登录或海外卡。

- Mac：自带 `python3`，打开「终端」就能用。
- Windows：到 python.org 装 Python，下面命令里的 `python3` 换成 `python`。

下载这个文件夹（GitHub 页面右上角绿色的 Code → Download ZIP，解压），在终端里进到 `ashare-watcher` 文件夹。

## 第 2 步：写下你的需求

新建一个文本文件，比如 `my_input.txt`，写上原教程用了什么、你想盯哪些股票（6 位代码）：

```
教程用 Alpaca 拿美股行情 + TradingView 回测 + paper trading 下单。
我在国内，想用 600519 和 300750 在 A 股先跑模拟盘。
```

不写股票代码也行，会按需求自动挑几只（沪深 300ETF、黄金 ETF、纳指 ETF 等）。`input_template.txt` 是现成的例子。

## 第 3 步：跑

```bash
python3 ashare_ai_watcher.py adapt --input my_input.txt --out out
```

几秒钟就跑完，打开 `out/report.md` 看结果。常用参数：

- `--cash 300000`：本金。茅台一手要 14 万多，本金不够时回测会写「因本金不够 1 手被跳过」，把本金调大再跑。
- `--offline`：没网时用自带的样例行情（报告里数据来源会写「样例数据」，那不是最新行情）。
- `--source akshare`：换成 AkShare 数据源，先 `pip install akshare`（建议在虚拟环境里装）。

想实时盯盘（交易时段内每 60 秒查一次，出现新信号会打印 `[ALERT]`，按 Ctrl+C 退出）：

```bash
python3 ashare_ai_watcher.py watch --config out/watch_config.json --loop 60
```

## 用 Claude Code 跑

把这个文件夹放进 `.claude/skills/ashare-domestic-adapter/`，在 Claude Code 里说「帮我把这个教程改成 A 股版」，再把教程内容贴给它。它会按 `SKILL.md` 的步骤跑脚本、检查结果，再用大白话把报告讲给你听。

## 数据从哪来、有什么限制

- 历史日 K：腾讯财经公开接口；实时价：新浪财经公开接口。都免登录、国内直连，但不是官方付费数据：接口可能改版或限流，个人学习够用，不适合拿去做商业服务。
- 联网失败时自动用上次缓存，再不行用自带样例。
- 信号只有均线金叉/死叉、RSI 超买超卖、放量这几种，是演示用的入门规则，回测结果不代表以后能赚钱（样例里好几只都是亏的）。

## 文件

| 文件 | 作用 |
|---|---|
| `ashare_ai_watcher.py` | 主脚本（需求映射、信号、回测、模拟盘、盯盘），只用 Python 自带库 |
| `SKILL.md` | Claude Code Skill 版步骤 |
| `china_local_setup_guide.md` | 国内环境避坑指南：哪些能做、哪些在大陆做不了 |
| `input_template.txt` | 需求写法示例 |
| `sample_data/` | 离线样例行情（7 只标的，约一年日 K） |
