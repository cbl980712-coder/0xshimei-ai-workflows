---
name: ashare-domestic-adapter
description: 把海外 AI 交易教程(GMGN、Alpaca、Binance、IBKR、TradingView、yfinance 等)的环境需求，映射成国内免海外卡、免登录的 A 股平替方案，并跑出盯盘信号 + 回测 + 本地模拟盘报告。用户说"国内用不了教程里的平台""没海外卡能玩吗""帮我把这个教程改成 A 股版"时用。
---

# 国内数据源与 A 股平替链路适配器

## 前置
- 只需 Python 3.8+，不用装任何包(脚本只用标准库)。可选 `pip install akshare` 换数据源。
- 脚本: `ashare_ai_watcher.py`(与本文件同目录)。

## 步骤
1. **收需求**。让用户贴原教程/评论里用到的海外平台与想做的事(行情、回测、下单、提醒)，存成 `input.txt`。如果用户自己有关注的 A 股，请他写 6 位代码(如 600519)，脚本会优先盯这些。
2. **跑适配**:
   `python3 ashare_ai_watcher.py adapt --input input.txt --out out/ [--cash 300000] [--offline]`
   产出 `out/report.md`(映射表、最新信号、回测)、`watch_config.json`、`signals.json`、`ledger.csv`(模拟盘流水)、`data/*.csv`(缓存行情)。
3. **检查结果**(Claude 要做的)：
   - 映射表里每一行"海外→国内"是否合理；没识别的需求，手动补一行并说明。
   - 回测表里若出现"本金不够1手被跳过"，把 `--cash` 调大重跑，或换低价标的，不要把"0 笔交易"当结论。
   - 加密货币/链上类需求，必须明确告诉用户：大陆不支持，只保留"盯异动"的思路，改用 ETF/A 股。
4. **给用户实时盯盘**:
   `python3 ashare_ai_watcher.py watch --config out/watch_config.json --loop 60`
   交易时段内每 60 秒查一次，信号变化才打印 `[ALERT]`。
5. **交付**：把 report.md 的结论用大白话写给用户，附风险提示：仅技术演示、不是投资建议、不连任何券商、不真实下单。

## 注意
- 网络失败时脚本自动回退到缓存/`sample_data/`(报告里数据来源会写「上次缓存」或「样例数据」)，要告诉用户这不是最新行情。
- 不要承诺收益；不要替用户接券商账号密码。
- 想新增海外平台关键词: 改 `ashare_ai_watcher.py` 顶部 `RULES` 表即可。
