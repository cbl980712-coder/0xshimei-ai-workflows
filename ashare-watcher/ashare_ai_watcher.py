#!/usr/bin/env python3
"""国内数据源与 A 股平替链路适配器 (仅标准库, 无需登录/付费/海外卡)

子命令:
  adapt  --input 需求.txt --out 输出目录 [--offline]   需求 -> 映射表 + 配置 + 盯盘/回测/模拟盘报告
  watch  --config watch_config.json [--loop 60]         按配置实时盯盘, 触发信号就打印预警
数据源: 腾讯财经日K(默认) / 新浪实时报价; 装了 akshare 也可 --source akshare。
缓存: 拉到的数据存到 输出目录/data/*.csv; --offline 时只读缓存或 kit/sample_data。
"""
import argparse, csv, json, os, re, sys, time, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- 1. 需求映射 ----------
# (关键词正则, 海外项, 国内平替, 说明, 默认标的)
RULES = [
    (r"gmgn|meme|pump\.?fun|链上|solana|\bsol\b|dex", "GMGN/链上Meme币/DEX",
     "A股题材异动盯盘(高换手成长股)", "境内不可交易加密资产; 保留'抓异动+风控'思路, 用放量突破信号盯A股热点",
     ["sz300750", "sh688981", "sz002594"]),
    (r"binance|币安|okx|coinbase|btc|比特币|\beth\b|crypto|加密", "加密货币交易所API",
     "宽基/黄金/跨境ETF行情", "大陆不支持加密货币交易; 用510300沪深300、518880黄金、513100纳指ETF做'主流行情'盯盘",
     ["sh510300", "sh518880", "sh513100"]),
    (r"alpaca|interactive brokers|ibkr|robinhood|盈透|美股|nasdaq|nvda|tsla|aapl|yfinance|polygon", "海外券商/美股行情API",
     "腾讯财经/新浪公开行情(+可选AkShare)", "行情免登录; 下单换成本地模拟盘; 美股敞口可用513100纳指ETF",
     ["sh600519", "sz300750", "sh513100"]),
    (r"tradingview|backtest|回测|backtrader|vectorbt|zipline", "回测框架/TradingView",
     "本地回测(均线金叉/死叉)", "脚本内置, 含A股佣金、印花税、100股整手; 当天收盘出信号、次日开盘成交", None),
    (r"下单|order|broker|实盘|paper|模拟盘", "券商下单API",
     "本地模拟盘(T+1/整手/按板块涨跌停/费用)", "不连接任何券商, 只写 ledger.csv; 实盘请走自己券商的合规渠道", None),
    (r"openai|gpt|claude|llm|gemini|ai\s*agent|智能体", "海外大模型API",
     "规则信号 + 可选国产模型解读", "盯盘本身不依赖大模型; 需要解读时把 report.md 贴给任意国产模型", None),
]
DEFAULT_SYMBOLS = ["sh600519", "sz300750", "sh510300"]


def map_requirements(text):
    low = text.lower()
    hits, symbols = [], []
    for pat, old, new, why, syms in RULES:
        if re.search(pat, low):
            hits.append({"overseas": old, "domestic": new, "why": why})
            for s in syms or []:
                if s not in symbols:
                    symbols.append(s)
    # 需求里直接写了 6 位代码: 优先放前面
    own = []
    for code in re.findall(r"(?<!\d)(\d{6})(?!\d)", text):
        s = ("sh" if code[0] in "569" else "sz") + code
        if s not in own:
            own.append(s)
    symbols = own + [s for s in symbols if s not in own]
    if not hits:
        hits.append({"overseas": "(未识别)", "domestic": "默认A股蓝筹盯盘", "why": "没匹配到关键词, 使用默认标的"})
    return hits, (symbols or DEFAULT_SYMBOLS)[:6]


# ---------- 2. 数据 ----------
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}


def http(url, enc="utf-8"):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10).read().decode(enc, "ignore")


