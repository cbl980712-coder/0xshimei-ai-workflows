#!/usr/bin/env python3
"""prompt_guard_checker.py - AI 视频抽卡翻车风险检测（纯标准库，Python 3.8+）

输入：分镜文件（txt/md）。每个镜头以「镜头1」「Shot 1」或「## 」开头；
      可选字段 描述： 首帧： 尾帧： 时长： ；没写字段的行都算描述。
输出（写到 -o 目录）：
  report.md         风控自检清单（每镜头命中项 + 勾选框）
  final_prompts.md  标准首尾帧提示词（含死锁约束 + 负向参数）
  result.json       机器可读结果
  cost.csv          每镜头风险分/预估抽卡次数（给 shot_cost_calculator.xlsx 用）
用法：python3 prompt_guard_checker.py shots.md -o out/ [--price 4.0]
"""
import argparse, csv, json, os, re, sys, time

# (类别, 规则id, 正则, 权重, 命中说明, 处理建议)
RULES = [
    ("歧义词", "pronoun", r"它们|他们|她们|它|那个|这个|某个|某种|某人", 1,
     "指代不明，模型可能认错主体", "把代词替换成具体主体（如「穿红衣的女主」）"),
    ("歧义词", "vague", r"一些|许多|各种|类似|大概|随便|差不多|等等|之类|有点|氛围感|高级感|电影感",
     1, "模糊词，模型自行脑补", "换成可画出来的具体名词/数量/颜色"),
    ("歧义词", "multi_subject", r"[三四五六七八九十\d]+\s*个人|[三四五六七八九十]个孩子|众人|三个\S{1,3}", 2,
     "多主体，面部/身份易漂移", "单镜头主体 ≤2；其余放虚化背景"),
    ("人群", "crowd", r"人群|一群|很多人|许多人|观众|路人们", 2,
     "人群=大量脸，脸部易糊/融合", "改为背景虚化的 ≤3 个路人，或用远景剪影"),
    ("肢体冲突", "fight", r"打斗|打架|格斗|扭打|搏斗|厮杀|拳|踢|摔倒|推搡|砍|fight|punch|kick", 3,
     "复杂肢体对抗，肢体穿模/多手多脚高发", "拆成 2~3 个单动作镜头，用特写+遮挡避开接触瞬间"),
    ("肢体冲突", "contact", r"拥抱|抱起|抱住|接吻|亲吻|握手|牵手|十指|背起|扶住|搀扶|hug|kiss|handshake", 3,
     "两人身体接触，肢体融合风险", "只拍接触前/后画面（首帧分开→尾帧已抱住），或用侧面遮挡"),
    ("肢体冲突", "hand_detail", r"打字|弹琴|弹钢琴|吉他|写字|系鞋带|拿着|握着|递给|递出|吃饭|喝了|倒水|切菜|鼓掌|比心|手指|点击", 2,
     "手部精细操作，手指数量/形态易崩", "手放在画面外或半身构图；手持物改为静置于桌面"),
    ("肢体冲突", "run_dance", r"奔跑|狂奔|跑步|追逐|跳舞|舞蹈|翻滚|跳跃|飞奔|跑向|跑来|跑去|跳下|run|dance", 2,
     "大幅度全身运动，腿脚错乱", "改为侧面中景、单一方向行进，时长 ≤5 秒"),
    ("镜头剧烈", "orbit", r"360|环绕|旋转一周|绕着|orbit", 2,
     "大角度环绕，背景与主体易不一致", "限制为 ≤30° 小幅环绕"),
    ("镜头剧烈", "fast_move", r"快速|急速|迅速|飞速|猛地|瞬间|急推|急拉|甩镜|whip|fpv|穿越|穿过|俯冲", 2,
     "高速运镜/瞬变，运动模糊+几何崩坏", "改为缓慢/平稳；一镜只允许一种运镜"),
    ("镜头剧烈", "shake", r"手持|晃动|抖动|晃镜|震动|一镜到底", 2,
     "晃动或超长连续运动", "改稳定器视角；一镜到底拆成多个 ≤5 秒镜头"),
    ("文字/Logo", "text", r"文字|字幕|招牌|写着|标语|logo|Logo|LOGO|品牌名|字样|显示|海报上|横幅|车牌", 2,
     "画面内文字几乎必乱码", "画面不出文字，后期用剪辑软件叠加"),
    ("状态突变", "morph", r"变成|变为|变身|化作|蜕变|渐变为|融化|爆炸|火海|消失|瞬间出现|morph|transform", 3,
     "同一镜头内物体/人物形态大变，易闪烁/断裂", "拆两镜：首帧=变化前，尾帧=变化后，让模型只做过渡"),
    ("镜头剧烈", "mirror", r"镜子|倒影|水中倒影|玻璃反射|反光", 2,
     "反射需要一致的镜像，极易穿帮", "避开反射面或用模糊遮挡"),
]
CAMERA_TERMS = r"推镜|拉镜|推近|拉远|推进|拉出|摇镜|横摇|平移|横移|跟拍|跟随|升降|升起|下降|变焦|航拍|环绕|穿越|甩镜|俯冲|dolly|pan|tilt|zoom|orbit"

