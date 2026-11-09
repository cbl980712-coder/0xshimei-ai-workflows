#!/usr/bin/env python3
"""build_xlsx.py - 用标准库生成 shot_cost_calculator.xlsx（不依赖 openpyxl）。
用法：python3 build_xlsx.py 原稿out目录 修订稿out目录 [更多成对目录...] -o shot_cost_calculator.xlsx
每对：原稿检测结果 vs 按建议修改后的检测结果，逐镜头对照。参数页可改单价/失败率模型，公式自动重算。
"""
import argparse, json, os, zipfile
from xml.sax.saxutils import escape

PRICE, BASE, SLOPE, CAP, LOCK = 4.0, 0.10, 0.08, 0.85, 0.6


def col(i):
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i]


def cell(ref, v, f=None, style=0):
    s = ' s="%d"' % style if style else ""
    if f is not None:
        return '<c r="%s"%s><f>%s</f><v>%s</v></c>' % (ref, s, escape(f), v)
    if isinstance(v, str):
        return '<c r="%s"%s t="inlineStr"><is><t>%s</t></is></c>' % (ref, s, escape(v))
    return '<c r="%s"%s><v>%s</v></c>' % (ref, s, v)


def sheet(rows):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols><col min="1" max="12" width="16" customWidth="1"/></cols><sheetData>']
    for r, cells in enumerate(rows, 1):
        out.append('<row r="%d">%s</row>' % (r, "".join(cells)))
    out.append("</sheetData></worksheet>")
    return "".join(out)


def p(score):
    return min(CAP, BASE + SLOPE * score)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("-o", "--out", default="shot_cost_calculator.xlsx")
    ap.add_argument("--price", type=float, default=4.0, help="单次生成价格(元)，默认 4.0，和检查脚本用同一个数")
    a = ap.parse_args()
    global PRICE
    PRICE = a.price
    for dd in a.dirs:
        if not os.path.exists(os.path.join(dd, "result.json")):
            raise SystemExit("%s 里没有 result.json：先用 prompt_guard_checker.py 跑出这个目录" % dd)
    if len(a.dirs) % 2:
        raise SystemExit("目录要成对给：原稿 修订稿")
    params = [
        [cell("A1", "单次生成价(元)", style=1), cell("B1", PRICE)],
        [cell("A2", "基础失败率", style=1), cell("B2", BASE)],
        [cell("A3", "每1风险分增加失败率", style=1), cell("B3", SLOPE)],
        [cell("A4", "失败率上限", style=1), cell("B4", CAP)],
        [cell("A5", "死锁约束后失败率系数(假设)", style=1), cell("B5", LOCK)],
        [],
        [cell("A7", "说明：失败率=MIN(上限, 基础+每分×风险分) 与 系数都是未经实测的假设；改这里的数，对照表自动重算。预期抽卡次数=1/(1-失败率)。单价默认 ¥4 来自第三方对可灵 5 秒 1080p 约 0.56 美元的折算，请换成你自己平台的实价。")],
    ]
    params[-1] = [cell("A7", params[-1][0].split("<t>")[1].split("</t>")[0])]
    head = ["例子", "镜头", "原稿风险分", "原稿失败率", "原稿预期抽卡", "原稿成本(元)", "修订风险分", "修订失败率", "修订预期抽卡", "修订成本(元)", "节省(元)", "节省%"]
    rows = [[cell(col(i) + "1", h, style=1) for i, h in enumerate(head)]]
    r = 2
    tot = {"b": 0, "a": 0}
    for k in range(0, len(a.dirs), 2):
        before = json.load(open(os.path.join(a.dirs[k], "result.json"), encoding="utf-8"))
        after = json.load(open(os.path.join(a.dirs[k + 1], "result.json"), encoding="utf-8"))
        name = os.path.basename(os.path.dirname(os.path.abspath(a.dirs[k]))) or a.dirs[k]
        # 按镜头名对照：拆镜后修订稿会多出镜头（如 镜头1b），原来按顺序一一配对会把多出来的丢掉
        bm = {x["shot"]: x for x in before}
        am = {x["shot"]: x for x in after}
        names = [x["shot"] for x in before] + [x["shot"] for x in after if x["shot"] not in bm]
        for nm in names:
            b, f = bm.get(nm), am.get(nm)
            pb = p(b["score_before"]) if b else 0
            pa = p(f["score_before"]) * LOCK if f else 0
            cb = PRICE / (1 - pb) if b else 0
            ca = PRICE / (1 - pa) if f else 0
            tot["b"] += cb; tot["a"] += ca
            row = [cell("A%d" % r, "例子" + name), cell("B%d" % r, nm)]
            if b:
                row += [cell("C%d" % r, b["score_before"]),
                        cell("D%d" % r, round(pb, 4), "MIN(参数!$B$4,参数!$B$2+参数!$B$3*C%d)" % r),
                        cell("E%d" % r, round(1 / (1 - pb), 4), "1/(1-D%d)" % r),
                        cell("F%d" % r, round(cb, 4), "E%d*参数!$B$1" % r)]
            else:
                row += [cell("C%d" % r, "（拆镜新增）"), cell("F%d" % r, 0)]
            if f:
                row += [cell("G%d" % r, f["score_before"]),
                        cell("H%d" % r, round(pa, 4), "MIN(参数!$B$4,参数!$B$2+参数!$B$3*G%d)*参数!$B$5" % r),
                        cell("I%d" % r, round(1 / (1 - pa), 4), "1/(1-H%d)" % r),
                        cell("J%d" % r, round(ca, 4), "I%d*参数!$B$1" % r)]
            else:
                row += [cell("G%d" % r, "（修订稿删掉）"), cell("J%d" % r, 0)]
            row += [cell("K%d" % r, round(cb - ca, 4), "F%d-J%d" % (r, r))]
            if b:
                row += [cell("L%d" % r, round((cb - ca) / cb, 4), "K%d/F%d" % (r, r))]
            rows.append(row)
            r += 1
    last = r - 1
    rows.append([cell("A%d" % r, "合计", style=1),
                 cell("F%d" % r, round(tot["b"], 4), "SUM(F2:F%d)" % last),
                 cell("J%d" % r, round(tot["a"], 4), "SUM(J2:J%d)" % last),
                 cell("K%d" % r, round(tot["b"] - tot["a"], 4), "SUM(K2:K%d)" % last),
                 cell("L%d" % r, round((tot["b"] - tot["a"]) / tot["b"], 4), "K%d/F%d" % (r, r))])
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="参数" sheetId="1" r:id="rId1"/><sheet name="单镜头对照" sheetId="2" r:id="rId2"/></sheets><calcPr fullCalcOnLoad="1"/></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><sz val="11"/><name val="Arial"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": sheet(params),
        "xl/worksheets/sheet2.xml": sheet(rows),
    }
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in files.items():
            z.writestr(n, c)
    print("已生成 %s：%d 行镜头对照，合计 ¥%.1f → ¥%.1f" % (a.out, last - 1, tot["b"], tot["a"]))


if __name__ == "__main__":
    main()
