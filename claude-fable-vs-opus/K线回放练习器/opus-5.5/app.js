(() => {
  "use strict";

  // ---------- 常量 ----------
  const DATA = window.KLINE_DATA || [];
  const N = DATA.length;
  const START_BARS = 50;
  const BALANCE = 10000;      // 初始资金 USDT
  const FEE = 0.0005;          // 手续费率（按成交额）
  const MAX_LEV = 10;          // 最大杠杆
  const $ = (id) => document.getElementById(id);

  // ---------- 多语言 ----------
  const I18N = window.I18N;
  let lang = "zh-CN";
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 忽略 */ } },
  };
  function pickLang() {
    const saved = store.get("kr_lang");
    if (saved && I18N.dict[saved]) return saved;
    const nav = (navigator.language || "zh-CN").toLowerCase();
    if (nav.startsWith("zh")) return /tw|hk|mo|hant/.test(nav) ? "zh-TW" : "zh-CN";
    if (nav.startsWith("ja")) return "ja";
    if (nav.startsWith("ko")) return "ko";
    return "en";
  }
  function t(key, ...args) {
    let s = (I18N.dict[lang] && I18N.dict[lang][key]) ?? I18N.dict["zh-CN"][key] ?? key;
    args.forEach((a, i) => { s = s.replace("{" + i + "}", a); });
    return s;
  }
  function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
      el.setAttribute("aria-label", t(el.dataset.i18nTitle));
    });
    document.title = t("title");
    $("playBtn").textContent = timer ? t("pause") : t("play");
    renderPanel();
    if (!$("summary").hidden) renderSummary();
    draw();
  }

  // ---------- 格式化 ----------
  const fmtPrice = (p) => p == null || !isFinite(p) ? "—" : p.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmtMoney = (v, sign = true) => {
    if (v == null || !isFinite(v)) return "—";
    const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return (v < 0 ? "-" : sign && v > 0 ? "+" : "") + s;
  };
  const fmtPct = (v, sign = true) => !isFinite(v) ? "—" : (sign && v > 0 ? "+" : "") + (v * 100).toFixed(2) + "%";
  const fmtQty = (q) => +q.toFixed(4) + "";
  const cls = (v) => v > 0 ? "pos" : v < 0 ? "neg" : "";
  const pad = (n) => String(n).padStart(2, "0");
  function fmtTime(ts, withDate = true) {
    const d = new Date(ts * 1000);
    const hm = pad(d.getHours()) + ":" + pad(d.getMinutes());
    return withDate ? pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + hm : hm;
  }

  // ---------- 状态 ----------
  let S;          // 交易状态
  let timer = null;
  function resetState() {
    S = {
      idx: Math.min(START_BARS, N) - 1,
      pos: null,          // { side: 1|-1, qty, entry, openIdx, fees }
      realized: 0,
      fees: 0,
      trades: [],
      markers: [],        // { idx, price, kind: 'open'|'close', side }
      peak: BALANCE,
      maxDD: 0,           // 金额
      maxDDPct: 0,
      ended: false,
    };
    view.offset = 0;
  }

  const price = () => DATA[S.idx].c;
  const floatPnl = (p = price()) => S.pos ? S.pos.side * (p - S.pos.entry) * S.pos.qty : 0;
  const equity = (p = price()) => BALANCE + S.realized + floatPnl(p);

  function updateDD() {
    const eq = equity();
    if (eq > S.peak) S.peak = eq;
    const dd = S.peak - eq;
    if (dd > S.maxDD) S.maxDD = dd;
    const ddPct = S.peak > 0 ? dd / S.peak : 0;
    if (ddPct > S.maxDDPct) S.maxDDPct = ddPct;
  }

  // ---------- 消息 ----------
  let msgTimer = null;
  function say(text, type = "ok") {
    const el = $("msg");
    el.textContent = text;
    el.className = "msg " + type;
    clearTimeout(msgTimer);
    msgTimer = setTimeout(() => { el.textContent = ""; el.className = "msg"; }, 4500);
  }

  // ---------- 交易 ----------
  function readNum(id) {
    const raw = $(id).value.trim();
    if (raw === "") return null;
    const v = Number(raw);
    return isFinite(v) && v > 0 ? v : NaN;
  }
  // 校验止盈止损，返回 { tp, sl } 或 错误文本
  function readTpSl(side, ref) {
    const tp = readNum("tpIn"), sl = readNum("slIn");
    if (Number.isNaN(tp)) return side > 0 ? t("errTpLong") : t("errTpShort");
    if (Number.isNaN(sl)) return side > 0 ? t("errSlLong") : t("errSlShort");
    if (side > 0) {
      if (tp != null && tp <= ref) return t("errTpLong");
      if (sl != null && sl >= ref) return t("errSlLong");
    } else {
      if (tp != null && tp >= ref) return t("errTpShort");
      if (sl != null && sl <= ref) return t("errSlShort");
    }
    return { tp, sl };
  }

  function closePosition(exitPrice, reason) {
    const p = S.pos;
    if (!p) return null;
    const exitFee = exitPrice * p.qty * FEE;
    const gross = p.side * (exitPrice - p.entry) * p.qty;
    const net = gross - p.fees - exitFee;
    S.realized += gross - exitFee;  // 开仓手续费在开仓时已扣
    S.fees += exitFee;
    S.trades.push({
      side: p.side, qty: p.qty, entry: p.entry, exit: exitPrice,
      openIdx: p.openIdx, closeIdx: S.idx, pnl: net, reason,
    });
    S.markers.push({ idx: S.idx, price: exitPrice, kind: "close", side: p.side });
    S.pos = null;
    $("tpIn").value = ""; $("slIn").value = "";
    return net;
  }

  function open(side) {
    if (S.ended) return say(t("errEnded"), "err");
    const qty = readNum("qtyIn");
    if (qty == null || Number.isNaN(qty)) return say(t("errQty"), "err");
    const px = price();
    const r = readTpSl(side, px);
    if (typeof r === "string") return say(r, "err");

    // 反手：先平掉反向仓位
    if (S.pos && S.pos.side !== side) {
      closePosition(px, "reverse");
    }
    const curQty = S.pos ? S.pos.qty : 0;
    const eqNow = equity(px);
    const maxQty = Math.max(0, (eqNow * MAX_LEV) / px - curQty);
    if (qty > maxQty + 1e-9) return say(t("errMargin", fmtQty(Math.floor(maxQty * 1000) / 1000)), "err"), refresh();

    const fee = px * qty * FEE;
    S.realized -= fee;
    S.fees += fee;
    if (S.pos) {
      const p = S.pos;
      p.entry = (p.entry * p.qty + px * qty) / (p.qty + qty);
      p.qty += qty;
      p.fees += fee;
      p.tp = r.tp; p.sl = r.sl;
      say(t("msgAdd", fmtQty(qty), fmtPrice(px)));
    } else {
      S.pos = { side, qty, entry: px, openIdx: S.idx, fees: fee, tp: r.tp, sl: r.sl };
      say(t("msgOpen", side > 0 ? t("sideLong") : t("sideShort"), fmtQty(qty), fmtPrice(px)));
    }
    S.markers.push({ idx: S.idx, price: px, kind: "open", side });
    updateDD();
    refresh();
  }

  function manualClose() {
    if (S.ended) return say(t("errEnded"), "err");
    if (!S.pos) return say(t("errNoPos"), "err");
    const net = closePosition(price(), "manual");
    updateDD();
    say(t("msgClose", fmtMoney(net)), net >= 0 ? "ok" : "err");
    refresh();
  }

  function updateTpSl(clear) {
    if (S.ended) return say(t("errEnded"), "err");
    if (clear) {
      $("tpIn").value = ""; $("slIn").value = "";
      if (S.pos) { S.pos.tp = null; S.pos.sl = null; }
      say(t("msgTpSlCleared"));
      return refresh();
    }
    if (!S.pos) {
      // 空仓时只检查格式，开仓时按方向校验
      const tp = readNum("tpIn"), sl = readNum("slIn");
      if (Number.isNaN(tp) || Number.isNaN(sl)) return say(t("errPrice"), "err");
      return say(t("msgTpSlPending"));
    }
    const r = readTpSl(S.pos.side, price());
    if (typeof r === "string") return say(r, "err");
    S.pos.tp = r.tp; S.pos.sl = r.sl;
    say(t("msgTpSlSet"));
    refresh();
  }

  // 新 K 线出现后检查止盈止损（按 开→低→高→收 或 开→高→低→收 的路径判断先后）
  function checkTriggers(bar) {
    const p = S.pos;
    if (!p || (p.tp == null && p.sl == null)) return;
    const hitAt = (kind, px) => {
      const net = closePosition(px, kind);
      say(t(kind === "tp" ? "msgTP" : "msgSL", fmtPrice(px), fmtMoney(net)), net >= 0 ? "ok" : "err");
    };
    // 跳空：开盘价已越过
    if (p.side > 0) {
      if (p.sl != null && bar.o <= p.sl) return hitAt("sl", bar.o);
      if (p.tp != null && bar.o >= p.tp) return hitAt("tp", bar.o);
    } else {
      if (p.sl != null && bar.o >= p.sl) return hitAt("sl", bar.o);
      if (p.tp != null && bar.o <= p.tp) return hitAt("tp", bar.o);
    }
    const path = bar.c >= bar.o ? ["l", "h"] : ["h", "l"];
    for (const ext of path) {
      if (ext === "l") {
        if (p.side > 0 && p.sl != null && bar.l <= p.sl) return hitAt("sl", p.sl);
        if (p.side < 0 && p.tp != null && bar.l <= p.tp) return hitAt("tp", p.tp);
      } else {
        if (p.side > 0 && p.tp != null && bar.h >= p.tp) return hitAt("tp", p.tp);
        if (p.side < 0 && p.sl != null && bar.h >= p.sl) return hitAt("sl", p.sl);
      }
    }
  }

  function next() {
    if (S.ended) { say(t("errEnded"), "err"); return false; }
    if (S.idx >= N - 1) { finish(); return false; }
    S.idx++;
    checkTriggers(DATA[S.idx]);
    // 权益耗尽强制平仓
    if (S.pos && equity() <= 0) {
      const net = closePosition(price(), "liq");
      say(t("msgClose", fmtMoney(net)), "err");
    }
    updateDD();
    if (S.idx >= N - 1) finish();
    refresh();
    return true;
  }

  function finish() {
    if (S.ended) return;
    stopPlay();
    if (S.pos) closePosition(price(), "end");
    updateDD();
    S.ended = true;
    refresh();
    renderSummary();
    $("summary").hidden = false;
    $("againBtn").focus();
  }

  // ---------- 自动播放 ----------
  function startPlay() {
    if (S.ended) return say(t("errEnded"), "err");
    stopPlay();
    timer = setInterval(() => { if (!next()) stopPlay(); }, +$("speedSel").value);
    $("playBtn").textContent = t("pause");
    $("playBtn").classList.add("active");
  }
  function stopPlay() {
    if (timer) clearInterval(timer);
    timer = null;
    $("playBtn").textContent = t("play");
    $("playBtn").classList.remove("active");
  }
  const togglePlay = () => timer ? stopPlay() : startPlay();

  function restart() {
    stopPlay();
    resetState();
    $("summary").hidden = true;
    $("tpIn").value = ""; $("slIn").value = "";
    $("msg").textContent = "";
    refresh();
  }

  // ---------- 统计 ----------
  function stats() {
    const tr = S.trades;
    const wins = tr.filter((x) => x.pnl > 0);
    const losses = tr.filter((x) => x.pnl <= 0);
    const sumW = wins.reduce((a, x) => a + x.pnl, 0);
    const sumL = losses.reduce((a, x) => a + x.pnl, 0);
    return {
      n: tr.length,
      winRate: tr.length ? wins.length / tr.length : NaN,
      pf: sumL < 0 ? sumW / -sumL : (sumW > 0 ? Infinity : NaN),
      avgWin: wins.length ? sumW / wins.length : NaN,
      avgLoss: losses.length ? sumL / losses.length : NaN,
      best: tr.length ? Math.max(...tr.map((x) => x.pnl)) : NaN,
      worst: tr.length ? Math.min(...tr.map((x) => x.pnl)) : NaN,
      tpHits: tr.filter((x) => x.reason === "tp").length,
      slHits: tr.filter((x) => x.reason === "sl").length,
    };
  }

  const reasonText = (r) => ({ manual: t("reasonManual"), tp: t("reasonTP"), sl: t("reasonSL"), end: t("reasonEnd"), reverse: t("reasonReverse"), liq: t("reasonLiq") }[r] || r);
  const kv = (label, value, c = "") => `<dt>${label}</dt><dd class="${c}">${value}</dd>`;

  function renderPanel() {
    if (!S) return;
    const px = price();
    const p = S.pos;
    const fp = floatPnl();
    let h = "";
    if (p) {
      const notional = p.qty * px;
      h += kv(t("side"), `<span class="tag ${p.side > 0 ? "long" : "short"}">${p.side > 0 ? t("sideLong") : t("sideShort")}</span>`);
      h += kv(t("qty"), fmtQty(p.qty));
      h += kv(t("entry"), fmtPrice(p.entry));
      h += kv(t("mark"), fmtPrice(px));
      h += kv(t("floatPnl"), `${fmtMoney(fp)} (${fmtPct(p.side * (px - p.entry) / p.entry)})`, cls(fp));
      h += kv(t("tp"), fmtPrice(p.tp));
      h += kv(t("sl"), fmtPrice(p.sl));
      h += kv(t("leverage"), (notional / equity()).toFixed(2) + "×");
    } else {
      h += kv(t("side"), t("noPosition"));
      h += kv(t("mark"), fmtPrice(px));
      h += kv(t("floatPnl"), fmtMoney(0));
    }
    $("posBox").innerHTML = h;

    const st = stats();
    const eq = equity();
    let s = "";
    s += kv(t("balance"), fmtMoney(BALANCE, false));
    s += kv(t("equity"), fmtMoney(eq, false), cls(eq - BALANCE));
    s += kv(t("floatPnl"), fmtMoney(fp), cls(fp));
    s += kv(t("realized"), fmtMoney(S.realized), cls(S.realized));
    s += kv(t("winRate"), st.n ? `${fmtPct(st.winRate, false)} (${S.trades.filter((x) => x.pnl > 0).length}/${st.n})` : "—");
    s += kv(t("maxDD"), S.maxDD > 0 ? `${fmtMoney(-S.maxDD)} (${fmtPct(-S.maxDDPct)})` : "0.00", S.maxDD > 0 ? "neg" : "");
    s += kv(t("trades"), st.n);
    s += kv(t("fees"), fmtMoney(-S.fees));
    $("statBox").innerHTML = s;

    const rows = S.trades.map((x, i) => `<tr>
      <td>${i + 1}</td>
      <td><span class="tag ${x.side > 0 ? "long" : "short"}">${x.side > 0 ? t("sideLong") : t("sideShort")}</span> ${fmtQty(x.qty)}</td>
      <td title="${fmtTime(DATA[x.openIdx].t)}">${fmtPrice(x.entry)}</td>
      <td title="${fmtTime(DATA[x.closeIdx].t)}">${fmtPrice(x.exit)}</td>
      <td class="${cls(x.pnl)}">${fmtMoney(x.pnl)}</td>
      <td>${reasonText(x.reason)}</td>
    </tr>`).reverse().join("");
    $("tradeBody").innerHTML = rows || `<tr><td colspan="6" class="empty">${t("noTrades")}</td></tr>`;

    $("progText").textContent = `${S.idx + 1}/${N}`;
    $("progFill").style.width = ((S.idx + 1) / N * 100).toFixed(1) + "%";
  }

  function renderSummary() {
    const st = stats();
    const eq = equity();
    const pnl = eq - BALANCE;
    const ret = pnl / BALANCE;
    const hold = DATA[N - 1].c / DATA[START_BARS - 1].c - 1;
    $("sumHero").innerHTML = `
      <div><span class="lbl">${t("sumReturn")}</span><span class="big ${cls(ret)}">${fmtPct(ret)}</span></div>
      <div><span class="lbl">${t("sumPnl")}</span><span class="big ${cls(pnl)}">${fmtMoney(pnl)}</span></div>`;
    let h = "";
    h += kv(t("sumFinal"), fmtMoney(eq, false));
    h += kv(t("sumTrades"), st.n);
    h += kv(t("sumWin"), st.n ? fmtPct(st.winRate, false) : "—");
    h += kv(t("sumPF"), isFinite(st.pf) ? st.pf.toFixed(2) : st.pf === Infinity ? "∞" : "—");
    h += kv(t("sumAvgWin"), fmtMoney(st.avgWin), "pos");
    h += kv(t("sumAvgLoss"), fmtMoney(st.avgLoss), "neg");
    h += kv(t("sumBest"), fmtMoney(st.best), cls(st.best));
    h += kv(t("sumWorst"), fmtMoney(st.worst), cls(st.worst));
    h += kv(t("sumDD"), `${fmtMoney(-S.maxDD)} (${fmtPct(-S.maxDDPct)})`, S.maxDD > 0 ? "neg" : "");
    h += kv(t("sumHold"), fmtPct(hold), cls(hold));
    h += kv(t("sumTP"), st.tpHits);
    h += kv(t("sumSL"), st.slHits);
    h += kv(t("sumFees"), fmtMoney(-S.fees));
    $("sumBox").innerHTML = h;
    let c;
    if (!st.n) c = t("commentNoTrade");
    else if (ret > 0 && ret > hold && S.maxDDPct < 0.1) c = t("commentGreat");
    else if (ret > 0) c = t("commentProfit");
    else if (S.maxDDPct >= 0.1) c = t("commentLossDD");
    else c = t("commentLoss");
    $("sumComment").innerHTML = `<b>${t("sumComment")}：</b>${c}`;
  }

  // ---------- 图表 ----------
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  const view = { bars: 80, offset: 0, rightPad: 6, hover: null, w: 0, h: 0 };
  const AXIS_W = 74, TIME_H = 22;
  let colors = {};
  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    ["--up", "--down", "--text", "--muted", "--grid", "--line", "--panel", "--panel-2", "--cross", "--tp", "--sl", "--entry", "--accent"].forEach((k) => {
      colors[k.slice(2)] = cs.getPropertyValue(k).trim();
    });
  }

  function resize() {
    const r = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    view.w = Math.max(100, r.width);
    view.h = Math.max(100, r.height);
    canvas.width = Math.round(view.w * dpr);
    canvas.height = Math.round(view.h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function niceStep(range, target) {
    const raw = range / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const n = raw / mag;
    return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
  }

  function layout() {
    const plotW = view.w - AXIS_W;
    const totalH = view.h - TIME_H;
    const volH = Math.round(totalH * 0.18);
    const priceH = totalH - volH - 6;
    const maxOffset = Math.max(0, S.idx - 10);
    view.offset = Math.min(Math.max(0, view.offset), maxOffset);
    const end = S.idx - view.offset;
    const bars = Math.min(view.bars, end + 1);   // 数据不足一屏时按实际根数铺满
    const start = end - bars + 1;
    const slot = plotW / (bars + view.rightPad);
    const xOf = (i) => (i - start) * slot + slot / 2;
    view.L = { slot, start };
    return { plotW, priceH, volH, volTop: priceH + 6, totalH, start, end, slot, xOf };
  }

  function draw() {
    if (!S || !view.w) return;
    readColors();
    const L = layout();
    const { plotW, priceH, volH, volTop, start, end, slot, xOf } = L;
    ctx.clearRect(0, 0, view.w, view.h);

    // 价格范围
    let hi = -Infinity, lo = Infinity, vmax = 0;
    for (let i = start; i <= end; i++) {
      const d = DATA[i];
      if (d.h > hi) hi = d.h;
      if (d.l < lo) lo = d.l;
      if (d.v > vmax) vmax = d.v;
    }
    const levels = [];
    if (S.pos) {
      levels.push({ p: S.pos.entry, c: colors.entry, label: t("entry") });
      if (S.pos.tp != null) levels.push({ p: S.pos.tp, c: colors.tp, label: "TP" });
      if (S.pos.sl != null) levels.push({ p: S.pos.sl, c: colors.sl, label: "SL" });
    }
    levels.forEach((lv) => { hi = Math.max(hi, lv.p); lo = Math.min(lo, lv.p); });
    const padP = (hi - lo) * 0.08 || hi * 0.01;
    hi += padP; lo -= padP;
    const yOf = (p) => ((hi - p) / (hi - lo)) * priceH;
    const pOf = (y) => hi - (y / priceH) * (hi - lo);
    L.yOf = yOf; L.pOf = pOf;

    // 网格与价格刻度
    ctx.font = "11px ui-monospace, Menlo, monospace";
    ctx.textBaseline = "middle";
    const step = niceStep(hi - lo, Math.max(3, Math.floor(priceH / 55)));
    ctx.strokeStyle = colors.grid; ctx.lineWidth = 1;
    ctx.fillStyle = colors.muted; ctx.textAlign = "left";
    for (let p = Math.ceil(lo / step) * step; p <= hi; p += step) {
      const y = Math.round(yOf(p)) + 0.5;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke();
      ctx.fillText(p.toLocaleString("en-US", { maximumFractionDigits: step < 1 ? 2 : 0 }), plotW + 6, y);
    }
    // 时间刻度
    const every = Math.max(1, Math.ceil(80 / slot));
    const tickEvery = [1, 2, 3, 4, 6, 12, 24, 48, 72].find((x) => x >= every) || 96;
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (let i = start; i <= end; i++) {
      const d = new Date(DATA[i].t * 1000);
      if (d.getHours() % Math.min(tickEvery, 24) !== 0) continue;
      if (tickEvery > 24 && Math.floor(DATA[i].t / 86400) % (tickEvery / 24) !== 0) continue;
      const x = Math.round(xOf(i)) + 0.5;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, L.totalH); ctx.stroke();
      const label = d.getHours() === 0 ? pad(d.getMonth() + 1) + "-" + pad(d.getDate()) : fmtTime(DATA[i].t, false);
      ctx.fillText(label, x, L.totalH + 5);
    }
    // 分隔线
    ctx.strokeStyle = colors.line;
    ctx.beginPath(); ctx.moveTo(plotW + 0.5, 0); ctx.lineTo(plotW + 0.5, L.totalH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, L.totalH + 0.5); ctx.lineTo(view.w, L.totalH + 0.5); ctx.stroke();

    // K 线与成交量
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, plotW, L.totalH); ctx.clip();
    const bw = Math.max(1, Math.min(18, slot * 0.7));
    for (let i = start; i <= end; i++) {
      const d = DATA[i];
      const x = xOf(i);
      const up = d.c >= d.o;
      const col = up ? colors.up : colors.down;
      ctx.strokeStyle = col; ctx.fillStyle = col;
      const xc = Math.round(x) + 0.5;
      ctx.beginPath(); ctx.moveTo(xc, yOf(d.h)); ctx.lineTo(xc, yOf(d.l)); ctx.stroke();
      const y1 = yOf(Math.max(d.o, d.c)), y2 = yOf(Math.min(d.o, d.c));
      ctx.fillRect(Math.round(x - bw / 2), Math.round(y1), Math.round(bw), Math.max(1, Math.round(y2 - y1)));
      // 成交量
      const vh = (d.v / vmax) * (volH - 4);
      ctx.globalAlpha = 0.45;
      ctx.fillRect(Math.round(x - bw / 2), volTop + volH - vh, Math.round(bw), vh);
      ctx.globalAlpha = 1;
    }

    // 交易标记
    for (const m of S.markers) {
      if (m.idx < start || m.idx > end) continue;
      const x = xOf(m.idx), d = DATA[m.idx];
      const s = Math.max(5, Math.min(8, slot * 0.45));
      if (m.kind === "open") {
        const isLong = m.side > 0;
        ctx.fillStyle = isLong ? colors.up : colors.down;
        const y = isLong ? yOf(d.l) + 6 : yOf(d.h) - 6;
        ctx.beginPath();
        if (isLong) { ctx.moveTo(x, y); ctx.lineTo(x - s, y + s * 1.4); ctx.lineTo(x + s, y + s * 1.4); }
        else { ctx.moveTo(x, y); ctx.lineTo(x - s, y - s * 1.4); ctx.lineTo(x + s, y - s * 1.4); }
        ctx.closePath(); ctx.fill();
      } else {
        const y = yOf(m.price);
        ctx.strokeStyle = colors.text; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(x - s * 0.7, y - s * 0.7); ctx.lineTo(x + s * 0.7, y + s * 0.7);
        ctx.moveTo(x + s * 0.7, y - s * 0.7); ctx.lineTo(x - s * 0.7, y + s * 0.7); ctx.stroke();
        ctx.lineWidth = 1;
      }
    }
    ctx.restore();

    // 持仓线（开仓价 / 止盈 / 止损）
    const axisTag = (y, text, bg, fg = "#fff") => {
      ctx.fillStyle = bg;
      ctx.fillRect(plotW + 1, y - 9, AXIS_W - 1, 18);
      ctx.fillStyle = fg; ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.fillText(text, plotW + 6, y);
    };
    ctx.font = "11px ui-monospace, Menlo, monospace";
    for (const lv of levels) {
      const y = Math.round(yOf(lv.p)) + 0.5;
      ctx.strokeStyle = lv.c; ctx.setLineDash([6, 4]);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = lv.c; ctx.textAlign = "left"; ctx.textBaseline = "bottom";
      ctx.fillText(`${lv.label} ${fmtPrice(lv.p)}`, 6, y - 2);
      axisTag(y, fmtPrice(lv.p), lv.c);
    }

    // 最新价线
    const last = DATA[S.idx];
    const ly = Math.round(yOf(last.c)) + 0.5;
    const lc = last.c >= last.o ? colors.up : colors.down;
    ctx.strokeStyle = lc; ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(0, ly); ctx.lineTo(plotW, ly); ctx.stroke();
    ctx.setLineDash([]);
    axisTag(ly, fmtPrice(last.c), lc);

    // 十字光标
    const hv = view.hover;
    if (hv && hv.x < plotW && hv.y < L.totalH) {
      ctx.strokeStyle = colors.cross; ctx.setLineDash([4, 4]);
      const i = Math.round((hv.x - slot / 2) / slot + start);
      const ci = Math.min(end, Math.max(start, i));
      const cx = Math.round(xOf(ci)) + 0.5;
      ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, L.totalH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, hv.y + 0.5); ctx.lineTo(plotW, hv.y + 0.5); ctx.stroke();
      ctx.setLineDash([]);
      if (hv.y < priceH) axisTag(hv.y, fmtPrice(pOf(hv.y)), colors.muted);
      const tl = fmtTime(DATA[ci].t);
      ctx.font = "11px ui-monospace, Menlo, monospace";
      const tw = ctx.measureText(tl).width + 10;
      const tx = Math.min(Math.max(cx - tw / 2, 0), plotW - tw);
      ctx.fillStyle = colors.muted; ctx.fillRect(tx, L.totalH + 1, tw, TIME_H - 1);
      ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(tl, tx + tw / 2, L.totalH + TIME_H / 2 + 1);
      showOhlc(ci);
    } else {
      showOhlc(S.idx);
    }
  }

  function showOhlc(i) {
    const d = DATA[i];
    const prev = i > 0 ? DATA[i - 1].c : d.o;
    const chg = (d.c - prev) / prev;
    const c = d.c >= d.o ? "up" : "down";
    $("ohlc").innerHTML = `<span>BTC/USDT · 1h · ${fmtTime(d.t)}</span>` +
      ["o", "h", "l", "c"].map((k) => `<span>${t(k)} <b class="${c}">${fmtPrice(d[k])}</b></span>`).join("") +
      `<span class="${chg >= 0 ? "up" : "down"}">${fmtPct(chg)}</span>` +
      `<span>${t("v")} <b>${d.v.toFixed(0)}</b></span>`;
  }

  // 图表交互：滚轮缩放、拖动平移、双击回到最新
  let drag = null;
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const f = e.deltaY > 0 ? 1.12 : 1 / 1.12;
    view.bars = Math.round(Math.min(N, Math.max(20, view.bars * f)));
    draw();
  }, { passive: false });
  canvas.addEventListener("pointerdown", (e) => {
    drag = { x: e.clientX, offset: view.offset, id: e.pointerId };
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
  });
  canvas.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    view.hover = { x: e.clientX - r.left, y: e.clientY - r.top };
    if (drag) {
      const slot = view.L ? view.L.slot : (view.w - AXIS_W) / (view.bars + view.rightPad);
      view.offset = Math.round(drag.offset + (e.clientX - drag.x) / slot);
    }
    draw();
  });
  const endDrag = () => { drag = null; };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
  canvas.addEventListener("pointerleave", () => { if (!drag) { view.hover = null; draw(); } });
  canvas.addEventListener("dblclick", () => { view.offset = 0; draw(); });

  // ---------- 刷新 ----------
  function refresh() {
    renderPanel();
    draw();
  }

  // ---------- 主题 ----------
  function initTheme() {
    let th = store.get("kr_theme");
    if (!th) th = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    document.documentElement.dataset.theme = th;
  }
  function toggleTheme() {
    const th = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = th;
    store.set("kr_theme", th);
    draw();
  }

  // ---------- 绑定 ----------
  function bind() {
    $("nextBtn").addEventListener("click", () => next());
    $("playBtn").addEventListener("click", togglePlay);
    $("restartBtn").addEventListener("click", restart);
    $("speedSel").addEventListener("change", () => { if (timer) startPlay(); });
    $("longBtn").addEventListener("click", () => open(1));
    $("shortBtn").addEventListener("click", () => open(-1));
    $("closeBtn").addEventListener("click", manualClose);
    $("tpslBtn").addEventListener("click", () => updateTpSl(false));
    $("tpslClearBtn").addEventListener("click", () => updateTpSl(true));
    $("againBtn").addEventListener("click", restart);
    $("sumCloseBtn").addEventListener("click", () => { $("summary").hidden = true; });
    $("summary").addEventListener("click", (e) => { if (e.target.id === "summary") $("summary").hidden = true; });
    $("themeBtn").addEventListener("click", toggleTheme);

    const sel = $("langSel");
    sel.innerHTML = I18N.langs.map(([v, n]) => `<option value="${v}">${n}</option>`).join("");
    sel.value = lang;
    sel.addEventListener("change", () => { lang = sel.value; store.set("kr_lang", lang); applyLang(); });

    document.addEventListener("keydown", (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (!$("summary").hidden) {
        if (e.key === "Escape") $("summary").hidden = true;
        return;
      }
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "select" || tag === "textarea") return;
      const k = e.key.toLowerCase();
      if (e.code === "Space" || k === " ") {
        e.preventDefault();
        next();
      } else if (k === "p") togglePlay();
      else if (k === "b") open(1);
      else if (k === "s") open(-1);
      else if (k === "c") manualClose();
    });

    if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas.parentElement);
    window.addEventListener("resize", resize);
  }

  // ---------- 启动 ----------
  if (!N) {
    document.body.insertAdjacentHTML("afterbegin", '<p style="padding:16px;color:#ef5350">data.js 未加载 / data.js not loaded</p>');
    return;
  }
  initTheme();
  lang = pickLang();
  resetState();
  bind();
  applyLang();
  resize();

  // 供自检脚本使用
  window.__replay = { get state() { return S; }, next, open, manualClose, updateTpSl, restart, finish, startPlay, stopPlay, equity };
})();
