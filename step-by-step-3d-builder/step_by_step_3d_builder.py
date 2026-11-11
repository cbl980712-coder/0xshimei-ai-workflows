#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
step_by_step_3d_builder.py —— 分步拆解、逐部件自检、自动组装成单文件 Three.js 网页。

只用 Python 标准库（仅在 macOS + Python 3.9.6 + Chrome 上验证过） + 一个本机已有的 Chrome/Edge（无头模式做自检和截图）。不调用任何收费 API。
大模型（Claude Code / Cursor / 网页版聊天）负责"写每个部件的 JSON"，本脚本负责：
    拆解检查 → 逐部件自检（循环） → 组装 → 输出单文件 HTML + 报告。

常用命令（DIR = 一个项目目录，里面有 plan.json 和 parts/*.json）：
    doctor                      先跑这个，确认环境能用
    init DIR "描述"             建项目目录
    fetch DIR                   抓 plan.json 里 source_url 的真实网页文字到 DIR/source.txt
    prompt decompose DIR        打印"拆解"提示词（贴给大模型）
    prompt part DIR <id>        打印"单个部件"提示词
    prompt fix DIR <id>         打印"修复"提示词（会带上最近一次自检报错）
    check DIR                   只检查 plan.json（树、环、坐标、范围、源网页里有没有这个词），并打印装配图
    status DIR                  看哪些部件还没写，下一个该写谁
    test DIR [--only a,b]       在无头浏览器里循环挂载部件并自检
    build DIR [-o out.html] [--screenshot a.png] [--allow-fail]
"""
import argparse
import html as htmlmod
import json
import os
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "viewer_template.html"
PROMPTS = HERE / "prompts_3d_modular.md"
SHAPES = {"sphere", "box", "cylinder", "cone", "torus", "capsule", "tube", "gear", "scatter"}
PART_KEYS = {"shapes", "code", "anim", "update", "note"}


# ---------------------------------------------------------------- 小工具
def die(msg, code=1):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def load_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        die("找不到 %s：%s" % (what, path))
    except json.JSONDecodeError as e:
        die("%s 不是合法 JSON（第 %d 行第 %d 列）：%s\n   常见原因：把 ```json 代码围栏一起存进去了、多了结尾逗号、用了中文引号、注释没删。" % (what, e.lineno, e.colno, path))


def bound_arr(b):
    return list(b) if isinstance(b, (list, tuple)) else [b, b, b]


def find_browser():
    env = os.environ.get("BROWSER_BIN")
    if env and os.path.exists(env):
        return env
    cands = []
    if sys.platform == "darwin":
        for n in ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium"):
            cands.append("/Applications/%s.app/Contents/MacOS/%s" % (n, n))
    elif sys.platform.startswith("win"):
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
                cands.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
    else:
        for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
            w = shutil.which(n)
            if w:
                cands.append(w)
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def run_browser(browser, page, work, dump=True, screenshot=None, budget=20000, size="1400,860"):
    prof = tempfile.mkdtemp(prefix=".b3d-profile-", dir=str(work))
    try:
        cmd = [browser, "--headless=new", "--no-first-run", "--no-default-browser-check",
               "--user-data-dir=" + prof, "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
               "--ignore-gpu-blocklist", "--window-size=" + size, "--virtual-time-budget=%d" % budget]
        if screenshot:
            cmd.append("--screenshot=" + str(screenshot))
        elif dump:
            cmd.append("--dump-dom")
        cmd.append(Path(page).resolve().as_uri())
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=150)
        return r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def http_get(url, timeout=30):
    """先用 urllib；macOS 自带 Python 常见证书错误，就退回系统 curl。"""
    req = urllib.request.Request(url, headers={"User-Agent": "step-by-step-3d-builder/1.0 (educational tool)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), "urllib"
    except (ssl.SSLError, urllib.error.URLError) as e:
        if isinstance(e, urllib.error.URLError) and not isinstance(getattr(e, "reason", None), ssl.SSLError) and "CERTIFICATE" not in str(e):
            raise
        curl = shutil.which("curl") or shutil.which("curl.exe")
        if not curl:
            raise
        r = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", "step-by-step-3d-builder/1.0", url],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0 or not r.stdout:
            raise RuntimeError("curl 也失败了: " + r.stderr.decode("utf-8", "replace")[:200])
        return r.stdout, "curl（urllib 证书校验失败后的回退）"


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self.out, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "tr", "br"):
            self.out.append("\n")

    def handle_data(self, d):
        if not self.depth:
            self.out.append(d)


def html_to_text(raw):
    p = _Text()
    p.feed(raw)
    txt = htmlmod.unescape("".join(p.out))
    txt = re.sub(r"\[\d+\]|\[edit\]", "", txt)
    txt = re.sub(r"[ \t\r\f]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


# ---------------------------------------------------------------- 拆解检查
def topo(parts):
    byid = {p["id"]: p for p in parts}
    order, state = [], {}

    def visit(i, stack):
        if state.get(i) == 2:
            return
        if state.get(i) == 1:
            raise ValueError("循环依赖: " + " → ".join(stack + [i]))
        state[i] = 1
        p = byid[i]
        deps = ([p["parent"]] if p.get("parent") else []) + list(p.get("depends_on", []))
        for d in deps:
            visit(d, stack + [i])
        state[i] = 2
        order.append(p)

    for p in parts:
        visit(p["id"], [])
    return order


def world_positions(plan):
    byid = {p["id"]: p for p in plan["parts"]}
    cache = {}

    def w(i):
        if i in cache:
            return cache[i]
        p = byid[i]
        base = w(p["parent"]) if p.get("parent") else [0, 0, 0]
        cache[i] = [round(base[k] + p["position"][k], 4) for k in range(3)]
        return cache[i]

    return {p["id"]: w(p["id"]) for p in plan["parts"]}


def read_source(d):
    f = Path(d) / "source.txt"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def evidence_for(part, source):
    low = source.lower()
    return [{"term": t, "count": low.count(t.lower())} for t in part.get("source_terms", [])]


def check_plan(plan, source=""):
    errs, warns = [], []
    if not isinstance(plan, dict):
        return ["plan.json 顶层必须是 { ... } 对象（里面有 parts 列表），现在是 %s。照 examples/*/plan.json 的格式写。" % type(plan).__name__], [], []
    parts = plan.get("parts")
    if not parts:
        return ["plan.json 里没有 parts（还没拆解？先跑 prompt decompose，把大模型给的 JSON 存成 plan.json）"], [], []
    if not isinstance(parts, list) or not all(isinstance(x, dict) for x in parts):
        return ["plan.json 的 parts 必须是对象列表 [ {id:..., name:...}, ... ]"], [], []
    if source is not None and not source.strip() and any(x.get("source_terms") for x in parts):
        warns.append("source.txt 不存在或为空，部件的依据词（source_terms）没有被核对；先跑 fetch，或把资料正文存成 source.txt")
    ids = [p.get("id") for p in parts]
    for i, p in enumerate(parts):
        for k in ("id", "name", "position", "bound"):
            if k not in p:
                errs.append("第 %d 个部件缺字段 %s" % (i + 1, k))
        if p.get("id") and not re.match(r"^[a-z][a-z0-9_]*$", p["id"]):
            errs.append("id「%s」只能是小写字母/数字/下划线，且字母开头" % p["id"])
        if "position" in p and (not isinstance(p["position"], list) or len(p["position"]) != 3):
            errs.append("%s 的 position 必须是 3 个数字" % p.get("id"))
    if errs:
        return errs, warns, []
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errs.append("id 重复: %s" % ", ".join(sorted(dup)))
    idset = set(ids)
    for p in parts:
        if p.get("parent") and p["parent"] not in idset:
            errs.append("%s 的 parent「%s」不存在" % (p["id"], p["parent"]))
        for d in p.get("depends_on", []):
            if d not in idset:
                errs.append("%s 的 depends_on「%s」不存在" % (p["id"], d))
    if errs:
        return errs, warns, []
    try:
        order = topo(parts)
    except ValueError as e:
        return [str(e)], warns, []

    byid = {p["id"]: p for p in parts}
    world = world_positions(plan)
    for p in parts:
        par = byid.get(p.get("parent"))
        mode = p.get("inside", True if par else False)
        if par and mode:
            pb, cb = bound_arr(par["bound"]), bound_arr(p["bound"])
            axes = (0, 2) if mode == "xz" else (0, 1, 2)
            # 在子部件的 bound 球/椭球表面取 26 个方向的点，逐个检查是否落在父部件 bound 内
            worst = 0.0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        if dx == dy == dz == 0:
                            continue
                        d = (dx, dy, dz)
                        ln = sum(c * c for c in d) ** 0.5
                        pt = [p["position"][k] + cb[k] * d[k] / ln for k in range(3)]
                        worst = max(worst, sum((pt[k] / pb[k]) ** 2 for k in axes) ** 0.5)
            if worst > 1.03:
                errs.append("装配冲突：「%s」放不进「%s」——bound 表面最远点达到父部件范围的 %.0f%%（>100%%）。缩小 bound 或移近中心。"
                            % (p["name"], par["name"], worst * 100))
        if source and p.get("source_terms"):
            ev = evidence_for(p, source)
            if all(e["count"] == 0 for e in ev):
                warns.append("「%s」的 source_terms %s 在源网页里一次都没出现——可能是编的，或者该换个词" % (p["name"], p["source_terms"]))
    # 同级重叠不在这里查：bound 只是"活动范围"，范围球重叠很常见（19 条误报教训），真实几何的包围盒重叠留给浏览器自检。
    return errs, warns, order


