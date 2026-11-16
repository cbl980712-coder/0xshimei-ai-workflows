#!/usr/bin/env python3
"""会议速记 / 转写稿 -> 5-7 页汇报 PPT + 演讲提纲备忘 + 运行报告。

两步，可单独用：
  analyze : 文本 -> outline.json   （纯规则、离线、秒级；Claude 可以再改这个 JSON）
  build   : outline.json -> .pptx + notes.md + report.html

最常用：python make_presentation.py 会议.txt --out out/
改完大纲再生成：python make_presentation.py --outline out/outline.json --out out/
只依赖 python-pptx。不联网、不调用任何 API。
"""
import argparse, json, math, os, re, sys, time, html
from collections import Counter, OrderedDict

# ---------------------------------------------------------------- 文本清洗
STOP_SPEAKERS = {
    "answer", "question", "example", "examples", "note", "notes", "link", "summary", "problem",
    "solution", "context", "pros", "cons", "q", "a", "todo", "meeting", "why", "how", "option",
    "idea", "background", "result", "status", "issue", "proposal", "details", "tldr", "tl;dr",
    "attendance", "agenda", "decision", "action", "update", "goal", "goals", "non-goals", "caveat",
    "important", "warning", "tip", "output", "input", "reminder", "pro", "con", "date", "team",
    "others", "members", "scribe", "alternative", "motivation", "drawback", "benefit", "usage",
}
BOILER = re.compile(r"forward-looking|Securities and Exchange|safe harbor|undertake no obligation|"
                    r"reconciliation of|earnings release|investor relations website|^thank|^good (morning|afternoon)|"
                    r"welcome to|^with that|^operator|^now,? (i'll|let me|moving)|please refer|statements are subject|not guarantees|risks and uncertainties", re.I)

def clean_text(raw):
    t = raw.replace("\r\n", "\n")
    t = re.sub(r"\A---\n.*?\n---\n", "", t, flags=re.S)             # frontmatter
    t = re.sub(r"```.*?```", " ", t, flags=re.S)                    # 代码块
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"^\s*\[[^\]]+\]:\s*\S+.*$", "", t, flags=re.M)      # 链接定义
    t = re.sub(r"^\[\^[^\]]+\]:.*$", "", t, flags=re.M)             # 脚注定义
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", t)
    t = re.sub(r"\[\^[^\]]+\]", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"(\*\*|__)(.+?)\1", r"\2", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"^\s*>+\s?", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s*", "- ", t, flags=re.M)
    t = t.replace(" ", " ").replace("ﬁ", "fi")
    # PDF 常见断词： "profitabili ty" "dif fer" -> 仅修 小写+空格+1~2个小写 且接空格/标点 的明显断裂
    t = re.sub(r"\b([a-z]{4,}) ((?:ty|ter|fer|ing|ed|ent|ion|ly))\b(?=[\s,.;:])", r"\1\2", t)
    return t

SPEAKER_HDR = re.compile(r"^([A-Z][\w.'’-]+(?: [A-Z][\w.'’-]+){0,3}),[^–—\n]{2,80}[–—-] .{3,90}$")
SPEAKER_COLON = re.compile(r"^(?:[-*+]\s*)?([A-Za-z\u4e00-\u9fff][\w.'’\u4e00-\u9fff-]{1,28}(?: [A-Z][\w.'’-]{1,18}){0,2})(?::\s+|：\s*)(\S.*)$")
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*$")

def parse_blocks(text):
    """返回 [{section, speaker, text}]，并统计发言人。"""
    lines = text.split("\n")
    blocks, section, speaker = [], "", None
    buf = []
    cand = Counter()
    for ln in lines:
        m = SPEAKER_COLON.match(ln.strip())
        if m and m.group(1).lower() not in STOP_SPEAKERS:
            cand[m.group(1)] += 1
    speakers = {n for n, c in cand.items() if c >= 2}
    def flush():
        nonlocal buf
        s = re.sub(r"\s+", " ", " ".join(buf)).strip()
        if len(s) > 20:
            blocks.append({"section": section, "speaker": speaker, "text": s})
        buf = []
    for ln in lines:
        s = ln.strip()
        h = HEADING.match(s)
        if h:
            flush(); section = h.group(2).strip(); continue
        mh = SPEAKER_HDR.match(s)
        if mh:
            flush(); speaker = mh.group(1); continue
        mc = SPEAKER_COLON.match(s)
        if mc and mc.group(1) in speakers:
            flush(); speaker = mc.group(1); buf = [mc.group(2)]; flush(); continue
        if not s:
            flush(); continue
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            flush(); buf = [re.sub(r"^([-*+]|\d+[.)])\s+", "", s)]; flush(); continue
        buf.append(s)
    flush()
    return blocks

def split_sentences(p):
    out = re.split(r"(?<=[.!?。！？])\s+(?=[A-Z0-9\"“(一-鿿])", p)
    return [s.strip() for s in out if s.strip()]

# ---------------------------------------------------------------- 指标 / 打分
NUM = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?\s?(?:million|billion|thousand|M|B|K)?"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:%|percent|basis points|bps|million|billion|x\b|times|days|weeks|months|years|hours|minutes|ms\b)"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:customers|users|PRs|crates|ARR|seats|employees|万元|万|亿元|亿|元|个百分点|倍|天|周|个月|人|家|台))", re.I)
GROWTH = re.compile(r"收入|增长|订单|成本|节省|投诉率|客单价|revenue|ARR|margin|cash flow|growth|grew|increase|retention|churn|guidance|year-over-year|"
                    r"profit|bookings|subscribers|cost|saving|reduc|latency|users|adoption", re.I)