def fetch_tencent(sym, n=250):
    j = json.loads(http("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)))
    d = j["data"][sym]
    rows = d.get("qfqday") or d.get("day")
    return [{"date": r[0], "open": float(r[1]), "close": float(r[2]), "high": float(r[3]),
             "low": float(r[4]), "vol": float(r[5])} for r in rows]


def fetch_akshare(sym, n=250):
    import akshare as ak  # 可选依赖
    code = sym[-6:]
    if code.startswith(("51", "15", "56", "58", "16")):   # ETF/LOF 要用基金接口，股票接口会返回空表
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq").tail(n)
    else:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(n)
    return [{"date": str(r["日期"])[:10], "open": float(r["开盘"]), "close": float(r["收盘"]),
             "high": float(r["最高"]), "low": float(r["最低"]), "vol": float(r["成交量"])} for _, r in df.iterrows()]


def fetch_quote(sym):
    """新浪实时报价: 名称/现价/昨收"""
    t = http("https://hq.sinajs.cn/list=" + sym, "gbk")
    f = re.search(r'"(.*)"', t).group(1).split(",")
    return {"name": f[0], "price": float(f[3]), "prev": float(f[2])}


def save_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "open", "close", "high", "low", "vol"])
        w.writeheader()
        w.writerows(rows)


def load_csv(path):
    with open(path) as f:
        return [{k: (v if k == "date" else float(v)) for k, v in r.items()} for r in csv.DictReader(f)]


def get_bars(sym, outdir, offline, source="tencent"):
    cache = os.path.join(outdir, "data", sym + ".csv")
    if not offline:
        try:
            rows = fetch_akshare(sym) if source == "akshare" else fetch_tencent(sym)
            if len(rows) < 30 and source == "akshare":   # AkShare 偶尔给空表：退回腾讯
                rows = fetch_tencent(sym)
            if len(rows) < 30:
                raise ValueError("只拿到 %d 天行情" % len(rows))
            save_csv(cache, rows)
            return rows, "live"
        except Exception as e:
            print("  ! %s 在线获取失败(%s), 改用缓存" % (sym, e), file=sys.stderr)
    if os.path.exists(cache):
        return load_csv(cache), "上次缓存"
    sample = os.path.join(HERE, "sample_data", sym + ".csv")
    if os.path.exists(sample):
        return load_csv(sample), "样例数据"
    raise SystemExit("%s: 联网没取到，也没有缓存或样例数据（离线模式只带了样例里那几只）" % sym)


# ---------- 3. 指标/信号 ----------
def sma(v, n):
    return [None if i + 1 < n else sum(v[i + 1 - n:i + 1]) / n for i in range(len(v))]


def rsi(c, n=14):
    out = [None] * len(c)
    for i in range(n, len(c)):
        g = sum(max(c[j] - c[j - 1], 0) for j in range(i - n + 1, i + 1)) / n
        l = sum(max(c[j - 1] - c[j], 0) for j in range(i - n + 1, i + 1)) / n
        out[i] = 100 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def indicators(bars):
    c = [b["close"] for b in bars]
    v = [b["vol"] for b in bars]
    return {"ma5": sma(c, 5), "ma20": sma(c, 20), "rsi": rsi(c), "vma20": sma(v, 20),
            "hh20": [None if i < 20 else max(b["high"] for b in bars[i - 20:i]) for i in range(len(bars))]}