def assembly_text(plan, order):
    byid = {p["id"]: p for p in plan["parts"]}
    world = world_positions(plan)
    lines = ["装配图：%s" % plan.get("title", ""), "格式：名称 (id)  相对父部件坐标 → 世界坐标  bound", ""]

    def walk(pid, prefix, last):
        p = byid[pid]
        lines.append("%s%s%s (%s)  %s → %s  bound=%s" % (prefix, "└─ " if last else "├─ ", p["name"], pid,
                                                      json.dumps(p["position"]), json.dumps(world[pid]), json.dumps(p["bound"])))
        kids = [q["id"] for q in plan["parts"] if q.get("parent") == pid]
        for i, k in enumerate(kids):
            walk(k, prefix + ("   " if last else "│  "), i == len(kids) - 1)

    roots = [p["id"] for p in plan["parts"] if not p.get("parent")]
    for i, r in enumerate(roots):
        walk(r, "", i == len(roots) - 1)
    lines += ["", "建造顺序（先父后子、先依赖后使用）：", "  " + " → ".join(p["id"] for p in order)]
    return "\n".join(lines)


# ---------------------------------------------------------------- 部件文件
def part_file(d, pid):
    return Path(d) / "parts" / (pid + ".json")


def validate_part_json(pid, data):
    errs = []
    if not isinstance(data, dict):
        return ["%s.json 顶层必须是对象" % pid]
    for k in data:
        if k not in PART_KEYS:
            errs.append("%s.json 里有不认识的字段「%s」（不要把 position / bound 写进部件文件，位置由 plan.json 决定）" % (pid, k))
    if not isinstance(data.get("shapes") or [], list):
        return ["%s.json 的 shapes 必须是列表 [ {...}, ... ]" % pid]
    for i, s in enumerate(data.get("shapes") or []):
        if not isinstance(s, dict):
            errs.append("%s 第 %d 个 shape 必须是 { \"type\": ... } 对象" % (pid, i + 1))
            continue
        if s.get("type") not in SHAPES:
            errs.append("%s 第 %d 个 shape 的 type「%s」不在 %s 里" % (pid, i + 1, s.get("type"), sorted(SHAPES)))
    if not data.get("shapes") and not data.get("code"):
        errs.append("%s.json 既没有 shapes 也没有 code" % pid)
    if data.get("code") and "Math.random" in data["code"]:
        errs.append("%s 的 code 里用了 Math.random()：每次刷新形状都会变，请用 ctx.rngFrom(种子)" % pid)
    return errs


