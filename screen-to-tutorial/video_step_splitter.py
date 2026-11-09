#!/usr/bin/env python3
"""video_step_splitter.py - screen recording -> key frames -> illustrated HTML tutorial cards.

Two sub-commands:

  extract  INPUT -o OUT   INPUT = a screen recording (mp4/mov/webm/...) or a folder of screenshots
                          (sorted by file name). Detects "the screen really changed" moments, ignoring
                          mouse-cursor movement, and writes OUT/frames/step_XX.jpg, OUT/candidates.json,
                          OUT/contact_sheet.jpg and OUT/steps.draft.json.
  render   STEPS_JSON     Fills step_card_template.html with a steps.json (titles + descriptions written
                          by Claude / by you) and writes one HTML file (add --embed to inline the images).

Needs: Python 3.8+, Pillow, numpy; ffmpeg only when INPUT is a video.
"""
import argparse
import base64
import glob
import html
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
SMALL_W, SMALL_H = 320, 180  # analysis resolution


# ----------------------------------------------------------------------------- loading
def load_frames(src, work, fps, width):
    """Return list of (time_seconds, path) of frames resized to `width`."""
    if os.path.isdir(src):
        files = sorted(f for f in glob.glob(os.path.join(src, "*")) if f.lower().endswith(IMG_EXT))
        if not files:
            sys.exit("No images (png/jpg/webp) found in folder: %s" % src)
        out = []
        for i, f in enumerate(files):
            im = Image.open(f).convert("RGB")
            h = round(im.height * width / im.width)
            p = os.path.join(work, "f_%05d.jpg" % i)
            im.resize((width, h), Image.LANCZOS).save(p, quality=90)
            out.append((float(i), p))
        return out
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found. Install it (macOS: brew install ffmpeg) or pass a folder of screenshots.")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-vf", "fps=%s,scale=%d:-2" % (fps, width),
           "-q:v", "3", os.path.join(work, "f_%05d.jpg")]
    r = subprocess.run(cmd, stderr=subprocess.PIPE, universal_newlines=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed: " + r.stderr[-400:])
    files = sorted(glob.glob(os.path.join(work, "f_*.jpg")))
    if not files:
        sys.exit("ffmpeg produced no frames - is the file a valid video?")
    return [(i / float(fps), f) for i, f in enumerate(files)]


def small_gray(path):
    im = Image.open(path).convert("L").resize((SMALL_W, SMALL_H), Image.BILINEAR)
    return np.asarray(im, dtype=np.int16)


# ----------------------------------------------------------------------------- diffing
def _components(mask):
    """Connected components (8-neighbour) of a bool mask -> list of (pixels, x0, y0, x1, y1)."""
    ys, xs = np.nonzero(mask)
    todo = set(zip(ys.tolist(), xs.tolist()))
    comps = []
    while todo:
        seed = todo.pop()
        stack, pix = [seed], [seed]
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (y + dy, x + dx)
                    if n in todo:
                        todo.discard(n)
                        stack.append(n)
                        pix.append(n)
        py = [p[0] for p in pix]
        px = [p[1] for p in pix]
        comps.append((len(pix), min(px), min(py), max(px), max(py)))
    return comps


def dilate(m):
    o = m.copy()
    o[1:, :] |= m[:-1, :]
    o[:-1, :] |= m[1:, :]
    o[:, 1:] |= o[:, :-1].copy()
    o[:, :-1] |= o[:, 1:].copy()
    return o


def change(a, b, pix_thr, cursor_px):
    """Meaningful change between two small gray frames.

    Returns (count, bbox or None). Blobs no bigger than `cursor_px` in both directions (mouse cursor,
    text caret, a single typed character) are ignored. Huge changes skip the blob filter."""
    mask = np.abs(a - b) > pix_thr
    n = int(mask.sum())
    if n == 0:
        return 0, None
    if n > 0.06 * mask.size:  # page switch / dialog: no need to filter anything
        ys, xs = np.nonzero(mask)
        return n, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    mask = dilate(mask)
    count, box = 0, None
    for c, x0, y0, x1, y1 in _components(mask):
        if (x1 - x0 + 1) <= cursor_px and (y1 - y0 + 1) <= cursor_px:
            continue
        count += c
        box = (x0, y0, x1, y1) if box is None else (min(box[0], x0), min(box[1], y0), max(box[2], x1), max(box[3], y1))
    return count, box


# ----------------------------------------------------------------------------- detection
def detect(grays, times, thr, settle, gap, pix_thr, cursor_px):
    """State machine: compare every frame with the last accepted key frame; when it differs, wait until
    the screen has been calm for `settle` frames, then accept the first calm frame as a new key frame."""
    n = len(grays)
    calm_cnt = max(1, int(thr * SMALL_W * SMALL_H * 0.5))
    # 起点画面跳过开头的纯色画面（网页还在加载的白屏、黑屏），取第一张有内容的
    s0 = 0
    while s0 < n - 1 and float(grays[s0].std()) < 8:
        s0 += 1
    keys = [{"idx": s0, "score": 0, "box": None}]
    ref = s0
    i = s0 + 1
    while i < n:
        cnt, _ = change(grays[ref], grays[i], pix_thr, cursor_px)
        if cnt < thr * SMALL_W * SMALL_H:
            i += 1
            continue
        # screen is different from reference - find the first calm moment
        j = i
        found = None
        while j < n:
            ok = True
            for k in range(j, min(j + settle, n)):
                c, _ = change(grays[max(0, k - gap)], grays[k], pix_thr, cursor_px)
                if c > calm_cnt:
                    ok = False
                    break
            if ok and (j + settle <= n or j == n - 1):
                found = j
                break
            j += 1
        if found is None:
            found = n - 1
        cnt, box = change(grays[ref], grays[found], pix_thr, cursor_px)
        if cnt >= thr * SMALL_W * SMALL_H:
            keys.append({"idx": found, "score": cnt, "box": box})
            ref = found
        i = found + 1
    return keys


def _inside(inner, outer, slack=4):
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack
            and inner[2] <= outer[2] + slack and inner[3] <= outer[3] + slack)