# 自动软化：(正则, 替换)。只改「镜头剧烈」类措辞，不动剧情。
SOFTEN = [
    (r"360\s*度?环绕|环绕\s*360\s*度?|旋转一周|绕.{0,6}一圈", "小幅环绕(不超过30度)"),
    (r"一镜到底", "单一平稳运镜"),
    (r"甩镜|whip pan", "平稳摇镜"),
    (r"手持晃动镜头|手持晃动|手持跟拍|手持", "稳定器稳定"),
    (r"急推|急拉", "缓慢推进"),
    (r"快速|急速|迅速|飞速|猛地", "缓慢"),
    (r"穿越|俯冲", "平稳前移"),
    (r"很多人|一群人|人群|许多人", "背景虚化的少量路人(不超过3人,无清晰面孔)"),
]

NEG_BASE = "画面抖动, 闪烁, 面部变形, 五官漂移, 多余肢体, 画质模糊, 水印, 乱码文字"
NEG_BY_CAT = {
    "肢体冲突": "多余手指, 手指融合, 肢体穿模, 多手多脚, 关节反向弯曲",
    "镜头剧烈": "镜头突变, 画面撕裂, 运动拖影, 背景扭曲, 景别跳变",
    "歧义词": "额外人物, 主体替换, 人物数量变化",
    "人群": "人脸融合, 糊脸, 人群克隆",
    "文字/Logo": "文字变形, 错别字, 招牌乱码, 品牌标识变形",
    "状态突变": "物体凭空出现/消失, 形态突变, 中途切换",
}
WEIGHT_CAP = {"歧义词": 3, "肢体冲突": 6, "镜头剧烈": 6, "文字/Logo": 2, "状态突变": 3, "人群": 2, "时长": 3}
LOCK_FACTOR = 0.6  # 假设：加死锁约束+首尾帧对齐后，失败概率乘以该系数（未实测，可在 xlsx 里改）


def split_shots(text):
    pat = r"(?m)^\s*(?=(?:#+\s*)?(?:镜头|Shot|shot|SHOT)\s*[\d一二三四五六七八九十]+)"
    parts = [p.strip() for p in re.split(pat, text) if p.strip()]
    if len(parts) <= 1 and not re.match(r"\s*(?:#+\s*)?(?:镜头|Shot)", text):
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    shots = []
    for i, p in enumerate(parts, 1):
        lines = p.splitlines()
        head = re.sub(r"^#+\s*", "", lines[0]).strip()
        m = re.match(r"((?:镜头|Shot|shot)\s*[\d一二三四五六七八九十]+(?:[a-zA-Z]|[\-_.]\d+)?)\s*[:：\-—]?\s*(.*)", head)   # 拆镜后常写 镜头1b / 镜头1-2
        name, rest = (m.group(1), m.group(2)) if m else ("镜头%d" % i, head)
        body = ([rest] if rest else []) + lines[1:]
        f = {"首帧": "", "尾帧": "", "时长": "", "描述": []}
        for ln in body:
            ln = ln.strip()
            if not ln:
                continue
            mm = re.match(r"(首帧|尾帧|时长|描述|提示词)\s*[:：]\s*(.*)", ln)
            if mm:
                k = "描述" if mm.group(1) == "提示词" else mm.group(1)
                if k == "描述":
                    f["描述"].append(mm.group(2))
                else:
                    f[k] = mm.group(2)
            else:
                f["描述"].append(ln)
        desc = " ".join(f["描述"])
        # 行内「时长：N秒」写在描述末尾的情况
        dm = re.search(r"时长\s*[:：]\s*([\d.]+\s*秒)", desc)
        if dm and not f["时长"]:
            f["时长"] = dm.group(1)
            desc = re.sub(r"\s*时长\s*[:：]\s*[\d.]+\s*秒", "", desc).strip()
        seen = [x["name"] for x in shots]
        if name in seen:   # 同名镜头（比如拆镜后两个都叫 镜头1）加序号区分，成本表才对得上
            name = "%s#%d" % (name, seen.count(name) + 1 + sum(1 for x in seen if x.startswith(name + "#")))
        shots.append({"name": name, "desc": desc, "first": f["首帧"],
                      "last": f["尾帧"], "duration": f["时长"]})
    return shots