def make_spec(d, plan, only=None, need_all=False):
    d = Path(d)
    source = read_source(d)
    errs, warns, order = check_plan(plan, source)
    if errs:
        return None, errs, [], []
    have = {p["id"] for p in order if part_file(d, p["id"]).exists()}
    missing = [p["id"] for p in order if p["id"] not in have]
    if need_all and missing:
        return None, ["还没写部件文件: " + ", ".join(missing)], [], missing
    want = None
    if only:
        byid = {p["id"]: p for p in plan["parts"]}
        want = set()

        def add(i):
            if i in want:
                return
            want.add(i)
            if byid[i].get("parent"):
                add(byid[i]["parent"])
            for x in byid[i].get("depends_on", []):
                add(x)

        for i in only:
            if i not in byid:
                return None, ["--only 里的 %s 不在 plan.json" % i], [], []
            add(i)
    included, skipped, perrs = [], [], []
    inc_ids = set()
    for p in order:
        if want is not None and p["id"] not in want:
            continue
        deps = ([p["parent"]] if p.get("parent") else []) + list(p.get("depends_on", []))
        if p["id"] in have and all(x in inc_ids for x in deps):
            geo = load_json(part_file(d, p["id"]), p["id"] + ".json")
            perrs += validate_part_json(p["id"], geo)
            item = dict(p)
            item.update(geo)
            item["evidence"] = evidence_for(p, source)
            included.append(item)
            inc_ids.add(p["id"])
        else:
            skipped.append(p["id"])
    spec = {"title": plan.get("title", "3D 模型"), "subtitle": plan.get("subtitle", ""), "source_url": plan.get("source_url", ""),
            "background": plan.get("background", "#0b1020"), "camera": plan.get("camera", {}), "parts": included}
    return spec, perrs, skipped, missing


