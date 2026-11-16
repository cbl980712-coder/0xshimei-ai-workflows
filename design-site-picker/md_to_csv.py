#!/usr/bin/env python3
"""把 markdown 收藏清单（- [名称](网址) 简介）转成导入用 CSV。纯标准库。
用法: python3 md_to_csv.py 清单.md 输出.csv [--sections "Color,Typography"] [--section-level 2]
"""
import csv, re, sys, argparse

LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')

def clean(t):
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', t)           # 图片徽章
    t = LINK.sub(lambda m: m.group(1), t)                # 其余链接只留文字
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'[\U0001F300-\U0001FAFF☀-➿]', '', t)  # emoji
    t = t.replace('"', '').strip(' -—–:：*')
    return re.sub(r'\s+', ' ', t).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('md'); ap.add_argument('out')
    ap.add_argument('--sections', default='', help='只取这些标题（逗号分隔，不分大小写）；留空取全部')
    a = ap.parse_args()
    want = [s.strip().lower() for s in a.sections.split(',') if s.strip()]
    cat, rows = '', []
    import os
    if not os.path.isfile(a.md): sys.exit('出错了：找不到文件「%s」。请检查路径（带空格的路径要加引号）。' % a.md)
    try: lines = open(a.md, encoding='utf-8-sig').read().splitlines()
    except UnicodeDecodeError: sys.exit('出错了：「%s」不是 UTF-8 文本，请另存为 UTF-8 的 .md/.txt。' % a.md)
    for line in lines:
        h = re.match(r'^#{2,4}\s+(.*)', line)
        if h:
            cat = h.group(1).strip(); continue
        m = re.match(r'^\s*[-*]\s+\[([^\]]+)\]\((https?://[^)\s]+)\)(.*)', line)
        if not m: continue
        if want and cat.lower() not in want: continue
        rows.append([m.group(1).strip(), m.group(2), clean(m.group(3)), cat])
    if not rows:
        sys.exit('出错了：没读到任何链接。这个脚本只认「- [名称](https://网址) 简介」这种写法（行首是 - 或 *）。%s' % ('你用了 --sections，标题名要和 md 里的完全一致。' if want else ''))
    with open(a.out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['名称', '网址', '简介', '分类']); w.writerows(rows)
    print('写出 %d 行 -> %s' % (len(rows), a.out))

if __name__ == '__main__':
    main()