K_CONC = re.compile(r"(?:决定|确定|一致同意|结论|建议|优先|目标|上线|通过|批准)|\b(decid\w*|agree\w*|conclu\w*|resolv\w*|consensus|recommend\w*|therefore|overall|"
                    r"we (?:will|should|plan|propose|expect|believe|think)|stabili[sz]\w*|ship\w*|approv\w*|"
                    r"outlook|guidance|target\w*|priorit\w*|strategy|achiev\w*|deliver\w*)\b", re.I)
K_RISK = re.compile(r"(?:风险|问题|担心|但是|不过|延期|延误|超支|瓶颈|不确定|投诉|阻塞)|\b(risk\w*|concern\w*|problem\w*|issue\w*|however|but|unclear|worr\w*|challeng\w*|"
                    r"downside|against|limit\w*|break\w*|confus\w*|complex\w*|surpris\w*|pressure|decline\w*|"
                    r"headwind\w*|uncertain\w*|drawback|not sure|can't|cannot|don't)\b", re.I)
K_ACT = re.compile(r"(?:下一步|待办|跟进|负责|截止|本周|下周|需要|计划)|\b(next steps?|action items?|follow[- ]up|todo|will (?:write|draft|file|open|create|send|launch|continue|invest|"
                    r"focus|report|hold)|need(?:s)? to|plan(?:s)? to|going to|by (?:q[1-4]|end of|next)|"
                    r"ahead|looking forward|expect(?:s)? to)\b", re.I)

def score_sentence(s, pos_bonus=0.0):
    n = len(s)
    if n < 35 or n > 320 or s.endswith("?") or BOILER.search(s):
        return -1
    sc = 1.0 + pos_bonus
    sc += 0.8 * len(NUM.findall(s))
    sc += 0.6 * len(K_CONC.findall(s)) + 0.3 * len(K_RISK.findall(s))
    if 60 <= n <= 190: sc += 0.5
    return sc

def shorten(s, limit=150):
    s = s.strip().rstrip(".")
    if len(s) <= limit: return s
    cut = -1
    for m in re.finditer(r"[,;:–—]\s|\s(?:and|but|which|while|so)\s", s):
        if 70 <= m.start() <= limit: cut = m.start()
    if cut < 0:
        cut = s.rfind(" ", 0, limit)
    return s[:cut].rstrip(" ,;:–—") + "…"

def jacc(a, b):
    A, B = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(A & B) / max(1, len(A | B))

def pick(cands, k, used):
    out = []
    for sc, s, sp, sec in sorted(cands, key=lambda x: -x[0]):
        if sc <= 0 or any(jacc(s, u) > 0.5 for u in used): continue
        out.append((s, sp, sec)); used.append(s)
        if len(out) >= k: break
    return out

def strong_terms(text):
    terms = [m.group(0).strip() for m in NUM.finditer(text)][:2]
    m = K_CONC.search(text) or K_RISK.search(text)
    if m and len(terms) < 3: terms.append(m.group(0))
    return [t for t in dict.fromkeys(terms) if t in text]

LABELS = {
 "zh": dict(bg="背景与议题", metrics="核心指标", facts="关键事实", views="各方观点", risks="风险与分歧",
            concl="结论与决策", nxt="下一步与待办", agenda="本次讨论的议题", words="字", slides="页",
            speakers="发言人", source="来源", auto="自动提取草稿"),
 "en": dict(bg="Background & agenda", metrics="Key metrics", facts="Key facts", views="Positions by speaker",
            risks="Risks & open questions", concl="Conclusions & decisions", nxt="Next steps",
            agenda="Topics discussed", words="words", slides="slides", speakers="Speakers", source="Source",
            auto="Auto-extracted draft"),
}