def render_html(spec, out_path):
    tpl = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")
    page = tpl.replace("/*__SPEC__*/null", blob).replace("__TITLE__", htmlmod.escape(spec["title"]))
    Path(out_path).write_text(page, encoding="utf-8")


def browser_test(d, spec, browser):
    d = Path(d)
    tmp = d / ".b3d_test.html"
    render_html(spec, tmp)
    t0 = time.time()
    try:
        out, err = run_browser(browser, tmp, d)
    finally:
        tmp.unlink(missing_ok=True)
    secs = time.time() - t0
    m = re.search(r'<pre id="build-report"[^>]*>(.*?)</pre>', out, re.S)
    if not m or not m.group(1).strip():
        return None, secs, "没拿到自检报告。多半是加载 three.js 失败（需要能访问 cdn.jsdelivr.net），或页面脚本整体崩了。浏览器输出: " + (err or out)[-300:]
    return json.loads(htmlmod.unescape(m.group(1))), secs, None


def print_report(rep):
    for r in rep["parts"]:
        print("  %s %-18s %-10s %6.1f ms%s" % ("✓" if r["ok"] else "✗", r["name"], r["id"], r["ms"],
                                             "" if not r.get("extent") else "  实测尺寸 " + " × ".join("%.2f" % x for x in r["extent"])))
        for i in r["issues"]:
            print("      ✗ " + i)
        for w in r["warnings"]:
            print("      ! " + w)


