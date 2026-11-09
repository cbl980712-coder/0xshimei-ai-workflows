(function () {
  "use strict";

  // ---------- 常量 ----------
  var DATA = (window.KLINE_DATA || []).map(function (b) {
    return { t: b[0], o: b[1], h: b[2], l: b[3], c: b[4], v: b[5] };
  });
  var TOTAL = DATA.length;
  var START_BARS = Math.min(50, TOTAL);
  var INIT_BALANCE = 10000;
  var FEE = 0.0005; // 单边手续费
  var MAX_LEV = 10;
  var LANGS = ["zh-CN", "en", "zh-TW", "ja", "ko"];

  function $(id) { return document.getElementById(id); }

  // ---------- 多语言 ----------
  var lang = "zh-CN";
  function store(key, val) {
    try {
      if (val === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, val);
    } catch (e) { /* 隐私模式下可能不可用，忽略 */ }
    return null;
  }
  function detectLang() {
    var saved = store("kreplay_lang");
    if (saved && LANGS.indexOf(saved) >= 0) return saved;
    var n = (navigator.language || "en").toLowerCase();
    if (n.indexOf("zh") === 0) return /tw|hk|mo|hant/.test(n) ? "zh-TW" : "zh-CN";
    if (n.indexOf("ja") === 0) return "ja";
    if (n.indexOf("ko") === 0) return "ko";
    return "en";
  }
  function t(key) {
    var dict = window.I18N[lang] || window.I18N["zh-CN"];
    var s = dict[key];
    if (s === undefined) s = window.I18N["zh-CN"][key];
    if (s === undefined) return key;
    var args = arguments;
    return s.replace(/\{(\d)\}/g, function (_, i) {
      var v = args[Number(i) + 1];
      return v === undefined ? "" : v;
    });
  }
  function applyI18n() {
    document.documentElement.lang = lang;
    document.title = t("title");
    var i, els;
    els = document.querySelectorAll("[data-i18n]");
    for (i = 0; i < els.length; i++) els[i].textContent = t(els[i].getAttribute("data-i18n"));
    els = document.querySelectorAll("[data-i18n-aria]");
    for (i = 0; i < els.length; i++) els[i].setAttribute("aria-label", t(els[i].getAttribute("data-i18n-aria")));
    els = document.querySelectorAll("[data-i18n-ph]");
    for (i = 0; i < els.length; i++) els[i].setAttribute("placeholder", t(els[i].getAttribute("data-i18n-ph")));
    els = document.querySelectorAll("[data-i18n-title]");
    for (i = 0; i < els.length; i++) els[i].setAttribute("title", t(els[i].getAttribute("data-i18n-title")));
  }

  // ---------- 格式化 ----------
  function fmtPrice(x) {
    return x.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }
  function fmtMoney(x) {
    return x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtSigned(x) {
    var r = Math.round(x * 100) / 100;
    return (r > 0 ? "+" : r < 0 ? "-" : "") + fmtMoney(Math.abs(r));
  }
  function fmtPct(x) {
    var r = Math.round(x * 10000) / 100;
    return (r > 0 ? "+" : r < 0 ? "-" : "") + Math.abs(r).toFixed(2) + "%";
  }
  function pad2(n) { return n < 10 ? "0" + n : "" + n; }
  function fmtTime(ms) {
    var d = new Date(ms);
    return pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " + pad2(d.getHours()) + ":00";
  }
  function signClass(x) { return x > 0.004 ? "pos-up" : x < -0.004 ? "pos-down" : ""; }

  // ---------- 状态 ----------
  var S; // 回放与账户
  var timer = null;
  var view = { slot: 8, offset: 0, hover: null }; // slot: 每根占的像素；offset: 向左回看的根数
  var lastMsg = null;

  function newState() {
    return {
      idx: START_BARS, // 已显示的根数
      balance: INIT_BALANCE, // 已结算余额
      pos: null,
      trades: [],
      fees: 0,
      peak: INIT_BALANCE,
      maxDD: 0, // 比例
      maxDDAbs: 0,
      finished: false,
    };
  }
  function lastBar() { return DATA[S.idx - 1]; }
  function floatPnl(price) {
    if (!S.pos) return 0;
    return S.pos.side * (price - S.pos.entry) * S.pos.qty - S.pos.feeOpen;
  }
  function equity() { return S.balance + floatPnl(lastBar().c); }
  function trackDrawdown() {
    var eq = equity();
    if (eq > S.peak) S.peak = eq;
    var dd = S.peak > 0 ? (S.peak - eq) / S.peak : 0;
    if (dd > S.maxDD) { S.maxDD = dd; S.maxDDAbs = S.peak - eq; }
  }

  // ---------- 提示 ----------
  function setMsg(type, key) {
    lastMsg = { type: type, key: key, args: Array.prototype.slice.call(arguments, 2) };
    renderMsg();
  }
  function clearMsg() { lastMsg = null; renderMsg(); }
  function renderMsg() {
    var el = $("msg");
    if (!lastMsg) { el.textContent = ""; el.className = "msg"; return; }
    var args = lastMsg.args.map(function (a) { return typeof a === "function" ? a() : a; });
    el.textContent = t.apply(null, [lastMsg.key].concat(args));
    el.className = "msg " + lastMsg.type;
  }

  // ---------- 交易 ----------
  function readLevel(inp) {
    var raw = inp.value.trim();
    if (raw === "") return null;
    var v = Number(raw);
    if (!isFinite(v) || v <= 0) return NaN;
    return v;
  }
  // 校验止盈止损；通过返回 {tp, sl}，否则提示并返回 null
  function checkLevels(side, price) {
    var tp = readLevel($("tpInp")), sl = readLevel($("slInp"));
    if ((tp !== null && isNaN(tp)) || (sl !== null && isNaN(sl))) { setMsg("err", "mBadNumber"); return null; }
    var p = fmtPrice(price);
    if (side === 1) {
      if (tp !== null && tp <= price) { setMsg("err", "mTpLong", p); return null; }
      if (sl !== null && sl >= price) { setMsg("err", "mSlLong", p); return null; }
    } else {
      if (tp !== null && tp >= price) { setMsg("err", "mTpShort", p); return null; }
      if (sl !== null && sl <= price) { setMsg("err", "mSlShort", p); return null; }
    }
    return { tp: tp, sl: sl };
  }
  function calcLiq(pos) {
    // 亏完全部余额的价格；1 倍以内做多不会强平
    var liq = pos.entry - pos.side * (S.balance - pos.feeOpen) / pos.qty;
    return liq > 0 ? liq : null;
  }
  function openPosition(side) {
    if (S.finished) { setMsg("err", "mEnded"); return; }
    if (S.pos) { setMsg("err", "mHasPos"); return; }
    var eq = equity();
    if (eq < 1) { setMsg("err", "mNoFunds"); return; }
    var amount = Number($("amountInp").value);
    if (!isFinite(amount) || amount <= 0) { setMsg("err", "mAmount"); return; }
    var cap = Math.floor(eq * MAX_LEV * 100) / 100;
    if (amount > cap) { setMsg("err", "mAmountMax", fmtMoney(cap)); return; }
    var price = lastBar().c;
    var lv = checkLevels(side, price);
    if (!lv) return;
    var qty = amount / price;
    var pos = {
      side: side, qty: qty, entry: price, entryIdx: S.idx - 1, amount: amount,
      tp: lv.tp, sl: lv.sl, feeOpen: amount * FEE, liq: null,
    };
    pos.liq = calcLiq(pos);
    S.pos = pos;
    S.fees += pos.feeOpen;
    trackDrawdown();
    setMsg("ok", side === 1 ? "mOpenedLong" : "mOpenedShort", qty.toFixed(4), fmtPrice(price));
    renderAll();
  }
  function closePosition(price, reason) {
    var p = S.pos;
    if (!p) return null;
    var feeClose = p.qty * price * FEE;
    var pnl = p.side * (price - p.entry) * p.qty - p.feeOpen - feeClose;
    if (reason === "liq" || pnl < -S.balance) pnl = -S.balance; // 最多亏完余额
    S.balance += pnl;
    S.fees += feeClose;
    var tr = {
      side: p.side, qty: p.qty, entry: p.entry, exit: price,
      entryIdx: p.entryIdx, exitIdx: S.idx - 1, pnl: pnl, reason: reason,
    };
    S.trades.push(tr);
    S.pos = null;
    $("tpInp").value = "";
    $("slInp").value = "";
    trackDrawdown();
    setMsg(pnl >= 0 ? "ok" : "err", "mClosed", function () { return t("r_" + reason); }, fmtSigned(pnl));
    return tr;
  }
  function manualClose() {
    if (!S.pos) { setMsg("err", S.finished ? "mEnded" : "mNoPos"); return; }
    closePosition(lastBar().c, "manual");
    renderAll();
  }
  function updateTpSl() {
    if (!S.pos) { setMsg("err", S.finished ? "mEnded" : "mNoPos"); return; }
    var lv = checkLevels(S.pos.side, lastBar().c);
    if (!lv) return;
    S.pos.tp = lv.tp;
    S.pos.sl = lv.sl;
    setMsg("ok", "mTpSlUpdated");
    renderAll();
  }
  // 新 K 线出来后检查止损 / 强平 / 止盈
  function checkTriggers(bar) {
    var p = S.pos;
    if (!p) return;
    var stop = p.sl, stopReason = "sl";
    if (p.side === 1) {
      if (p.liq !== null && (stop === null || p.liq >= stop)) { stop = p.liq; stopReason = "liq"; }
      if (stop !== null && bar.l <= stop) {
        closePosition(stopReason === "liq" ? stop : Math.min(bar.o, stop), stopReason);
      } else if (p.tp !== null && bar.h >= p.tp) {
        closePosition(Math.max(bar.o, p.tp), "tp");
      }
    } else {
      if (p.liq !== null && (stop === null || p.liq <= stop)) { stop = p.liq; stopReason = "liq"; }
      if (stop !== null && bar.h >= stop) {
        closePosition(stopReason === "liq" ? stop : Math.max(bar.o, stop), stopReason);
      } else if (p.tp !== null && bar.l <= p.tp) {
        closePosition(Math.min(bar.o, p.tp), "tp");
      }
    }
  }

  // ---------- 回放 ----------
  function step() {
    if (S.finished) { stopAuto(); openSummary(); return; }
    if (S.idx >= TOTAL) { finish(); return; }
    S.idx++;
    view.offset = 0;
    view.hover = null;
    checkTriggers(lastBar());
    trackDrawdown();
    if (S.idx >= TOTAL) { finish(); return; }
    renderAll();
  }
  function finish() {
    stopAuto();
    if (S.pos) closePosition(lastBar().c, "end");
    S.finished = true;
    renderAll();
    openSummary();
  }
  function startAuto() {
    if (S.finished) { openSummary(); return; }
    stopAuto();
    timer = setInterval(step, Number($("speedSel").value) || 400);
    renderPlayBtn();
  }
  function stopAuto() {
    if (timer) { clearInterval(timer); timer = null; }
    renderPlayBtn();
  }
  function toggleAuto() { if (timer) stopAuto(); else startAuto(); }
  function reset() {
    stopAuto();
    S = newState();
    view.offset = 0;
    view.hover = null;
    $("tpInp").value = "";
    $("slInp").value = "";
    $("amountInp").value = INIT_BALANCE;
    closeSummary();
    setMsg("ok", "mReset");
    renderAll();
  }

  // ---------- 右侧面板 ----------
  function setVal(id, text, cls) {
    var el = $(id);
    el.textContent = text;
    el.className = cls || "";
  }
  function winRate() {
    if (!S.trades.length) return null;
    var w = 0;
    for (var i = 0; i < S.trades.length; i++) if (S.trades[i].pnl > 0) w++;
    return w / S.trades.length;
  }
  function renderPanel() {
    var price = lastBar().c;
    var fl = floatPnl(price);
    var realized = S.balance - INIT_BALANCE;
    setVal("sEquity", fmtMoney(equity()) + " USDT");
    if (S.pos) {
      var p = S.pos;
      setVal("sPos", t(p.side === 1 ? "posLong" : "posShort") + " " + p.qty.toFixed(4) + " BTC", p.side === 1 ? "pos-up" : "pos-down");
      setVal("sEntry", fmtPrice(p.entry));
      setVal("sTpSl", (p.tp === null ? "—" : fmtPrice(p.tp)) + " / " + (p.sl === null ? "—" : fmtPrice(p.sl)));
      setVal("sFloat", fmtSigned(fl) + " (" + fmtPct(fl / p.amount) + ")", signClass(fl));
    } else {
      setVal("sPos", t("none"));
      setVal("sEntry", "—");
      setVal("sTpSl", "—");
      setVal("sFloat", "0.00");
    }
    setVal("sReal", fmtSigned(realized), signClass(realized));
    var wr = winRate();
    setVal("sWin", wr === null ? "—" : (wr * 100).toFixed(1) + "%");
    setVal("sDD", S.maxDD > 0 ? "-" + (S.maxDD * 100).toFixed(2) + "% (" + fmtMoney(S.maxDDAbs) + ")" : "0.00%", S.maxDD > 0 ? "pos-down" : "");
    setVal("sCount", String(S.trades.length));

    // 交易记录（新的在上）
    var body = $("tradeBody");
    body.textContent = "";
    for (var i = S.trades.length - 1; i >= 0; i--) {
      var tr = S.trades[i];
      var row = document.createElement("tr");
      var cells = [
        [String(i + 1), ""],
        [t(tr.side === 1 ? "posLong" : "posShort"), tr.side === 1 ? "pos-up" : "pos-down"],
        [fmtPrice(tr.entry), ""],
        [fmtPrice(tr.exit), ""],
        [fmtSigned(tr.pnl), signClass(tr.pnl)],
        [t("r_" + tr.reason), ""],
      ];
      for (var k = 0; k < cells.length; k++) {
        var td = document.createElement("td");
        td.textContent = cells[k][0];
        if (cells[k][1]) td.className = cells[k][1];
        row.appendChild(td);
      }
      body.appendChild(row);
    }
    $("tradeTable").hidden = S.trades.length === 0;
    $("noTrades").hidden = S.trades.length > 0;

    $("progText").textContent = t("progress", S.idx, TOTAL);
    $("progFill").style.width = (S.idx / TOTAL * 100).toFixed(2) + "%";
    $("summaryBtn").hidden = !S.finished;
  }
  function renderPlayBtn() {
    $("playBtn").textContent = t(timer ? "pause" : "play");
  }

  // ---------- 总结 ----------
  function buildSummary() {
    var ret = S.balance / INIT_BALANCE - 1;
    var hold = DATA[TOTAL - 1].c / DATA[START_BARS - 1].c - 1;
    var wins = [], losses = [], best = null, worst = null;
    S.trades.forEach(function (tr) {
      if (tr.pnl > 0) wins.push(tr.pnl); else losses.push(tr.pnl);
      if (best === null || tr.pnl > best) best = tr.pnl;
      if (worst === null || tr.pnl < worst) worst = tr.pnl;
    });
    function avg(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : null; }
    var aw = avg(wins), al = avg(losses);
    var payoff = aw !== null && al !== null && al < 0 ? aw / Math.abs(al) : null;
    var wr = winRate();

    var hero = $("sumReturn");
    hero.textContent = fmtPct(ret);
    hero.className = signClass(ret);
    $("sumVerdict").textContent = !S.trades.length
      ? t("verdictNoTrade", fmtPct(hold))
      : t(ret > hold ? "verdictBeat" : "verdictLose", fmtPct(hold));

    var rows = [
      ["sumFinal", fmtMoney(S.balance) + " USDT", ""],
      ["realized", fmtSigned(S.balance - INIT_BALANCE), signClass(S.balance - INIT_BALANCE)],
      ["tradeCount", String(S.trades.length), ""],
      ["winRate", wr === null ? "—" : (wr * 100).toFixed(1) + "%", ""],
      ["maxDD", (S.maxDD > 0 ? "-" : "") + (S.maxDD * 100).toFixed(2) + "%", S.maxDD > 0 ? "pos-down" : ""],
      ["avgWin", aw === null ? "—" : fmtSigned(aw), aw === null ? "" : "pos-up"],
      ["avgLoss", al === null ? "—" : fmtSigned(al), al === null ? "" : signClass(al)],
      ["payoff", payoff === null ? "—" : payoff.toFixed(2), ""],
      ["best", best === null ? "—" : fmtSigned(best), best === null ? "" : signClass(best)],
      ["worst", worst === null ? "—" : fmtSigned(worst), worst === null ? "" : signClass(worst)],
      ["sumFees", fmtMoney(S.fees), ""],
      ["hold", fmtPct(hold), signClass(hold)],
    ];
    var dl = $("sumStats");
    dl.textContent = "";
    rows.forEach(function (r) {
      var div = document.createElement("div");
      var dt = document.createElement("dt");
      var dd = document.createElement("dd");
      dt.textContent = t(r[0]);
      dd.textContent = r[1];
      if (r[2]) dd.className = r[2];
      div.appendChild(dt);
      div.appendChild(dd);
      dl.appendChild(div);
    });
  }
  function openSummary() {
    buildSummary();
    var dlg = $("summaryDlg");
    if (dlg.open) return;
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  }
  function closeSummary() {
    var dlg = $("summaryDlg");
    if (!dlg.open) return;
    if (typeof dlg.close === "function") dlg.close();
    else dlg.removeAttribute("open");
  }

  // ---------- K 线图 ----------
  var canvas = $("chart");
  var ctx = canvas.getContext("2d");
  var G = { w: 0, h: 0, plotW: 0, axisW: 66, timeH: 22, top: 30, priceH: 0, volTop: 0, volH: 0, last: 0, first: 0, lo: 0, hi: 1 };
  var PAD_BARS = 2;

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function resizeCanvas() {
    var wrap = $("chartWrap");
    var w = wrap.clientWidth, h = wrap.clientHeight;
    if (!w || !h) return;
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var firstTime = G.w === 0;
    G.w = w; G.h = h;
    G.axisW = w < 520 ? 58 : 66;
    G.plotW = w - G.axisW;
    G.volH = Math.round(h * 0.16);
    G.volTop = h - G.timeH - G.volH;
    G.priceH = G.volTop - 8 - G.top;
    if (firstTime) view.slot = Math.max(5, Math.min(12, G.plotW / 90));
    drawChart();
  }
  function clampView() {
    view.slot = Math.max(3, Math.min(32, view.slot));
    var maxOff = Math.max(0, S.idx - 10);
    view.offset = Math.max(0, Math.min(maxOff, view.offset));
  }
  function barX(i) { return G.plotW - (G.last - i + 0.5 + PAD_BARS) * view.slot; }
  function priceY(p) { return G.top + (G.hi - p) / (G.hi - G.lo) * G.priceH; }
  function yPrice(y) { return G.hi - (y - G.top) / G.priceH * (G.hi - G.lo); }
  function indexAt(x) { return Math.floor(G.last + PAD_BARS + 1 - (G.plotW - x) / view.slot); }
  function niceStep(range, target) {
    var raw = range / target;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var n = raw / mag;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
  }
  function axisTag(y, text, bg, fg) {
    if (y < G.top - 8 || y > G.volTop) return;
    ctx.fillStyle = bg;
    ctx.fillRect(G.plotW, y - 9, G.axisW, 18);
    ctx.fillStyle = fg;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(text, G.plotW + 5, y);
  }
  function hLine(y, color, dash) {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash(dash || []);
    ctx.beginPath();
    ctx.moveTo(0, Math.round(y) + 0.5);
    ctx.lineTo(G.plotW, Math.round(y) + 0.5);
    ctx.stroke();
    ctx.restore();
  }

  function drawChart() {
    if (!G.w) return;
    clampView();
    var C = {
      card: cssVar("--card"), grid: cssVar("--grid"), line: cssVar("--line"),
      text: cssVar("--text"), muted: cssVar("--muted"),
      up: cssVar("--up"), down: cssVar("--down"), accent: cssVar("--accent"),
    };
    var slot = view.slot;
    ctx.clearRect(0, 0, G.w, G.h);
    ctx.fillStyle = C.card;
    ctx.fillRect(0, 0, G.w, G.h);
    ctx.font = "11px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

    G.last = S.idx - 1 - Math.round(view.offset);
    var count = Math.ceil(G.plotW / slot) + 1;
    G.first = Math.max(0, G.last - count);

    // 价格范围
    var lo = Infinity, hi = -Infinity, vmax = 0, i, b;
    for (i = G.first; i <= G.last; i++) {
      b = DATA[i];
      if (b.l < lo) lo = b.l;
      if (b.h > hi) hi = b.h;
      if (b.v > vmax) vmax = b.v;
    }
    var cur = lastBar().c;
    if (S.pos) {
      [S.pos.entry, S.pos.tp, S.pos.sl].forEach(function (lv) {
        if (lv !== null && Math.abs(lv - cur) / cur < 0.06) {
          if (lv < lo) lo = lv;
          if (lv > hi) hi = lv;
        }
      });
    }
    var padP = (hi - lo) * 0.07 || hi * 0.01;
    G.lo = lo - padP; G.hi = hi + padP;

    // 横向网格和价格刻度
    var stepP = niceStep(G.hi - G.lo, Math.max(3, Math.floor(G.priceH / 55)));
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (var p = Math.ceil(G.lo / stepP) * stepP; p <= G.hi; p += stepP) {
      var gy = priceY(p);
      hLine(gy, C.grid);
      ctx.fillStyle = C.muted;
      ctx.fillText(fmtPrice(p), G.plotW + 5, gy);
    }

    // 时间刻度
    var steps = [1, 2, 3, 4, 6, 12, 24, 48, 96];
    var stepH = steps[steps.length - 1];
    for (i = 0; i < steps.length; i++) { if (steps[i] * slot >= 64) { stepH = steps[i]; break; } }
    var tzMs = new Date(DATA[G.last].t).getTimezoneOffset() * 60000;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (i = G.first; i <= G.last; i++) {
      var localH = Math.floor((DATA[i].t - tzMs) / 3600000);
      if (localH % stepH !== 0) continue;
      var tx = barX(i);
      if (tx < 24 || tx > G.plotW - 20) continue;
      ctx.strokeStyle = C.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(Math.round(tx) + 0.5, G.top - 8);
      ctx.lineTo(Math.round(tx) + 0.5, G.h - G.timeH);
      ctx.stroke();
      var d = new Date(DATA[i].t);
      ctx.fillStyle = C.muted;
      ctx.fillText(d.getHours() === 0 ? pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) : pad2(d.getHours()) + ":00", tx, G.h - G.timeH / 2);
    }

    // 蜡烛和成交量
    var bodyW = Math.max(1, Math.floor(slot * 0.72));
    if (bodyW > 2 && bodyW % 2 === 0) bodyW -= 1;
    for (i = G.first; i <= G.last; i++) {
      b = DATA[i];
      var x = Math.round(barX(i));
      if (x < -slot) continue;
      var up = b.c >= b.o;
      ctx.fillStyle = up ? C.up : C.down;
      var yh = priceY(b.h), yl = priceY(b.l), yo = priceY(b.o), yc = priceY(b.c);
      ctx.fillRect(x, Math.round(yh), 1, Math.max(1, Math.round(yl) - Math.round(yh)));
      var bt = Math.round(Math.min(yo, yc));
      ctx.fillRect(x - Math.floor(bodyW / 2), bt, bodyW, Math.max(1, Math.round(Math.max(yo, yc)) - bt));
      var vh = Math.max(1, Math.round(b.v / vmax * (G.volH - 4)));
      ctx.globalAlpha = 0.45;
      ctx.fillRect(x - Math.floor(bodyW / 2), G.volTop + G.volH - vh, bodyW, vh);
      ctx.globalAlpha = 1;
    }

    // 开平仓标记
    function marker(idx, price, side, isEntry) {
      if (idx < G.first || idx > G.last) return;
      var mx = barX(idx), my = priceY(price);
      ctx.fillStyle = isEntry ? (side === 1 ? C.up : C.down) : C.card;
      ctx.strokeStyle = isEntry ? C.card : C.text;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      if (isEntry) {
        var bar = DATA[idx];
        var by = side === 1 ? priceY(bar.l) + 6 : priceY(bar.h) - 6;
        var dir = side === 1 ? 1 : -1; // 做多：K 线下方朝上的三角
        ctx.moveTo(mx, by);
        ctx.lineTo(mx - 5, by + 9 * dir);
        ctx.lineTo(mx + 5, by + 9 * dir);
        ctx.closePath();
        ctx.fill();
      } else {
        ctx.arc(mx, my, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
    }
    S.trades.forEach(function (tr) {
      marker(tr.entryIdx, tr.entry, tr.side, true);
      marker(tr.exitIdx, tr.exit, tr.side, false);
    });
    if (S.pos) marker(S.pos.entryIdx, S.pos.entry, S.pos.side, true);

    // 现价线
    var lb = lastBar();
    var curColor = lb.c >= lb.o ? C.up : C.down;
    var cy = priceY(lb.c);
    if (cy >= G.top - 8 && cy <= G.volTop) {
      hLine(cy, curColor, [2, 3]);
      axisTag(cy, fmtPrice(lb.c), curColor, "#fff");
    }

    // 持仓线
    if (S.pos) {
      var lines = [
        [S.pos.entry, C.accent, t("lineEntry")],
        [S.pos.tp, C.up, t("lineTp")],
        [S.pos.sl, C.down, t("lineSl")],
      ];
      lines.forEach(function (ln) {
        if (ln[0] === null) return;
        var ly = priceY(ln[0]);
        if (ly < G.top - 8 || ly > G.volTop) return;
        hLine(ly, ln[1], [6, 4]);
        ctx.fillStyle = ln[1];
        ctx.textAlign = "left";
        ctx.textBaseline = "bottom";
        ctx.fillText(ln[2] + " " + fmtPrice(ln[0]), 8, ly - 2);
        axisTag(ly, fmtPrice(ln[0]), ln[1], "#fff");
      });
    }

    // 十字线
    var hv = view.hover;
    if (hv && hv.x < G.plotW && hv.i >= G.first && hv.i <= G.last) {
      var hx = Math.round(barX(hv.i)) + 0.5;
      ctx.save();
      ctx.strokeStyle = C.muted;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(hx, G.top - 8);
      ctx.lineTo(hx, G.h - G.timeH);
      ctx.stroke();
      ctx.restore();
      if (hv.y >= G.top && hv.y <= G.top + G.priceH) {
        hLine(hv.y, C.muted, [3, 3]);
        axisTag(hv.y, fmtPrice(yPrice(hv.y)), C.muted, C.card);
      }
      var label = fmtTime(DATA[hv.i].t);
      var lw = ctx.measureText(label).width + 10;
      var lx = Math.max(0, Math.min(G.plotW - lw, hx - lw / 2));
      ctx.fillStyle = C.muted;
      ctx.fillRect(lx, G.h - G.timeH + 2, lw, G.timeH - 4);
      ctx.fillStyle = C.card;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, lx + lw / 2, G.h - G.timeH / 2);
    }

    // 分隔线
    ctx.strokeStyle = C.line;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(G.plotW + 0.5, 0);
    ctx.lineTo(G.plotW + 0.5, G.h);
    ctx.moveTo(0, G.h - G.timeH + 0.5);
    ctx.lineTo(G.w, G.h - G.timeH + 0.5);
    ctx.stroke();

    renderLegend();
  }

  function renderLegend() {
    var hv = view.hover;
    var i = hv && hv.i >= 0 && hv.i < S.idx ? hv.i : S.idx - 1;
    var b = DATA[i];
    var prev = i > 0 ? DATA[i - 1].c : b.o;
    var chg = b.c / prev - 1;
    var cls = b.c >= b.o ? "pos-up" : "pos-down";
    var el = $("legend");
    el.textContent = "";
    var parts = [
      [fmtTime(b.t), ""],
      ["O ", fmtPrice(b.o)], ["H ", fmtPrice(b.h)], ["L ", fmtPrice(b.l)], ["C ", fmtPrice(b.c)],
      ["", fmtPct(chg)], ["Vol ", fmtMoney(b.v)],
    ];
    parts.forEach(function (pt) {
      var span = document.createElement("span");
      span.appendChild(document.createTextNode(pt[0]));
      if (pt[1]) {
        var bEl = document.createElement("b");
        bEl.className = cls;
        bEl.textContent = pt[1];
        span.appendChild(bEl);
      }
      el.appendChild(span);
    });
  }

  // 图表交互：拖动回看、滚轮缩放、十字线
  var drag = null;
  function localPos(e) {
    var r = canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }
  canvas.addEventListener("pointerdown", function (e) {
    var p = localPos(e);
    drag = { x: p.x, offset: view.offset, id: e.pointerId };
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
  });
  canvas.addEventListener("pointermove", function (e) {
    var p = localPos(e);
    if (drag && drag.id === e.pointerId) {
      view.offset = drag.offset + (p.x - drag.x) / view.slot;
      clampView();
    }
    view.hover = { x: p.x, y: p.y, i: 0 };
    G.last = S.idx - 1 - Math.round(view.offset);
    view.hover.i = Math.max(0, Math.min(S.idx - 1, indexAt(p.x)));
    drawChart();
  });
  function endDrag(e) {
    if (drag && drag.id === e.pointerId) drag = null;
    if (e.pointerType !== "mouse") { view.hover = null; drawChart(); }
  }
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
  canvas.addEventListener("pointerleave", function () {
    if (drag) return;
    view.hover = null;
    drawChart();
  });
  canvas.addEventListener("wheel", function (e) {
    e.preventDefault();
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      view.offset -= e.deltaX / view.slot;
    } else {
      view.slot *= e.deltaY < 0 ? 1.1 : 1 / 1.1;
    }
    view.hover = null;
    drawChart();
  }, { passive: false });
  function zoom(f) { view.slot *= f; drawChart(); }

  // ---------- 汇总渲染 ----------
  function renderAll() {
    renderPanel();
    renderPlayBtn();
    drawChart();
  }

  // ---------- 主题 ----------
  function currentTheme() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function toggleTheme() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store("kreplay_theme", next);
    drawChart();
  }

  // ---------- 事件绑定 ----------
  function on(id, fn) { $(id).addEventListener("click", fn); }
  on("nextBtn", function () { stopAuto(); step(); });
  on("playBtn", toggleAuto);
  on("resetBtn", reset);
  on("summaryBtn", openSummary);
  on("longBtn", function () { openPosition(1); });
  on("shortBtn", function () { openPosition(-1); });
  on("closeBtn", manualClose);
  on("tpslBtn", updateTpSl);
  on("zoomIn", function () { zoom(1.25); });
  on("zoomOut", function () { zoom(0.8); });
  on("themeBtn", toggleTheme);
  on("sumClose", closeSummary);
  on("sumAgain", reset);
  $("quickAmt").addEventListener("click", function (e) {
    var btn = e.target.closest("[data-mult]");
    if (!btn) return;
    var eq = Math.max(0, equity());
    $("amountInp").value = Math.floor(eq * Number(btn.getAttribute("data-mult")));
    clearMsg();
  });
  $("speedSel").addEventListener("change", function () { if (timer) startAuto(); });
  $("langSel").addEventListener("change", function () {
    lang = this.value;
    store("kreplay_lang", lang);
    applyI18n();
    renderMsg();
    renderAll();
    if ($("summaryDlg").open) buildSummary();
  });
  // 用鼠标或手指点过的按钮不保留焦点，避免之后按空格又触发一次
  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("button");
    if (btn && e.detail > 0 && !btn.closest("dialog")) btn.blur();
  });
  function isTyping(el) {
    return el && (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA");
  }
  document.addEventListener("keydown", function (e) {
    if ($("summaryDlg").open || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.code === "Space") {
      e.preventDefault();
      stopAuto();
      step();
      return;
    }
    if (isTyping(e.target) || e.repeat) return;
    var k = (e.key || "").toLowerCase();
    if (k === "b") openPosition(1);
    else if (k === "s") openPosition(-1);
    else if (k === "c") manualClose();
    else if (k === "p") toggleAuto();
  });
  document.addEventListener("keyup", function (e) {
    // 焦点在按钮上时，空格抬起会再点一次按钮，这里拦掉
    if (e.code === "Space" && !$("summaryDlg").open && e.target.tagName === "BUTTON") e.preventDefault();
  });
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var onScheme = function () { drawChart(); };
    if (mq.addEventListener) mq.addEventListener("change", onScheme);
    else if (mq.addListener) mq.addListener(onScheme);
  }
  if (window.ResizeObserver) new ResizeObserver(resizeCanvas).observe($("chartWrap"));
  else window.addEventListener("resize", resizeCanvas);

  // ---------- 启动 ----------
  var savedTheme = store("kreplay_theme");
  if (savedTheme === "dark" || savedTheme === "light") document.documentElement.setAttribute("data-theme", savedTheme);
  lang = detectLang();
  $("langSel").value = lang;
  S = newState();
  applyI18n();
  resizeCanvas();
  renderAll();

  // 供自检脚本读取状态
  window.KReplay = {
    state: function () { return S; },
    equity: equity,
    view: view,
    isPlaying: function () { return !!timer; },
  };
})();
