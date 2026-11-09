#!/usr/bin/env python3
"""生成 300 根模拟 BTC/USDT 1 小时 K 线，写入 data.js（页面直接加载，无需网络）。

行情分段：震荡 → 上涨 → 高位震荡 → 急跌 → 下跌 → 底部震荡 → 反弹，
带波动率聚集（GARCH 风格）、日内波动差异、偶发长上/下影线（插针）。
固定随机种子，重复运行结果一致。用法：python3 gen_data.py [种子]
"""
import json
import math
import random
import sys
from datetime import datetime, timezone

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261110
N = 300
START_PRICE = 67250.0
START_TS = int(datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc).timestamp())

# (根数, 每小时漂移, 基础波动率)
REGIMES = [
    (40, 0.0000, 0.0045),   # 开盘震荡
    (55, 0.0016, 0.0055),   # 上涨趋势
    (35, 0.0000, 0.0050),   # 高位震荡
    (12, -0.0060, 0.0110),  # 急跌
    (48, -0.0012, 0.0065),  # 阴跌
    (50, 0.0001, 0.0045),   # 底部震荡
    (60, 0.0014, 0.0058),   # 反弹
]
assert sum(r[0] for r in REGIMES) == N

rng = random.Random(SEED)


def fat_tail():
    """Student-t(4) 近似，制造少量大波动。"""
    z = rng.gauss(0, 1)
    chi = sum(rng.gauss(0, 1) ** 2 for _ in range(4)) / 4
    return z / math.sqrt(chi) * math.sqrt(0.5)


candles = []
price = START_PRICE
vol_state = 1.0
mean_anchor = START_PRICE
i = 0
for length, drift, base_vol in REGIMES:
    if drift == 0.0 or abs(drift) < 0.0005:
        mean_anchor = price
    for _ in range(length):
        ts = START_TS + i * 3600
        hour = (i % 24)
        # 欧美时段波动更大
        session = 1.25 if 13 <= hour <= 20 else (0.8 if 2 <= hour <= 7 else 1.0)
        vol_state = 0.85 * vol_state + 0.15 * (0.6 + abs(rng.gauss(0, 1)))
        sigma = base_vol * session * vol_state
        # 震荡段向均值回归
        revert = 0.0
        if abs(drift) < 0.0005:
            revert = -0.08 * math.log(price / mean_anchor)
        ret = drift + revert * 0.1 + sigma * fat_tail()
        o = price
        c = o * math.exp(ret)
        body_hi, body_lo = max(o, c), min(o, c)
        hi = body_hi * (1 + abs(rng.gauss(0, sigma * 0.55)))
        lo = body_lo * (1 - abs(rng.gauss(0, sigma * 0.55)))
        vol_mult = 1.0
        # 插针：约 4% 概率出现长影线
        r = rng.random()
        if r < 0.022:
            lo = body_lo * (1 - rng.uniform(0.012, 0.03))
            vol_mult = rng.uniform(2.5, 4.0)
        elif r < 0.04:
            hi = body_hi * (1 + rng.uniform(0.012, 0.028))
            vol_mult = rng.uniform(2.5, 4.0)
        move = abs(ret) / max(sigma, 1e-9)
        volume = rng.uniform(380, 720) * session * (0.7 + 0.5 * move) * vol_mult * (1.6 if abs(drift) > 0.004 else 1.0)
        candles.append({
            "t": ts,
            "o": round(o, 1),
            "h": round(hi, 1),
            "l": round(lo, 1),
            "c": round(c, 1),
            "v": round(volume, 2),
        })
        price = c
        i += 1

# 修正四舍五入后的一致性
for k in candles:
    k["h"] = max(k["h"], k["o"], k["c"])
    k["l"] = min(k["l"], k["o"], k["c"])

meta = {
    "symbol": "BTC/USDT",
    "interval": "1h",
    "seed": SEED,
    "note": "模拟数据，非真实行情 / Simulated data, not real market data",
}
with open("data.js", "w", encoding="utf-8") as f:
    f.write("// 由 gen_data.py 生成的模拟 BTC/USDT 1 小时 K 线（300 根），非真实行情\n")
    f.write("window.KLINE_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
    f.write("window.KLINE_DATA = [\n")
    f.write(",\n".join(json.dumps(k, separators=(",", ":")) for k in candles))
    f.write("\n];\n")

closes = [k["c"] for k in candles]
print(f"生成 {len(candles)} 根，起 {candles[0]['o']}，终 {closes[-1]}，"
      f"最高 {max(k['h'] for k in candles)}，最低 {min(k['l'] for k in candles)}")