def scan(shot, need_frames=True):
    """返回命中列表、总分、时长。"""
    text = " ".join([shot["desc"], shot["first"], shot["last"]])
    hits, by_cat = [], {}
    for cat, rid, pat, w, msg, fix in RULES:
        ms = sorted(set(m.group(0) for m in re.finditer(pat, text)))
        if ms and rid == "contact" and not re.search(pat, shot["desc"]):
            # 接触只出现在首帧/尾帧（静态姿态），正是「只拍接触前后」的改法，不再按高风险算
            w, msg, fix = 1, "首帧或尾帧是接触后的静态姿态", "问题不大：两张图用同一参考生成，注意手臂位置前后连贯"
        if ms:
            hits.append({"category": cat, "rule": rid, "matches": ms, "weight": w, "msg": msg, "fix": fix})
            by_cat[cat] = by_cat.get(cat, 0) + w * min(len(ms), 2)
    cams = set(re.findall(CAMERA_TERMS, text))
    if len(cams) >= 2:
        hits.append({"category": "镜头剧烈", "rule": "multi_camera", "matches": sorted(cams), "weight": 2,
                     "msg": "同一镜头叠加 %d 种运镜" % len(cams), "fix": "一镜只留一种运镜"})
        by_cat["镜头剧烈"] = by_cat.get("镜头剧烈", 0) + 2
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s)", shot["duration"])
    dur = float(dm.group(1)) if dm else None
    if dur and dur > 5:
        w = 3 if dur > 8 else 1
        hits.append({"category": "时长", "rule": "duration", "matches": ["%g秒" % dur], "weight": w,
                     "msg": "单镜头 %g 秒，越长越容易后半段崩" % dur, "fix": "拆成 ≤5 秒的多个镜头"})
        by_cat["时长"] = w
    score = sum(min(v, WEIGHT_CAP.get(k, 3)) for k, v in by_cat.items())
    if need_frames and (not shot["first"] or not shot["last"]):
        hits.append({"category": "首尾帧", "rule": "no_frames", "matches": [], "weight": 2,
                     "msg": "缺少显式首帧/尾帧描述（模型会自己决定结尾）", "fix": "已按描述起止自动起草，需你确认"})
        score += 2
    return hits, score, dur


def level(score):
    return "低" if score <= 1 else "中" if score <= 4 else "高" if score <= 8 else "极高"


def p_fail(score):
    return min(0.85, 0.10 + 0.08 * score)  # 假设模型，非实测


def soften(text):
    changes = []
    for pat, rep in SOFTEN:
        m = re.search(pat, text)
        if m:
            changes.append("「%s」→「%s」" % (m.group(0), rep))
            text = re.sub(pat, rep, text)
    return text, changes


def clauses(desc):
    cs = [c.strip() for c in re.split(r"[，。；,;！!]", desc) if c.strip()]
    return cs or [desc]


def build_prompt(shot, hits, soft_desc):
    cs = clauses(soft_desc)
    first = shot["first"] or (cs[0] + "（起始静态姿态，自动起草，请核对）")
    last = shot["last"] or (cs[-1] + "（结束稳定姿态，自动起草，请核对）")
    cats = []
    for h in hits:
        if h["category"] in NEG_BY_CAT and h["category"] not in cats:
            cats.append(h["category"])
    neg = NEG_BASE + "".join(", " + NEG_BY_CAT[c] for c in cats)
    text = (
        "【主体与场景】%s\n"
        "【首帧】%s\n"
        "【尾帧】%s\n"
        "【运动】只描述首帧到尾帧之间的一个连续动作；运镜：单一、缓慢、平稳。\n"
        "【死锁约束】人物外貌/服装/发型/光线/场景在首尾帧保持一致；主体数量不变；"
        "不新增画面外元素；画面内不出现文字；时长 ≤5 秒。\n"
        "【负向】%s" % (soft_desc, first, last, neg))
    return {"first": first, "last": last, "neg": neg, "text": text}