def merge_followups(keys, times, merge_gap, ratio=0.5):
    """Typing is invisible to the cursor filter frame-by-frame, so one typed sentence can produce two key
    frames ("Li" and "Lin Wei"). If a key frame comes within `merge_gap` seconds, changes inside the previous
    key frame's changed box and is much weaker (< ratio x), treat it as a continuation: keep the later frame."""
    if merge_gap <= 0:
        return keys
    out = [keys[0]]
    for k in keys[1:]:
        p = out[-1]
        if (len(out) > 1 and p["box"] and k["box"] and times[k["idx"]] - times[p["idx"]] <= merge_gap
                and _inside(k["box"], p["box"]) and k["score"] < ratio * p["score"]):
            out[-1] = {"idx": k["idx"], "score": p["score"] + k["score"],
                       "box": (min(p["box"][0], k["box"][0]), min(p["box"][1], k["box"][1]),
                               max(p["box"][2], k["box"][2]), max(p["box"][3], k["box"][3])), "merged": True}
        else:
            out.append(k)
    return out


def detect_shots(grays, thr, pix_thr, cursor_px):
    """Screenshot-folder mode: every image is already a settled state, so just drop near-duplicates."""
    keys, ref = [{"idx": 0, "score": 0, "box": None}], 0
    for i in range(1, len(grays)):
        cnt, box = change(grays[ref], grays[i], pix_thr, cursor_px)
        if cnt >= thr * SMALL_W * SMALL_H:
            keys.append({"idx": i, "score": cnt, "box": box})
            ref = i
    return keys


def pick(keys, max_steps):
    """Keep the start frame + at most `max_steps` strongest changes, in time order."""
    body = keys[1:]
    if len(body) > max_steps:
        top = sorted(body, key=lambda k: -k["score"])[:max_steps]
        body = sorted(top, key=lambda k: k["idx"])
    return [keys[0]] + body


def box_pct(box):
    if box is None:
        return None
    x0, y0, x1, y1 = box
    x, y = x0 / SMALL_W * 100, y0 / SMALL_H * 100
    w, h = (x1 - x0 + 1) / SMALL_W * 100, (y1 - y0 + 1) / SMALL_H * 100
    if w * h > 0.55 * 100 * 100:  # whole-screen changes (dialog dimming) -> no useful box
        return None
    pad = 0.8
    x, y = max(0, x - pad), max(0, y - pad)
    return [round(x, 1), round(y, 1), round(min(100 - x, w + 2 * pad), 1), round(min(100 - y, h + 2 * pad), 1)]