# ---------------------------------------------------------------- 分析
def analyze(raw, title=None, lang="zh", source_name="", max_slides=7):
    L = LABELS[lang]
    text = clean_text(raw)
    blocks = parse_blocks(text)
    if not blocks:
        print("出错了：没有从输入里解析出可用的文字（内容太短，或几乎全是代码/链接）。\n  请确认文件里是会议发言或纪要正文，至少要有几句完整的话。", file=sys.stderr); sys.exit(2)
    words = len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9][\w'’.-]*", text))
    # 全文句子（带位置、发言人、章节）
    sents, N = [], len(blocks)
    for i, b in enumerate(blocks):
        for j, s in enumerate(split_sentences(b["text"])):
            sents.append(dict(s=s, sp=b["speaker"], sec=b["section"], i=i, j=j, pos=i / max(1, N - 1)))
    h1 = re.search(r"^#\s+(.+)$", raw, re.M)
    if not title:
        title = h1.group(1).strip() if h1 else (source_name or "会议汇报")
    spk_words = Counter()
    for b in blocks:
        if b["speaker"]: spk_words[b["speaker"]] += len(b["text"].split())
    speakers = [n for n, _ in spk_words.most_common(6)]
    sections = list(OrderedDict.fromkeys(b["section"] for b in blocks if b["section"]))
    used, slides = [], []

    # 指标
    mets = []
    for x in sents:
        if BOILER.search(x["s"]) or x["s"].endswith("?"): continue
        for m in NUM.finditer(x["s"]):
            v = re.sub(r"\s+", " ", m.group(0)).strip()
            before = x["s"][:m.start()].split()[-7:]
            after = x["s"][m.end():].split()[:4]
            label = shorten(x["s"], 85)
            w = (2 if GROWTH.search(x["s"]) else 0) + (1 if "%" in v or "$" in v else 0) + (1 if x["sp"] else 0)
            mets.append((w, v, label, x["s"]))
    metrics, seen = [], set()
    for w, v, label, s in sorted(mets, key=lambda z: -z[0]):
        if w < 3 or v in seen or any(jacc(label, u['label']) > 0.6 for u in metrics): continue
        seen.add(v); metrics.append(dict(value=v, label=label, source=s)); used.append(s)
        if len(metrics) == 6: break

    # 1 封面
    sub = []
    if speakers: sub.append(f"{L['speakers']}: " + ", ".join(speakers[:4]))
    sub.append(f"{words} {L['words']} → {L['auto']}")
    slides.append(dict(type="cover", title=title, subtitle=" | ".join(sub), notes=[]))

    # 2 背景与议题
    lead = [x for x in sents if score_sentence(x["s"]) > 0 and x["pos"] < 0.2]
    bg = pick([(score_sentence(x["s"], 0.5 - x["pos"]), x["s"], x["sp"], x["sec"]) for x in lead], 2, used)
    bul = [dict(text=shorten(s), strong=strong_terms(shorten(s))) for s, _, _ in bg]
    if sections:
        agenda = [s for s in sections if len(s) < 60 and s.lower() != title.lower()][:5]
        if agenda:
            bul.append(dict(text=f"{L['agenda']}: " + " / ".join(agenda), strong=[L['agenda'] + ":"]))
    slides.append(dict(type="bullets", title=L["bg"], bullets=bul, notes=[s for s, _, _ in bg]))

    # 3 指标 或 关键事实
    if len(metrics) >= 3:
        slides.append(dict(type="metrics", title=L["metrics"], metrics=metrics,
                           takeaway=shorten(metrics[0]["source"], 140), notes=[m["source"] for m in metrics]))
    else:
        c = [(score_sentence(x["s"]) + 0.5 * len(NUM.findall(x["s"])), x["s"], x["sp"], x["sec"]) for x in sents]
        facts = pick(c, 4, used)
        slides.append(dict(type="bullets", title=L["facts"],
                           bullets=[dict(text=shorten(s), strong=strong_terms(shorten(s))) for s, _, _ in facts],
                           notes=[s for s, _, _ in facts]))

    # 4 各方观点（有发言人按人，否则按章节）
    views = []
    if len(speakers) >= 2:
        for sp in speakers[:5]:
            c = [(score_sentence(x["s"]) + 0.4 * len(K_CONC.findall(x["s"])), x["s"], sp, x["sec"])
                 for x in sents if x["sp"] == sp]
            p = pick(c, 1, used)
            if p: views.append((sp, p[0][0]))
        bul = [dict(text=f"{sp}: {shorten(s, 135)}", strong=[sp + ":"] + strong_terms(shorten(s, 135))[:1]) for sp, s in views]
    else:
        for sec in sections[:6]:
            c = [(score_sentence(x["s"]), x["s"], x["sp"], sec) for x in sents if x["sec"] == sec]
            p = pick(c, 1, used)
            if p: views.append((sec, p[0][0]))
        bul = [dict(text=f"{sec}: {shorten(s, 130)}", strong=[sec + ":"]) for sec, s in views[:5]]
    slides.append(dict(type="bullets", title=L["views"], bullets=bul, notes=[s for _, s in views]))

    # 5 风险
    c = [(score_sentence(x["s"]) + 1.2 * len(K_RISK.findall(x["s"])) - 0.5 * len(K_CONC.findall(x["s"])), x["s"], x["sp"], x["sec"]) for x in sents]
    c = [z for z in c if K_RISK.search(z[1])]
    rk = pick(c, 4, used)
    slides.append(dict(type="bullets", title=L["risks"],
                       bullets=[dict(text=shorten(s), strong=([k.group(0)] if (k := K_RISK.search(shorten(s))) else []) + strong_terms(shorten(s))[:1]) for s, _, _ in rk],
                       notes=[f"{sp or ''}: {s}".strip(": ") for s, sp, _ in rk]))

    # 6 结论
    c = [(score_sentence(x["s"]) + 1.3 * len(K_CONC.findall(x["s"])) + 1.2 * x["pos"] - 0.3 * len(K_RISK.findall(x["s"])), x["s"], x["sp"], x["sec"]) for x in sents]
    cc = pick(c, 4, used)
    slides.append(dict(type="bullets", title=L["concl"],
                       bullets=[dict(text=shorten(s), strong=strong_terms(shorten(s))) for s, _, _ in cc],
                       notes=[f"{sp or ''}: {s}".strip(": ") for s, sp, _ in cc]))

    # 7 下一步
    c = [(score_sentence(x["s"]) + 1.5 * len(K_ACT.findall(x["s"])) + 0.8 * x["pos"], x["s"], x["sp"], x["sec"])
         for x in sents if K_ACT.search(x["s"])]
    ac = pick(c, 4, used)
    if ac:
        slides.append(dict(type="bullets", title=L["nxt"],
                           bullets=[dict(text=shorten(s, 140), strong=([k.group(0)] if (k := K_ACT.search(shorten(s, 140))) else [])) for s, _, _ in ac],
                           notes=[f"{sp or ''}: {s}".strip(": ") for s, sp, _ in ac]))
    slides = [s for s in slides if s["type"] in ("cover", "metrics") or s.get("bullets")]
    slides = slides[:max_slides]
    return dict(title=title, lang=lang, source=source_name, words=words, slides=slides)

# ---------------------------------------------------------------- 排版：文字换行估算
def text_width(s, size):
    w = 0.0
    for ch in s:
        w += size * (1.0 if ord(ch) > 0x2E80 else 0.56 if ch.isupper() else 0.5 if ch != " " else 0.28)
    return w

def count_lines(s, size, width_pt):
    if text_width(s, size) <= width_pt: return 1
    lines, cur = 1, 0.0
    for tok in re.findall(r"[⺀-￿]|\S+\s*", s):
        tw = text_width(tok, size)
        if cur + tw > width_pt and cur > 0: lines += 1; cur = 0
        cur += tw
    return lines

def fit_bullets(bullets, width_in, height_in, sizes=(28, 26, 24, 22, 20, 18, 17, 16)):
    """选能放进文本框的最大字号；返回 (字号, 行数, 是否放得下)。"""
    for size in sizes:
        wpt = (width_in - 0.5) * 72 - size * 1.2          # 去掉内边距和项目符号缩进
        lines = sum(count_lines(b["text"], size, wpt) for b in bullets)
        h = (lines * size * 1.2 + len(bullets) * size * 0.95) / 72
        if h <= height_in: return size, lines, True
    return sizes[-1], lines, False

# ---------------------------------------------------------------- 生成 PPTX
NAVY, ACCENT, INK, GREY, PALE = "1F3A5F", "D9480F", "222B38", "6B7685", "EEF2F7"

def build_pptx(outline, path):
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree

    rgb = lambda h: RGBColor.from_string(h)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    # 母版/版式占位符改成 16:9，用户之后在 PowerPoint 里新建页也是对的
    geo = {1: (0.7, 0.45, 11.9, 1.0), 2: (0.7, 1.75, 11.9, 4.9)}
    for lay in list(prs.slide_layouts)[:7] + [prs.slide_master]:
        for ph in lay.placeholders:
            t = ph.placeholder_format.type
            try:
                if "TITLE" in str(t) and "SUB" not in str(t): ph.left, ph.top, ph.width, ph.height = [Inches(v) for v in geo[1]]
                elif "BODY" in str(t) or "OBJECT" in str(t): ph.left, ph.top, ph.width, ph.height = [Inches(v) for v in geo[2]]
            except Exception: pass

    def style(run, size, bold=False, color=INK):
        f = run.font; f.size = Pt(size); f.bold = bold; f.color.rgb = rgb(color); f.name = "Calibri"
        rPr = run._r.get_or_add_rPr()
        for tag in ("a:ea", "a:cs"):
            e = etree.SubElement(rPr, qn(tag)); e.set("typeface", "Microsoft YaHei" if tag == "a:ea" else "Calibri")

    def rect(sl, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
        s = sl.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        s.fill.solid(); s.fill.fore_color.rgb = rgb(color); s.line.fill.background(); s.shadow.inherit = False
        return s

    def write_runs(par, text, strong, size, color=INK):
        """把 strong 里出现的片段做成加粗 + 强调色，其余正常。"""
        spans = []
        for t in strong:
            i = text.find(t)
            if i >= 0: spans.append((i, i + len(t)))
        spans.sort(); merged = []
        for a, b in spans:
            if merged and a < merged[-1][1]: merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else: merged.append((a, b))
        pos = 0
        for a, b in merged:
            if a > pos: r = par.add_run(); r.text = text[pos:a]; style(r, size, False, color)
            r = par.add_run(); r.text = text[a:b]; style(r, size, True, ACCENT)
            pos = b
        if pos < len(text): r = par.add_run(); r.text = text[pos:]; style(r, size, False, color)

    def footer(sl, n, total):
        tb = sl.shapes.add_textbox(Inches(0.7), Inches(6.95), Inches(11.9), Inches(0.35))
        p = tb.text_frame.paragraphs[0]; r = p.add_run()
        r.text = f"{outline.get('source') or outline['title']}  ·  {n} / {total}"; style(r, 11, False, GREY)

    def set_title(sl, text):
        t = sl.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.9), Inches(0.4), Inches(11.7), Inches(1.0)
        tf = t.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = text
        style(r, 32 if text_width(text, 32) < 11.2 * 72 else 26, True, NAVY)
        rect(sl, 0.7, 0.55, 0.12, 0.7, ACCENT)
        rect(sl, 0.7, 1.45, 11.9, 0.03, "C9D1DC")

    total = len(outline["slides"])
    checks = []
    for sd in outline["slides"]:                       # 高亮片段必须真在原句里，否则提示
        for b in sd.get("bullets", []):
            for t in b.get("strong", []):
                if t not in b["text"]: print(f"  提示：高亮片段 '{t}' 不在句子里，已忽略：{b['text'][:30]}…")
    for n, sd in enumerate(outline["slides"], 1):
        notes = sd.get("notes") or []
        if sd["type"] == "cover":
            sl = prs.slides.add_slide(prs.slide_layouts[0])
            sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(NAVY)
            rect(sl, 0.9, 2.55, 0.14, 1.9, ACCENT)
            t, st = sl.shapes.title, sl.placeholders[1]
            size = 40 if text_width(sd["title"], 40) < 2 * 11 * 72 else 32
            t.left, t.top, t.width, t.height = Inches(1.3), Inches(2.4), Inches(11), Inches(1.5)
            t.text_frame.word_wrap = True; t.text_frame.vertical_anchor = MSO_ANCHOR.BOTTOM
            p = t.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
            r = p.add_run(); r.text = sd["title"]; style(r, size, True, "FFFFFF")
            st.left, st.top, st.width, st.height = Inches(1.3), Inches(4.0), Inches(11), Inches(0.9)
            st.text_frame.word_wrap = True
            p = st.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
            r = p.add_run(); r.text = sd.get("subtitle", ""); style(r, 18, False, "C9D6E8")
            checks.append(dict(n=n, title=sd["title"], font=size, lines=count_lines(sd["title"], size, 11 * 72), fits=True))
        elif sd["type"] == "metrics":
            sl = prs.slides.add_slide(prs.slide_layouts[5]); set_title(sl, sd["title"])
            ms = sd["metrics"][:6]; cols = 3 if len(ms) > 4 else 2 if len(ms) == 4 else len(ms)
            rows = math.ceil(len(ms) / cols); cw, ch, gx, gy = 3.75, 1.95, 0.325, 0.3
            x0 = 0.7 + (11.9 - (cols * cw + (cols - 1) * gx)) / 2
            for i, m in enumerate(ms):
                x, y = x0 + (i % cols) * (cw + gx), 1.8 + (i // cols) * (ch + gy)
                card = rect(sl, x, y, cw, ch, PALE, MSO_SHAPE.ROUNDED_RECTANGLE); card.adjustments[0] = 0.08
                rect(sl, x, y + 0.2, 0.08, ch - 0.4, ACCENT)
                tb = sl.shapes.add_textbox(Inches(x + 0.25), Inches(y + 0.12), Inches(cw - 0.4), Inches(ch - 0.2))
                tf = tb.text_frame; tf.word_wrap = True
                p = tf.paragraphs[0]; r = p.add_run(); r.text = m["value"]
                vs = 40 if len(m["value"]) <= 8 else 32; style(r, vs, True, ACCENT)
                p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = m["label"]; style(r2, 17, False, INK)
                ln = count_lines(m["label"], 17, (cw - 0.65) * 72)
                checks.append(dict(n=n, title=f"指标卡 {m['value']}", font=17, lines=ln, fits=ln <= 3 and text_width(m["value"], vs) < (cw - 0.65) * 72))
            if sd.get("takeaway"):
                ty = 1.8 + rows * (ch + gy) + 0.05
                tb = sl.shapes.add_textbox(Inches(0.7), Inches(ty), Inches(11.9), Inches(0.9)); tb.text_frame.word_wrap = True
                p = tb.text_frame.paragraphs[0]; write_runs(p, "→ " + sd["takeaway"], [m["value"] for m in ms[:1]], 16, GREY)
                ln = count_lines(sd["takeaway"], 16, 11.4 * 72); checks.append(dict(n=n, title="指标页底部结论", font=16, lines=ln, fits=ty + ln * 0.3 < 6.9))
            footer(sl, n, total)
        else:
            sl = prs.slides.add_slide(prs.slide_layouts[1]); set_title(sl, sd["title"])
            body = sl.placeholders[1]
            body.left, body.top, body.width, body.height = Inches(0.9), Inches(1.75), Inches(11.7), Inches(4.95)
            bl = sd["bullets"]
            size, lines, ok = fit_bullets(bl, 11.7, 4.95)
            tf = body.text_frame; tf.word_wrap = True
            for i, b in enumerate(bl):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.level = 0; p.space_after = Pt(size * 0.9); p.line_spacing = 1.05
                write_runs(p, b["text"], b.get("strong", []), size)
            checks.append(dict(n=n, title=sd["title"], font=size, lines=lines, fits=ok))
            footer(sl, n, total)
        if sd["type"] == "cover":
            pass
        ns = sl.notes_slide.notes_text_frame
        ns.text = "\n".join(notes) if notes else ""
        sd["_font"] = checks[-1]["font"] if checks else None
    prs.save(path)
    return checks

# ---------------------------------------------------------------- 讲稿备忘 / 报告
def build_notes(outline, path):
    L = LABELS[outline.get("lang", "zh")]
    out = [f"# 演讲提纲备忘：{outline['title']}", "",
           f"> 由 make_presentation.py 自动生成；共 {len(outline['slides'])} 页，建议总时长 {max(3, len(outline['slides']) * 1)} 分钟（估算：每页约 1 分钟）。", ""]
    for n, s in enumerate(outline["slides"], 1):
        out.append(f"## 第 {n} 页　{s['title']}")
        if s["type"] == "cover":
            out += ["- 开场：说明这是哪次会议、谁参加、今天只讲结论和待办。", f"- 数据来源：{s.get('subtitle','')}", ""]
            continue
        if s["type"] == "metrics":
            out += [f"- **{m['value']}**　{m['label']}" for m in s["metrics"]]
        else:
            out += [f"- {b['text']}" for b in s["bullets"]]
        if s.get("notes"):
            out.append("\n口头补充（原话依据，讲的时候可展开）：")
            out += [f"  - 「{x[:220]}」" for x in s["notes"][:4]]
        out.append("")
    open(path, "w", encoding="utf-8").write("\n".join(out))

def build_report(outline, checks, secs, path, pptx_name):
    e = html.escape
    def hl(text, strong):
        t = e(text)
        for s in sorted(strong, key=len, reverse=True):
            if s and e(s) in t: t = t.replace(e(s), f"<mark>{e(s)}</mark>", 1)
        return t
    rows = []
    for n, s in enumerate(outline["slides"], 1):
        if s["type"] == "metrics":
            inner = "<div class='cards'>" + "".join(f"<div class='card'><b>{e(m['value'])}</b><span>{e(m['label'])}</span></div>" for m in s["metrics"]) + "</div>"
        elif s["type"] == "cover":
            inner = f"<p class='sub'>{e(s.get('subtitle',''))}</p>"
        else:
            inner = "<ul>" + "".join(f"<li>{hl(b['text'], b.get('strong', []))}</li>" for b in s["bullets"]) + "</ul>"
        fit = next((c for c in checks if c["n"] == n), None)
        tag = "" if not fit else f"<span class='fit {'ok' if fit['fits'] else 'bad'}'>字号 {fit['font']}pt · 约 {fit['lines']} 行 · {'放得下' if fit['fits'] else '可能溢出'}</span>"
        rows.append(f"<section><h3><i>{n}</i>{e(s['title'])}{tag}</h3>{inner}</section>")
    page = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>运行报告 · {e(outline['title'])}</title><style>
body{{font:16px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f4f6f9;color:#222b38;margin:0;padding:24px 16px}}
main{{max-width:980px;margin:auto}} h1{{font-size:26px;margin:0 0 6px;color:#1f3a5f}} .meta{{color:#6b7685;margin-bottom:20px}}
section{{background:#fff;border-radius:10px;padding:14px 22px;margin:12px 0;border-left:6px solid #d9480f}}
h3{{margin:4px 0 6px;font-size:19px;color:#1f3a5f}} h3 i{{font-style:normal;background:#1f3a5f;color:#fff;border-radius:50%;display:inline-block;width:26px;height:26px;line-height:26px;text-align:center;font-size:14px;margin-right:10px}}
mark{{background:none;color:#d9480f;font-weight:700}} ul{{margin:4px 0;padding-left:22px}} li{{margin:5px 0}}
.fit{{float:right;font-size:12px;font-weight:400;padding:2px 8px;border-radius:10px}} .ok{{background:#e3f4e8;color:#1c6b3a}} .bad{{background:#fde8e1;color:#b3360c}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}} .card{{background:#eef2f7;border-radius:8px;padding:10px 14px}} .card b{{display:block;font-size:28px;color:#d9480f}} .card span{{font-size:14px}}
.sub{{color:#6b7685}}</style><main>
<h1>{e(outline['title'])}</h1>
<div class="meta">输入 {outline.get('words','?')} 词 · 输出 {len(outline['slides'])} 页 · 用时 {secs:.2f} 秒 · 成品 {e(pptx_name)}</div>
{''.join(rows)}</main></html>"""
    open(path, "w", encoding="utf-8").write(page)

# ---------------------------------------------------------------- 命令行
def die(msg):
    print("出错了：" + msg, file=sys.stderr)
    sys.exit(2)

def read_text_file(path):
    """读输入文件；给人看得懂的报错，不抛堆栈。UTF-8 读不了时依次试 GB18030（常见中文 txt）。"""
    if not os.path.exists(path): die(f"找不到输入文件：{path}\n  请检查路径和文件名（文件名里有空格要用引号括起来）。")
    if os.path.isdir(path): die(f"{path} 是文件夹，不是文件。请给一个 .txt 或 .md 文件。")
    if os.path.splitext(path)[1].lower() in (".pdf", ".docx", ".doc", ".pptx", ".xlsx"):
        die("这是 PDF/Word 等二进制文件，脚本只读纯文本。请先复制成 .txt 或 .md 再用。")
    try: data = open(path, "rb").read()
    except OSError as e: die(f"打不开 {path}：{e.strerror}")
    if not data.strip(): die(f"{path} 是空文件。请放入会议记录文字后再运行。")
    for enc in ("utf-8-sig", "gb18030"):
        try: text = data.decode(enc)
        except UnicodeDecodeError: continue
        if enc != "utf-8-sig": print(f"提示：{path} 不是 UTF-8，已按 {enc} 读取；若出现乱码，请另存为 UTF-8。")
        return text
    die(f"{path} 不是文本文件（UTF-8/GB18030 都读不出来）。请另存为 UTF-8 的 .txt。")

def load_outline(path):
    if not os.path.exists(path): die(f"找不到大纲文件：{path}\n  大纲是第一次运行时在 --out 目录里生成的 *.outline.json。")
    try: o = json.load(open(path, encoding="utf-8-sig"))
    except json.JSONDecodeError as e: die(f"{path} 不是合法的 JSON（第 {e.lineno} 行第 {e.colno} 列：{e.msg}）。\n  常见原因：少了逗号/引号，或结尾多了逗号。")
    except (OSError, UnicodeDecodeError) as e: die(f"读不了大纲 {path}：{e}")
    if not isinstance(o, dict) or not isinstance(o.get("slides"), list) or not o["slides"]:
        die(f"{path} 的结构不对：最外层要是对象，且有非空的 \"slides\" 列表（格式见 SKILL.md 第 3 步）。")
    o.setdefault("title", "会议汇报"); o.setdefault("lang", "zh")
    for i, sd in enumerate(o["slides"], 1):
        if not isinstance(sd, dict) or sd.get("type") not in ("cover", "bullets", "metrics"):
            die(f"{path} 第 {i} 页：type 必须是 cover / bullets / metrics 之一。")
        sd.setdefault("title", o["title"]); sd.setdefault("notes", [])
        if sd["type"] == "bullets":
            bl = sd.get("bullets")
            if not isinstance(bl, list) or not bl: die(f"{path} 第 {i} 页（bullets）缺少非空的 \"bullets\" 列表。")
            for b in bl:
                if not isinstance(b, dict) or not isinstance(b.get("text"), str): die(f"{path} 第 {i} 页：每条 bullet 要写成 {{\"text\": \"…\", \"strong\": [\"…\"]}}。")
                b.setdefault("strong", [])
        if sd["type"] == "metrics":
            ml = sd.get("metrics")
            if not isinstance(ml, list) or not ml: die(f"{path} 第 {i} 页（metrics）缺少非空的 \"metrics\" 列表。")
            for m in ml:
                if not isinstance(m, dict) or "value" not in m or "label" not in m: die(f"{path} 第 {i} 页：每张指标卡要有 value 和 label。")
    return o

def main():
    ap = argparse.ArgumentParser(description="会议文本 -> 汇报 PPT + 演讲提纲")
    ap.add_argument("input", nargs="?", help="会议速记/转写稿（.txt/.md；PDF 请先转成文本）")
    ap.add_argument("--outline", help="已有的 outline.json（跳过分析，只生成 PPT）")
    ap.add_argument("--out", default="out", help="输出目录，默认 out/")
    ap.add_argument("--name", help="输出文件名前缀，默认取输入文件名")
    ap.add_argument("--title", help="封面标题，默认取文档一级标题")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help="页面标题用中文还是英文（正文保持原文）")
    ap.add_argument("--max-slides", type=int, default=7)
    ap.add_argument("--selftest", action="store_true", help="用一段内置文字确认环境能跑通")
    a = ap.parse_args()
    t0 = time.time()
    try: os.makedirs(a.out, exist_ok=True)
    except OSError as e: die(f"不能创建输出文件夹 {a.out}：{e.strerror}")
    if a.selftest:
        raw = ("# Selftest weekly review\n\n## Results\n\n"
               "Alice: Revenue grew 25% to $12 million this quarter, which is ahead of our plan for the team.\n"
               "Bob: However, the churn risk is a concern because customer churn rose to 8% in the enterprise segment.\n"
               "Alice: We decided to prioritize the retention fix and we will ship the new version before June.\n"
               "Bob: The next step is that we need to finish the pricing research and follow up with finance.\n"
               "Carol: We agreed that onboarding time was reduced by 40% and that the problem is now mostly solved.\n\n## Plan\n\n"
               "Alice: Our target is 15% growth next quarter, and we plan to hire two support engineers soon.\n"
               "Bob: There is a risk that the pricing change will confuse existing customers, so we should test it first.\n"
               "Carol: Overall the team recommends launching the pilot in three regions and reporting back in 6 weeks.\n")
        name, src = "selftest", "selftest"
    elif a.outline:
        name, src, raw = a.name or os.path.splitext(os.path.basename(a.outline))[0], "", None
    else:
        if not a.input: ap.error("请给出输入文件，或用 --selftest")
        raw = read_text_file(a.input)
        name, src = a.name or os.path.splitext(os.path.basename(a.input))[0], os.path.basename(a.input)
    if a.outline:
        outline = load_outline(a.outline)
        name = a.name or "presentation"
    else:
        outline = analyze(raw, a.title, a.lang, src, a.max_slides)
        json.dump(outline, open(os.path.join(a.out, f"{name}.outline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    pptx = os.path.join(a.out, f"{name}.pptx")
    try: checks = build_pptx(outline, pptx)
    except ImportError: die("没有安装 python-pptx。请先运行：pip install python-pptx")
    except PermissionError: die(f"不能写入 {pptx}（文件可能正被 PowerPoint 打开，请先关掉）。")
    build_notes(outline, os.path.join(a.out, f"{name}.notes.md"))
    secs = time.time() - t0
    build_report(outline, checks, secs, os.path.join(a.out, f"{name}.report.html"), os.path.basename(pptx))
    bad = [c for c in checks if not c["fits"]]
    print(f"OK  {len(outline['slides'])} 页  用时 {secs:.2f}s  -> {pptx}")
    for c in checks:
        print(f"  第{c['n']}页 {c['title'][:28]:<30} {c['font']}pt  约{c['lines']}行  {'OK' if c['fits'] else '!! 可能溢出，请缩短文字'}")
    if not (5 <= len(outline["slides"]) <= 7): print(f"提示：只出了 {len(outline['slides'])} 页（目标 5-7 页）。通常是输入太短或太少完整发言：补充更多原话，或直接编辑 outline.json 加页。")
    if bad: print(f"提示：有 {len(bad)} 处估算可能溢出（上面标 !! 的），请缩短那几处文字后重新生成；这只是估算，以 report.html / 实际打开为准。")
    sys.exit(0)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(130)
    except SystemExit: raise
    except Exception as e:
        print(f"出错了：处理中遇到没预料到的问题（{type(e).__name__}: {e}）。\n  请检查输入文件内容；仍不行就带着这行提示和输入文件去提 issue。", file=sys.stderr); sys.exit(3)