def main():
    ap = argparse.ArgumentParser(description="AI 视频抽卡翻车风险检测")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("--price", type=float, default=4.0, help="单次生成价格(元)，默认 4.0")
    a = ap.parse_args()
    t0 = time.time()
    if not os.path.exists(a.input):
        sys.exit("找不到分镜文件：%s（先新建这个文件，写法见 README）" % a.input)
    text = open(a.input, encoding="utf-8").read()
    shots = split_shots(text)
    if not shots:
        sys.exit("没读到任何镜头：请检查输入格式（见 README）")
    os.makedirs(a.out, exist_ok=True)
    results = []
    for s in shots:
        hits, score, dur = scan(s)
        soft, changes = soften(s["desc"])
        _, score2, _ = scan(dict(s, desc=soft), need_frames=False)  # 重扫软化后文本，补帧后不再扣缺帧分
        pr = build_prompt(s, hits, soft)
        if score2 >= 5:
            pr['text'] = '【⚠ 仍高风险：先按自检清单拆镜，下面的首尾帧只是自动草稿，不要直接去抽卡】\n' + pr['text']
        before = p_fail(score)
        after = p_fail(score2) * (1 if score2 >= 5 else LOCK_FACTOR)  # 软化后仍>=5分的镜头不计节省
        results.append({"shot": s["name"], "desc": s["desc"], "score_before": score, "level": level(score),
                        "score_after_rescan": score2, "hits": hits, "soften": changes, "prompt": pr,
                        "unresolved": score2 >= 5,
                        "p_fail_before": round(p_fail(score), 3),
                        "p_fail_after": round(after, 3),
                        "draws_before": round(1 / (1 - p_fail(score)), 2), "draws_after": round(1 / (1 - after), 2)})
    L = ["# 风控自检清单", "", "输入：`%s`，镜头数：%d，单次生成价：¥%g" % (os.path.basename(a.input), len(results), a.price), ""]
    L.append("| 镜头 | 风险分(前→后重扫) | 等级 | 预估抽卡(前→后) |")
    L.append("|---|---|---|---|")
    for r in results:
        L.append("| %s | %d → %d | %s | %.2f → %.2f |" % (r["shot"], r["score_before"], r["score_after_rescan"], r["level"], r["draws_before"], r["draws_after"]))
    L.append("")
    for r in results:
        L += ["## %s（%s风险，%d 分）" % (r["shot"], r["level"], r["score_before"]), "> " + r["desc"], ""]
        if not r["hits"]:
            L.append("- [x] 未命中高风险项，可直接出片")
        for h in r["hits"]:
            m = "、".join(h["matches"])
            L.append("- [ ] **%s**%s：%s → %s" % (h["category"], ("（" + m + "）") if m else "", h["msg"], h["fix"]))
        for c in r["soften"]:
            L.append("- [x] 已自动软化 %s" % c)
        if r["unresolved"]:
            L.append("- [ ] **仍高风险(%d分)**：自动软化解决不了，必须按上面的建议手动拆镜后再跑一遍本脚本；预估节省不含此镜头" % r["score_after_rescan"])
        L += ["- [ ] 首帧图与尾帧图已用同一人物/场景参考生成（风格、光线一致）",
              "- [ ] 提示词只描述首帧→尾帧之间的一个动作", ""]
    L += ["## 出片前通用检查", "- [ ] 先用最低档/最短时长抽 1 张试片，通过再出高清",
          "- [ ] 单镜头 ≤5 秒", "- [ ] 画面内无文字，字幕后期叠", "- [ ] 同镜头最多 2 个主体、1 种运镜"]
    open(os.path.join(a.out, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    P = ["# 标准首尾帧提示词", ""]
    for r in results:
        P += ["## " + r["shot"], "```", r["prompt"]["text"], "```", ""]
    open(os.path.join(a.out, "final_prompts.md"), "w", encoding="utf-8").write("\n".join(P))
    json.dump(results, open(os.path.join(a.out, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "cost.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shot", "score_before", "score_after", "p_fail_before", "p_fail_after", "draws_before", "draws_after", "cost_before", "cost_after"])
        for r in results:
            w.writerow([r["shot"], r["score_before"], r["score_after_rescan"], r["p_fail_before"], r["p_fail_after"],
                        r["draws_before"], r["draws_after"], round(r["draws_before"] * a.price, 2), round(r["draws_after"] * a.price, 2)])
    tb = sum(r["draws_before"] for r in results) * a.price
    ta = sum(r["draws_after"] for r in results) * a.price
    print("镜头 %d 个 | 高风险(>=5分) %d 个 | 软化后仍需手动拆镜 %d 个 | 预估成本 ¥%.1f → ¥%.1f（模型估算，非实测）| 用时 %.3fs → %s" % (
        len(results), sum(1 for r in results if r["score_before"] >= 5), sum(1 for r in results if r["unresolved"]), tb, ta, time.time() - t0, a.out))


if __name__ == "__main__":
    main()