def signals_at(bars, ind, i):
    s = []
    if i < 1 or None in (ind["ma5"][i], ind["ma20"][i], ind["ma5"][i - 1], ind["ma20"][i - 1]):
        return s
    c = bars[i]["close"]
    if ind["ma5"][i - 1] <= ind["ma20"][i - 1] and ind["ma5"][i] > ind["ma20"][i]:
        s.append("金叉(MA5上穿MA20)")
    if ind["ma5"][i - 1] >= ind["ma20"][i - 1] and ind["ma5"][i] < ind["ma20"][i]:
        s.append("死叉(MA5下穿MA20)")
    r = ind["rsi"][i]
    if r is not None:
        if r < 30:
            s.append("RSI超卖(%.0f)" % r)
        if r > 70:
            s.append("RSI超买(%.0f)" % r)
    if ind["hh20"][i] and c > ind["hh20"][i] and ind["vma20"][i] and bars[i]["vol"] > 1.5 * ind["vma20"][i]:
        s.append("放量突破20日高点")
    return s


# ---------- 4. 回测 + 本地模拟盘 (A股规则) ----------
COMM, COMM_MIN, STAMP = 0.00025, 5.0, 0.0005  # 佣金万2.5(最低5元), 卖出印花税万5


def limit_pct(sym):
    """涨跌停幅度: 主板 10%, 创业板(300/301)和科创板(688/689) 20%, 北交所 30% (ST 股 5% 这里不区分)"""
    code = sym[-6:]
    if code.startswith(("300", "301", "688", "689")):
        return 0.20
    if sym.startswith("bj") or code.startswith(("43", "83", "87", "92")):
        return 0.30
    return 0.10


def backtest(bars, cash0=100000.0, sym=""):
    """金叉买/死叉卖; 整手100股; 当天收盘出信号、次日开盘成交; 当天买入最早次日才卖(T+1); 开盘涨停不买/跌停不卖(按板块涨跌幅)"""
    ind = indicators(bars)
    cash, sh, ledger, eq, skipped = cash0, 0, [], [], 0
    for i in range(1, len(bars) - 1):
        sg = signals_at(bars, ind, i)
        nxt = bars[i + 1]
        px = nxt["open"]
        prev = bars[i]["close"]
        lp = limit_pct(sym)
        up_lim = px >= prev * (1 + lp) - 0.005
        dn_lim = px <= prev * (1 - lp) + 0.005
        if any(x.startswith("金叉") for x in sg) and sh == 0 and not up_lim:
            q = int(cash / px / (1 + COMM) // 100 * 100)
            if q >= 100:
                fee = max(q * px * COMM, COMM_MIN)
                cash -= q * px + fee
                sh = q
                ledger.append([nxt["date"], "BUY", px, q, round(fee, 2), round(cash, 2)])
            else:
                skipped += 1  # 本金不够买1手(100股)
        elif any(x.startswith("死叉") for x in sg) and sh > 0 and not dn_lim:
            fee = max(sh * px * COMM, COMM_MIN) + sh * px * STAMP
            cash += sh * px - fee
            ledger.append([nxt["date"], "SELL", px, sh, round(fee, 2), round(cash, 2)])
            sh = 0
        eq.append(cash + sh * bars[i]["close"])
    final = cash + sh * bars[-1]["close"]
    peak, mdd = 0, 0
    for e in eq:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak else 0)
    return {"return": final / cash0 - 1, "buy_hold": bars[-1]["close"] / bars[1]["close"] - 1,
            "max_drawdown": mdd, "trades": len(ledger), "skipped": skipped, "ledger": ledger, "open_shares": sh}