# ---------------------------------------------------------------- 命令
def cmd_doctor(a):
    ok = True
    print("Python  : %s  %s" % (sys.version.split()[0], "✓" if sys.version_info >= (3, 8) else "✗ 需要 3.8+"))
    ok &= sys.version_info >= (3, 8)
    b = find_browser()
    print("浏览器  : %s" % (b if b else "✗ 没找到 Chrome / Edge。装一个，或设置环境变量 BROWSER_BIN 指向它的可执行文件"))
    ok &= bool(b)
    for f in (TEMPLATE, PROMPTS):
        print("%-8s: %s" % (f.name[:8], "✓" if f.exists() else "✗ 缺文件 " + f.name))
        ok &= f.exists()
    if b:
        with tempfile.TemporaryDirectory(dir=str(HERE)) as td:
            spec = {"title": "doctor", "background": "#000", "camera": {}, "parts": [
                {"id": "ball", "name": "球", "parent": None, "position": [0, 0, 0], "bound": 1.2,
                 "shapes": [{"type": "sphere", "r": 1, "color": "#4aa3ff"}]},
                {"id": "gear", "name": "齿轮", "parent": "ball", "position": [0, 0, 0], "bound": 0.8,
                 "shapes": [{"type": "gear", "module": 0.1, "teeth": 12, "thick": 0.1, "hole": 0.1}], "anim": {"rotate": [0, 1, 0]}}]}
            t0 = time.time()
            rep, secs, err = browser_test(td, spec, b)
        if rep and rep["passed"] == rep["total"]:
            print("端到端  : ✓ 无头浏览器 + three.js(CDN) 自检通过（%.1f 秒）" % secs)
        else:
            ok = False
            print("端到端  : ✗ %s" % (err or json.dumps(rep, ensure_ascii=False)[:300]))
    print("\n环境" + ("OK，可以开始了。" if ok else "还有问题，按上面 ✗ 处理后重跑 doctor。"))
    sys.exit(0 if ok else 1)


def cmd_init(a):
    d = Path(a.dir)
    (d / "parts").mkdir(parents=True, exist_ok=True)
    plan = {"title": a.description, "subtitle": "", "description": a.description, "source_url": a.url or "",
            "background": "#0b1020", "camera": {"position": [0, 3, 10], "target": [0, 0, 0]}, "parts": []}
    p = d / "plan.json"
    if a.url and not re.match(r"^https?://\S+$", a.url):
        die("--url 必须是 http:// 或 https:// 开头、中间没有空格的网址，现在是：%s" % a.url)
    if p.exists():
        die("%s 已经存在，不覆盖" % p)
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✓ 已建 %s。下一步：python3 %s prompt decompose %s" % (p, Path(sys.argv[0]).name, shlex.quote(str(d))))