def mmss(t):
    return "%02d:%02d" % (int(t) // 60, int(t) % 60)


def contact_sheet(paths, labels, out, cols=3, cw=520):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ch = round(ims[0].height * cw / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 8) + 8), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = 8 + (i % cols) * (cw + 8), 8 + (i // cols) * (ch + 8)
        sheet.paste(im.resize((cw, ch), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + 150, y + 26), fill=(220, 38, 38))
        d.text((x + 8, y + 6), labels[i], fill=(255, 255, 255))
    sheet.save(out, quality=88)


# ----------------------------------------------------------------------------- extract
def cmd_extract(a):
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    fdir = os.path.join(a.out, "frames")
    if os.path.isdir(fdir):
        shutil.rmtree(fdir)
    os.makedirs(fdir)
    work = tempfile.mkdtemp(prefix="vss_")
    try:
        frames = load_frames(a.input, work, a.fps, a.width)
        times = [t for t, _ in frames]
        grays = [small_gray(p) for _, p in frames]
        thr, keys = a.threshold, []
        for attempt in range(4):  # too few steps -> be more sensitive and retry
            if os.path.isdir(a.input):
                keys = detect_shots(grays, thr, a.pixel_diff, a.cursor_size)
            else:
                keys = merge_followups(detect(grays, times, thr, a.settle, a.gap, a.pixel_diff, a.cursor_size),
                                       times, a.merge_gap)
            if len(keys) - 1 >= a.min_steps:
                break
            print("  only %d change(s) at threshold %.4f -> retrying more sensitive" % (len(keys) - 1, thr))
            thr *= 0.5
        found = len(keys) - 1
        keys = pick(keys, a.max_steps)
        cands, paths, labels, draft = [], [], [], []
        for n, k in enumerate(keys):
            name = "step_%02d.jpg" % n
            dst = os.path.join(fdir, name)
            shutil.copy(frames[k["idx"]][1], dst)
            rel = "frames/" + name
            bp = box_pct(k["box"])
            cands.append({"file": rel, "time": round(times[k["idx"]], 2), "time_label": mmss(times[k["idx"]]),
                          "change_score": k["score"], "changed_box_pct": bp, "is_start_frame": n == 0})
            paths.append(dst)
            labels.append("#%d  %s" % (n, mmss(times[k["idx"]])))
            if n > 0:
                draft.append({"image": rel, "time": mmss(times[k["idx"]]), "title": "", "desc": "", "box": bp, "click": None})
        contact_sheet(paths, labels, os.path.join(a.out, "contact_sheet.jpg"))
        with open(os.path.join(a.out, "candidates.json"), "w", encoding="utf-8") as f:
            json.dump({"source": os.path.basename(a.input.rstrip("/")), "frames_analysed": len(frames),
                       "changes_found_before_pruning": found, "kept_steps": len(keys) - 1, "threshold_used": thr,
                       "frames": cands}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(a.out, "steps.draft.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "", "subtitle": "", "start_image": "frames/step_00.jpg", "steps": draft}, f,
                      ensure_ascii=False, indent=2)
        print("extract: %d frames analysed, %d change(s) found, %d step(s) kept, %.1fs"
              % (len(frames), found, len(keys) - 1, time.time() - t0))
        for c in cands:
            print("  %s  t=%s  score=%s  box=%s" % (c["file"], c["time_label"], c["change_score"], c["changed_box_pct"]))
        print("next: look at %s/contact_sheet.jpg (or every frames/*.jpg) and fill steps.draft.json" % a.out)
        if found < a.min_steps:
            print("WARNING: fewer than --min-steps changes detected; try --threshold 0.0005 or check the input.")
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------------- render
LABELS = {
    "zh": {"step": "步骤", "start": "起点", "total": "共 %d 步", "overview": "操作概览", "lang": "zh-CN"},
    "en": {"step": "Step", "start": "Start", "total": "%d steps", "overview": "Overview", "lang": "en"},
}


def img_src(path, base, embed):
    full = path if os.path.isabs(path) else os.path.join(base, path)
    if not os.path.exists(full):
        sys.exit("image not found: %s" % full)
    if embed:
        im = Image.open(full).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    return full


def cmd_render(a):
    base = os.path.dirname(os.path.abspath(a.steps))
    data = json.load(open(a.steps, encoding="utf-8"))
    tpl = open(a.template, encoding="utf-8").read()
    L = LABELS[a.lang]
    s, e = tpl.index("<!--CARD_START-->"), tpl.index("<!--CARD_END-->")
    card_tpl = tpl[s + len("<!--CARD_START-->"):e]
    out_dir = os.path.dirname(os.path.abspath(a.output))
    cards, toc = [], []
    steps = data["steps"]
    for i, st in enumerate(steps, 1):
        if not st.get("title"):
            sys.exit("step %d has no title - fill steps.json first" % i)
        src = img_src(st["image"], base, a.embed)
        if not a.embed:
            src = os.path.relpath(src, out_dir)
        overlay = ""
        if st.get("box"):
            x, y, w, h = st["box"]
            overlay += '<span class="box" style="left:%s%%;top:%s%%;width:%s%%;height:%s%%"></span>' % (x, y, w, h)
        if st.get("click"):
            overlay += '<span class="dot" style="left:%s%%;top:%s%%"></span>' % tuple(st["click"])
        desc = "".join("<p>%s</p>" % html.escape(p) for p in str(st.get("desc", "")).split("\n") if p.strip())
        tip = '<p class="tip">%s</p>' % html.escape(st["tip"]) if st.get("tip") else ""
        card = (card_tpl.replace("{{N}}", str(i)).replace("{{STEP_LABEL}}", L["step"])
                .replace("{{CARD_TITLE}}", html.escape(st["title"])).replace("{{CARD_DESC}}", desc + tip)
                .replace("{{IMG}}", src).replace("{{OVERLAY}}", overlay)
                .replace("{{TIME}}", html.escape(str(st.get("time", "")))))
        cards.append(card)
        toc.append('<li><a href="#s%d">%s</a></li>' % (i, html.escape(st["title"])))
    page = tpl[:s] + "\n".join(cards) + tpl[e + len("<!--CARD_END-->"):]
    start = ""
    if data.get("start_image") and not a.no_start:
        ssrc = img_src(data["start_image"], base, a.embed)
        if not a.embed:
            ssrc = os.path.relpath(ssrc, out_dir)
        start = '<figure class="start"><img src="%s" alt="start" loading="lazy"><figcaption>%s</figcaption></figure>' % (ssrc, L["start"])
    for k, v in {"{{LANG}}": L["lang"], "{{TITLE}}": html.escape(data.get("title", "Tutorial")),
                 "{{SUBTITLE}}": html.escape(data.get("subtitle", "")), "{{TOC}}": "\n".join(toc),
                 "{{TOTAL}}": L["total"] % len(steps), "{{OVERVIEW}}": L["overview"], "{{START}}": start,
                 "{{FOOTER}}": html.escape(data.get("footer", ""))}.items():
        page = page.replace(k, v)
    os.makedirs(out_dir, exist_ok=True)
    open(a.output, "w", encoding="utf-8").write(page)
    print("render: %d cards -> %s (%.0f KB)" % (len(steps), a.output, os.path.getsize(a.output) / 1024.0))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="video / screenshot folder -> key frames")
    e.add_argument("input")
    e.add_argument("-o", "--out", required=True)
    e.add_argument("--fps", type=float, default=5, help="analysis frame rate for videos (default 5)")
    e.add_argument("--width", type=int, default=960, help="saved frame width (default 960)")
    e.add_argument("--min-steps", type=int, default=4)
    e.add_argument("--max-steps", type=int, default=6)
    e.add_argument("--threshold", type=float, default=0.0015,
                   help="share of the screen that must change to count as a step (default 0.0015 = 0.15%%)")
    e.add_argument("--settle", type=int, default=2, help="frames the screen must stay calm (default 2)")
    e.add_argument("--gap", type=int, default=2, help="frame distance used for calm check (default 2)")
    e.add_argument("--pixel-diff", type=int, default=14, help="gray-level difference that counts as changed (lower = sees pale highlights)")
    e.add_argument("--merge-gap", type=float, default=2.0,
                   help="seconds: a weak follow-up change in the same spot (typing) is merged into the previous step; 0 = off")
    e.add_argument("--cursor-size", type=int, default=11, help="blobs <= this many analysis px are treated as cursor")
    e.set_defaults(fn=cmd_extract)
    r = sub.add_parser("render", help="steps.json + template -> HTML")
    r.add_argument("steps")
    r.add_argument("-o", "--output", required=True)
    r.add_argument("--template", default=os.path.join(here, "step_card_template.html"))
    r.add_argument("--embed", action="store_true", help="inline images as base64 (single portable file)")
    r.add_argument("--lang", choices=sorted(LABELS), default="zh")
    r.add_argument("--no-start", action="store_true", help="omit the start-screen picture")
    r.set_defaults(fn=cmd_render)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
