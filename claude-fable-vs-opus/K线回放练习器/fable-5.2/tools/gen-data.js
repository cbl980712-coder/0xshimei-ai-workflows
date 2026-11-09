#!/usr/bin/env node
// 生成 300 根模拟 BTC/USDT 1 小时 K 线，写入 ../data.js
// 用法：node tools/gen-data.js [随机种子]
// 固定种子，重复运行得到同一段行情。
const fs = require("fs");
const path = require("path");

const SEED = Number(process.argv[2]) || 7;
const COUNT = 300;
const START_PRICE = 67200;
const START_TIME = Date.UTC(2026, 8, 1, 0, 0, 0); // 2026-09-01 00:00 UTC

// mulberry32 伪随机
function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = rng(SEED);
function gauss() {
  let u = 0, v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// 行情阶段：drift 为每根的平均涨跌幅，vol 为每根波动率，revert 为向阶段起点回归的力度（震荡用）
const REGIMES = [
  { len: 46, drift: 0.0000, vol: 0.0032, revert: 0.06, name: "横盘震荡" },
  { len: 44, drift: 0.0019, vol: 0.0042, revert: 0.0, name: "上涨趋势" },
  { len: 30, drift: 0.0001, vol: 0.0046, revert: 0.05, name: "高位震荡" },
  { len: 42, drift: -0.0024, vol: 0.0058, revert: 0.0, name: "下跌趋势" },
  { len: 40, drift: 0.0000, vol: 0.0030, revert: 0.07, name: "低位盘整" },
  { len: 48, drift: 0.0015, vol: 0.0040, revert: 0.0, name: "反弹" },
  { len: 50, drift: -0.0003, vol: 0.0050, revert: 0.03, name: "宽幅震荡" },
];

const bars = [];
let price = START_PRICE;
let volState = 1; // 波动聚集：大波动之后更容易接着大波动
let i = 0;

for (const rg of REGIMES) {
  const anchor = Math.log(price);
  for (let k = 0; k < rg.len && i < COUNT; k++, i++) {
    const open = price;
    const shock = gauss();
    volState = 0.86 * volState + 0.14 * (0.55 + 0.75 * Math.abs(shock));
    const vol = rg.vol * volState;

    let ret = rg.drift + vol * shock - rg.revert * (Math.log(open) - anchor);

    // 偶发大实体（消息行情）
    const news = rand() < 0.025;
    if (news) ret += (rand() < 0.5 ? -1 : 1) * (0.008 + rand() * 0.01);

    const close = open * Math.exp(ret);
    const top = Math.max(open, close);
    const bot = Math.min(open, close);

    let upWick = Math.abs(gauss()) * vol * 0.45;
    let dnWick = Math.abs(gauss()) * vol * 0.45;

    // 插针：约 6% 的 K 线有一根 1%~2.6% 的长影线，下跌段更容易向下插
    let pin = false;
    if (rand() < 0.06) {
      pin = true;
      const size = 0.01 + rand() * 0.016;
      const downBias = rg.drift < 0 ? 0.65 : rg.drift > 0 ? 0.4 : 0.5;
      if (rand() < downBias) dnWick += size;
      else upWick += size;
    }

    const high = top * (1 + upWick);
    const low = bot * (1 - dnWick);

    const range = (high - low) / open;
    const volume =
      (420 + 5200 * range * 100 * 0.6) *
      Math.exp(0.35 * gauss()) *
      (pin ? 1.7 : 1) *
      (news ? 1.5 : 1);

    const r1 = (x) => Math.round(x * 10) / 10;
    const o = r1(open), c = r1(close);
    bars.push([
      START_TIME + i * 3600 * 1000,
      o,
      Math.max(r1(high), o, c),
      Math.min(r1(low), o, c),
      c,
      Math.round(volume * 100) / 100,
    ]);
    price = c;
  }
}

const out =
  "// 模拟 BTC/USDT 1 小时 K 线，共 " + bars.length + " 根，由 tools/gen-data.js 生成（种子 " + SEED + "）。\n" +
  "// 每行：[开盘时间(毫秒), 开, 高, 低, 收, 成交量(BTC)]。数据为程序生成，不是真实行情。\n" +
  "window.KLINE_DATA = [\n" +
  bars.map((b) => "  " + JSON.stringify(b)).join(",\n") +
  "\n];\n";

fs.writeFileSync(path.join(__dirname, "..", "data.js"), out);

// 打印概况，方便检查
const closes = bars.map((b) => b[4]);
const hi = Math.max(...bars.map((b) => b[2]));
const lo = Math.min(...bars.map((b) => b[3]));
let pins = 0;
for (const b of bars) {
  const up = (b[2] - Math.max(b[1], b[4])) / b[1];
  const dn = (Math.min(b[1], b[4]) - b[3]) / b[1];
  if (up > 0.01 || dn > 0.01) pins++;
}
console.log("根数", bars.length, "起", bars[0][1], "收", closes[closes.length - 1], "最高", hi, "最低", lo, "插针", pins);
let idx = 0;
for (const rg of REGIMES) {
  const a = bars[idx][1], b = bars[Math.min(idx + rg.len, COUNT) - 1][4];
  console.log(rg.name, idx, "→", idx + rg.len - 1, a, "→", b, ((b / a - 1) * 100).toFixed(2) + "%");
  idx += rg.len;
}