def cmd_fetch(a):
    d = Path(a.dir)
    plan = load_json(d / "plan.json", "plan.json")
    url = a.url or plan.get("source_url")
    if not url:
        die("plan.json 里没有 source_url，也没传 --url")
    t0 = time.time()
    try:
        raw, how = http_get(url)
    except urllib.error.HTTPError as e:
        die("抓取失败：%s 返回 HTTP %d。网址是不是写错了？（浏览器里先打开确认能看到页面）" % (url, e.code))
    except Exception as e:
        die("抓取失败：%s（没网、被墙或证书问题；可以自己把网页正文存成 %s/source.txt 再继续）" % (e, d))
    txt = html_to_text(raw.decode("utf-8", "replace"))
    (d / "source.txt").write_text(txt, encoding="utf-8")
    meta = {"url": url, "bytes_html": len(raw), "chars_text": len(txt), "via": how, "seconds": round(time.time() - t0, 2),
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (d / "source.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✓ 抓到 %s：HTML %d 字节 → 文字 %d 字符，经由 %s，用时 %.2f 秒" % (url, len(raw), len(txt), how, meta["seconds"]))
    if len(txt) < 5000:
        print("! 只抓到 %d 个字符，偏少：可能是「消歧义页」、跳转页或需要登录的页面，里面不一定有部件名。建议换一个更具体的页面，或自己把正文存成 %s/source.txt。" % (len(txt), shlex.quote(str(d))))


def _fill(tpl, kv):
    for k, v in kv.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl


def _template(name):
    m = re.search(r"<!-- template: %s -->\s*```text\n(.*?)\n```" % name, PROMPTS.read_text(encoding="utf-8"), re.S)
    if not m:
        die("prompts_3d_modular.md 里找不到模板 " + name)
    return m.group(1)


def _inside_rule(plan, p):
    par = next((q for q in plan["parts"] if q["id"] == p.get("parent")), None)
    mode = p.get("inside", True if par else False)
    if not par or not mode:
        return "无（可以在父部件之外）"
    return "所有顶点必须落在「%s」的 bound=%s 之内（%s）" % (par["name"], json.dumps(par["bound"]), "仅水平投影" if mode == "xz" else "三维")


def cmd_prompt(a):
    d = Path(a.dir)
    plan = load_json(d / "plan.json", "plan.json")
    src = read_source(d)
    if a.kind == "decompose":
        block = ("下面是真实资料（节选），部件只能来自这里：\n-----\n%s\n-----" % src[:6000]) if src else "（没有提供资料，请只用你有把握的常识部件。）"
        print(_fill(_template("decompose"), {"description": plan.get("description", plan.get("title", "")),
                                             "source_block": block, "source_url": plan.get("source_url", "")}))
        return
    if not a.part:
        die("prompt %s 需要再给一个部件 id" % a.kind)
    byid = {p["id"]: p for p in plan["parts"]}
    if a.part not in byid:
        die("plan.json 里没有部件 " + a.part)
    p = byid[a.part]
    par = byid.get(p.get("parent"))
    done = [q["name"] + "(" + q["id"] + ")" for q in plan["parts"] if part_file(d, q["id"]).exists() and q["id"] != a.part]
    kv = {"part_name": p["name"], "part_id": p["id"], "title": plan.get("title", ""), "part_desc": p.get("desc", ""),
          "parent_name": par["name"] if par else "世界原点", "position": json.dumps(p["position"]), "bound": json.dumps(p["bound"]),
          "inside_rule": _inside_rule(plan, p), "done_parts": "、".join(done) or "（还没有）"}
    if a.kind == "part":
        print(_fill(_template("part"), kv))
    else:
        last = d / ".last_report.json"
        issues = "（没有找到最近一次自检报告，请先跑 test）"
        if last.exists():
            rep = json.loads(last.read_text(encoding="utf-8"))
            r = next((x for x in rep["parts"] if x["id"] == a.part), None)
            if r:
                issues = "\n".join(["- " + i for i in r["issues"]] + ["- (提醒) " + w for w in r["warnings"]]) or "（该部件已通过）"
        pf = part_file(d, a.part)
        kv.update({"issues": issues, "previous_json": pf.read_text(encoding="utf-8") if pf.exists() else "{}"})
        print(_fill(_template("fix"), kv))


def cmd_check(a):
    d = Path(a.dir)
    plan = load_json(d / "plan.json", "plan.json")
    t0 = time.time()
    errs, warns, order = check_plan(plan, read_source(d))
    for e in errs:
        print("✗ " + e)
    for w in warns:
        print("! " + w)
    if errs:
        sys.exit(1)
    txt = assembly_text(plan, order)
    (d / "assembly.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print("\n✓ plan 检查通过：%d 个部件，%d 条提醒，用时 %.2f 秒（装配图已写入 assembly.txt）" % (len(order), len(warns), time.time() - t0))


def cmd_status(a):
    d = Path(a.dir)
    plan = load_json(d / "plan.json", "plan.json")
    errs, _, order = check_plan(plan, read_source(d))
    if errs:
        die("plan 有问题，先 check：" + errs[0])
    nxt = None
    for p in order:
        f = part_file(d, p["id"])
        mark, note = "·", ""
        if f.exists():
            try:
                bad = validate_part_json(p["id"], json.loads(f.read_text(encoding="utf-8")))
                mark, note = ("✗", "文件有问题：" + bad[0]) if bad else ("✓", "")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                mark, note = "✗", "文件为空或不是合法 JSON，需要重写"
        print("  %s %-12s %s  %s" % (mark, p["id"], p["name"], note))
        if mark != "✓" and nxt is None:
            nxt = p["id"]
    print("\n（✓ 只表示文件在且格式对；是否通过几何自检要跑 test）")
    print("下一个该写：%s" % (nxt or "（全部写完了，可以 build）"))
    if nxt:
        print("命令：python3 %s prompt part %s %s" % (Path(sys.argv[0]).name, shlex.quote(str(d)), nxt))


def _need_browser():
    b = find_browser()
    if not b:
        die("没找到 Chrome / Edge，无法做浏览器里的自检。先跑 doctor 看说明。")
    return b


def cmd_test(a):
    d = Path(a.dir)
    plan = load_json(d / "plan.json", "plan.json")
    only = a.only.split(",") if a.only else None
    spec, errs, skipped, _ = make_spec(d, plan, only)
    if spec is None or errs:
        for e in errs:
            print("✗ " + e)
        sys.exit(1)
    if skipped:
        print("（跳过还没写的部件/依赖它们的部件: %s）" % ", ".join(skipped))
    rep, secs, err = browser_test(d, spec, _need_browser())
    if err:
        die(err)
    print_report(rep)
    (d / ".last_report.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    bad = rep["total"] - rep["passed"]
    print("\n%s 自检 %d/%d 通过，%d 条提醒，浏览器往返 %.1f 秒" % ("✓" if not bad else "✗", rep["passed"], rep["total"], rep["warnings"], secs))
    sys.exit(1 if bad else 0)


def cmd_build(a):
    d = Path(a.dir)
    log = {"stages": {}}
    t_all = time.time()

    def stage(name, t0):
        log["stages"][name] = round(time.time() - t0, 2)

    t0 = time.time()
    plan = load_json(d / "plan.json", "plan.json")
    errs, warns, order = check_plan(plan, read_source(d))
    for w in warns:
        print("! " + w)
    if errs:
        for e in errs:
            print("✗ " + e)
        sys.exit(1)
    (d / "assembly.txt").write_text(assembly_text(plan, order), encoding="utf-8")
    stage("plan_check", t0)

    t0 = time.time()
    spec, perrs, _, _ = make_spec(d, plan, need_all=True)
    if spec is None or perrs:
        for e in perrs:
            print("✗ " + e)
        sys.exit(1)
    stage("load_parts", t0)

    t0 = time.time()
    rep, secs, err = browser_test(d, spec, _need_browser())
    if err:
        die(err)
    stage("browser_test", t0)
    print_report(rep)
    (d / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = rep["total"] - rep["passed"]
    if bad and not a.allow_fail:
        print("\n✗ 有 %d 个部件没通过自检，未输出 HTML（想先看看效果就加 --allow-fail）。" % bad)
        sys.exit(1)

    t0 = time.time()
    out = Path(a.output) if a.output else d / "index.html"
    render_html(spec, out)
    stage("assemble", t0)

    if a.screenshot:
        t0 = time.time()
        _, e = run_browser(_need_browser(), out, d, dump=False, screenshot=Path(a.screenshot).resolve(), budget=15000)
        stage("screenshot", t0)
    log["total_seconds"] = round(time.time() - t_all, 2)
    log["parts"] = rep["total"]
    log["passed"] = rep["passed"]
    log["warnings"] = rep["warnings"]
    log["output_bytes"] = out.stat().st_size
    (d / "run_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n✓ 输出 %s（%.0f KB），自检 %d/%d，脚本总用时 %.1f 秒（各阶段 %s）" %
          (out, out.stat().st_size / 1024, rep["passed"], rep["total"], log["total_seconds"], json.dumps(log["stages"])))
    print("\n⚠ 几何自检通过不等于模型外观正确：自检只查尺寸和范围，不查部件之间有没有连上、整体像不像。\n"
          "  请打开 %s 人工检查连接关系和整体形状（可参考 examples/04-anglepoise-lamp：8/8 通过但上下灯臂没接上）。" % out)


def main():
    ap = argparse.ArgumentParser(description="分步拆解 → 逐部件自检 → 组装成单文件 Three.js 网页")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("init"); s.add_argument("dir"); s.add_argument("description"); s.add_argument("--url"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("fetch"); s.add_argument("dir"); s.add_argument("--url"); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("prompt"); s.add_argument("kind", choices=["decompose", "part", "fix"]); s.add_argument("dir"); s.add_argument("part", nargs="?"); s.set_defaults(fn=cmd_prompt)
    s = sub.add_parser("check"); s.add_argument("dir"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("status"); s.add_argument("dir"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("test"); s.add_argument("dir"); s.add_argument("--only"); s.set_defaults(fn=cmd_test)
    s = sub.add_parser("build"); s.add_argument("dir"); s.add_argument("-o", "--output"); s.add_argument("--screenshot")
    s.add_argument("--allow-fail", action="store_true"); s.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        sys.exit(0)
    a.fn(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