# ---------- 5. 输出 ----------
def run_adapt(a):
    text = open(a.input, encoding="utf-8").read()
    out = a.out
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    hits, symbols = map_requirements(text)
    cfg = {"symbols": symbols, "ma": [5, 20], "rsi": [30, 70], "vol_ratio": 1.5, "interval_sec": 60}
    json.dump(cfg, open(os.path.join(out, "watch_config.json"), "w"), ensure_ascii=False, indent=1)
    md = ["# 国内平替方案\n", "## 一、需求映射\n", "| 原帖用到(海外) | 国内平替 | 说明 |", "|---|---|---|"]
    md += ["| %s | %s | %s |" % (h["overseas"], h["domestic"], h["why"]) for h in hits]
    md += ["", "## 二、盯盘标的与最新信号(生成于 %s)\n" % dt.date.today()]
    allledger, summ = [], []
    for s in symbols:
        bars, src = get_bars(s, out, a.offline, a.source)
        ind = indicators(bars)
        sg = signals_at(bars, ind, len(bars) - 1)
        r = backtest(bars, a.cash, s)
        summ.append({"symbol": s, "last_date": bars[-1]["date"], "close": bars[-1]["close"], "signals": sg,
                     "source": src, "return": round(r["return"], 4), "buy_hold": round(r["buy_hold"], 4),
                     "max_drawdown": round(r["max_drawdown"], 4), "trades": r["trades"], "skipped_no_cash": r["skipped"]})
        allledger += [[s] + row for row in r["ledger"]]
        md.append("- **%s** %s 收 %.3f  数据:%s  信号: %s" % (s, bars[-1]["date"], bars[-1]["close"], src, "、".join(sg) or "无"))
    md += ["", "## 三、回测(近约1年, 金叉买/死叉卖, %.0f元本金, 含佣金/印花税/整手, 次日开盘成交, 按板块涨跌停)\n" % a.cash,
           "| 标的 | 策略收益 | 买入持有 | 最大回撤 | 交易次数 |", "|---|---|---|---|---|"]
    md += ["| %s | %+.1f%% | %+.1f%% | %.1f%% | %d%s |" % (
        x["symbol"], x["return"] * 100, x["buy_hold"] * 100, x["max_drawdown"] * 100, x["trades"],
        " (另有%d次金叉因本金不够1手被跳过, 可加大 --cash)" % x["skipped_no_cash"] if x["skipped_no_cash"] else "")
        for x in summ]
    md += ["", "> 仅为技术演示, 不构成投资建议; 本工具不连接任何券商, 不会真实下单。"]
    open(os.path.join(out, "report.md"), "w", encoding="utf-8").write("\n".join(md))
    json.dump({"mapping": hits, "summary": summ}, open(os.path.join(out, "signals.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(out, "ledger.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "date", "side", "price", "qty", "fee", "cash_after"])
        w.writerows(allledger)
    print("\n".join(md))
    print("\n[耗时 %.1fs] 输出在 %s/" % (time.time() - t0, out))


def run_watch(a):
    cfg = json.load(open(a.config))
    seen = {}
    while True:
        for s in cfg["symbols"]:
            try:
                bars = fetch_tencent(s, 60)
                q = fetch_quote(s)
                if bars[-1]["date"] == str(dt.date.today()):
                    bars[-1] = dict(bars[-1], close=q["price"])
                sg = signals_at(bars, indicators(bars), len(bars) - 1)
                chg = q["price"] / q["prev"] - 1
                if abs(chg) >= 0.05:
                    sg.append("日内异动%+.1f%%" % (chg * 100))
                line = "%s %s(%s) %.3f %+.2f%%" % (dt.datetime.now().strftime("%H:%M:%S"), q["name"], s, q["price"], chg * 100)
                if sg and seen.get(s) != tuple(sg):
                    print("[ALERT]", line, "|", "、".join(sg))
                    seen[s] = tuple(sg)
                else:
                    print("      ", line)
            except Exception as e:
                print("  ! ", s, e)
        if not a.loop:
            break
        time.sleep(a.loop)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)   # 盯盘输出逐行立刻显示
    except Exception:
        pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("adapt")
    x.add_argument("--input", required=True)
    x.add_argument("--out", required=True)
    x.add_argument("--cash", type=float, default=100000.0)
    x.add_argument("--offline", action="store_true")
    x.add_argument("--source", default="tencent", choices=["tencent", "akshare"])
    y = sp.add_parser("watch")
    y.add_argument("--config", required=True)
    y.add_argument("--loop", type=int, default=0)
    a = p.parse_args()
    run_adapt(a) if a.cmd == "adapt" else run_watch(a)
