#!/usr/bin/env python3
"""把 .pptx 直接读出来，按真实坐标/字号/颜色画成 HTML（没装 PowerPoint 也能看版式）。
用法：python preview_pptx.py deck.pptx [out.html]
注意：浏览器的换行与 PowerPoint 略有出入，以 PowerPoint/Keynote 打开为准。"""
import sys, html, os
try: from pptx import Presentation
except ImportError: sys.exit("出错了：没有安装 python-pptx。请先运行：pip install python-pptx")
from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

PX = 100 / 914400.0            # 1 英寸 = 100 px
def px(v): return round(Emu(v or 0) * PX, 1)

def fill_css(shape):
    try:
        if shape.fill.type == 1: return f"background:#{shape.fill.fore_color.rgb};"
    except Exception: pass
    return ""

def render_shape(sh):
    css = f"left:{px(sh.left)}px;top:{px(sh.top)}px;width:{px(sh.width)}px;height:{px(sh.height)}px;"
    if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
        css += fill_css(sh)
        if "ROUNDED" in str(sh.auto_shape_type): css += "border-radius:14px;"
    inner = ""
    if sh.has_text_frame and sh.text_frame.text.strip():
        is_body = sh.is_placeholder and sh.placeholder_format.type in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT)
        va = {1: "flex-start", 3: "center", 4: "flex-end"}.get(sh.text_frame.vertical_anchor, "flex-start")
        paras = []
        for p in sh.text_frame.paragraphs:
            runs = ""
            for r in p.runs:
                f = r.font; col = f"#{f.color.rgb}" if f.color and f.color.type else "inherit"
                runs += (f"<span style='font-size:{(f.size.pt if f.size else 18)*100/72:.1f}px;"
                         f"font-weight:{700 if f.bold else 400};color:{col}'>{html.escape(r.text)}</span>")
            sa = f"margin-bottom:{p.space_after.pt*100/72:.1f}px;" if p.space_after else ""
            al = "text-align:left;"
            bullet = "<b class=bl>•</b>" if is_body else ""
            paras.append(f"<p style='{sa}{al}'>{bullet}{runs}</p>")
        inner = f"<div class=tf style='justify-content:{va}'>{''.join(paras)}</div>"
    return f"<div class=sh style='{css}'>{inner}</div>"

def main():
    if len(sys.argv) < 2: sys.exit("用法：python3 scripts/preview_pptx.py out/deck.pptx")
    src = sys.argv[1]
    if not os.path.isfile(src): sys.exit(f"出错了：找不到 {src}。请先用 make_presentation.py 生成 .pptx。")
    out = sys.argv[2] if len(sys.argv) > 2 else src.rsplit(".", 1)[0] + ".preview.html"
    try: prs = Presentation(src)
    except Exception: sys.exit(f"出错了：{src} 不是有效的 .pptx 文件。")
    W, H = px(prs.slide_width), px(prs.slide_height)
    slides = []
    for i, s in enumerate(prs.slides, 1):
        bg = "#ffffff"
        try:
            if s.background.fill.type == 1: bg = f"#{s.background.fill.fore_color.rgb}"
        except Exception: pass
        body = "".join(render_shape(sh) for sh in s.shapes)
        slides.append(f"<div class=slide id=s{i} style='width:{W}px;height:{H}px;background:{bg}'>{body}</div>")
    page = f"""<!doctype html><html><meta charset=utf-8><title>{html.escape(src)} 预览</title><style>
body{{margin:0;background:#d8dde4;font-family:Calibri,'Microsoft YaHei','PingFang SC',sans-serif}}
.slide{{position:relative;margin:24px auto;overflow:hidden;box-shadow:0 2px 12px #0003}}
.sh{{position:absolute;box-sizing:border-box}} .tf{{display:flex;flex-direction:column;height:100%;padding:5px 10px;box-sizing:border-box}}
.tf p{{margin:0;line-height:1.2}} .bl{{display:inline-block;width:.9em;color:#d9480f}}</style><body>{''.join(slides)}</body></html>"""
    open(out, "w", encoding="utf-8").write(page); print("预览已写入", out)
if __name__ == "__main__": main()
