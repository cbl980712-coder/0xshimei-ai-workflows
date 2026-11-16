#!/usr/bin/env python3
"""用 清单整理.csv 生成按用途分组的静态索引页（带搜索框）。用法: python3 build_index.py 清单整理.csv 输出.html"""
import csv, html, sys, collections
import os
if len(sys.argv) != 3: sys.exit('用法：python3 build_index.py 清单整理.csv 输出.html（清单整理.csv 是 pick_sites.py 的输出）')
src, out = sys.argv[1], sys.argv[2]
if not os.path.isfile(src): sys.exit('出错了：找不到「%s」。先跑 pick_sites.py，再用它输出目录里的 清单整理.csv。' % src)
csv.field_size_limit(2**31 - 1)
rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
if not rows or '状态' not in rows[0]: sys.exit('出错了：「%s」不是 pick_sites.py 生成的 清单整理.csv（缺少「状态」列）。' % src)
ok = [r for r in rows if r['状态'] == '可用']
groups = collections.OrderedDict()
for r in ok:
    for t in (r['用途标签'] or '其他').split('/'):
        groups.setdefault(t, []).append(r)
parts = []
for t, rs in sorted(groups.items(), key=lambda x: -len(x[1])):
    li = ''.join('<li data-k="%s"><a href="%s" target="_blank" rel="noopener">%s</a> <span>%s</span></li>' % (
        html.escape((r['名称'] + ' ' + r['简介']).lower()), html.escape(r['网址']), html.escape(r['名称'] or r['网址']), html.escape(r['简介'][:90])) for r in rs)
    parts.append('<section><h2>%s <small>%d</small></h2><ul>%s</ul></section>' % (html.escape(t), len(rs), li))
doc = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>设计参考索引</title>
<style>:root{--bg:#faf8f4;--fg:#1d1b17;--mu:#6b665c;--ln:#e4dfd3;--ac:#c2410c}@media(prefers-color-scheme:dark){:root{--bg:#161512;--fg:#f1ede4;--mu:#a39d8e;--ln:#38352e;--ac:#fb923c}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}main{max-width:900px;margin:0 auto;padding:24px 16px 60px}
h1{margin:0}p{color:var(--mu)}input{width:100%%;font:inherit;padding:8px 10px;border:1px solid var(--ln);border-radius:8px;background:var(--bg);color:var(--fg)}
h2{border-bottom:1px solid var(--ln);padding-bottom:4px;margin-top:28px}small{color:var(--mu);font-weight:400}ul{list-style:none;padding:0}li{padding:3px 0}a{color:var(--ac)}li span{color:var(--mu);font-size:13px}</style></head>
<body><main><h1>设计参考索引</h1><p>由「设计网站筛选器」从 %d 个可用站整理而成（简介不足的已排除，在待补清单里）。「可用」指简介达到筛选门槛，不表示网址已逐一核对，打开前请自己确认链接还在。按用途分组，一个站可出现在多组。</p>
<input id="q" placeholder="搜索名称或简介，如 font / icon / 配色"><div id="g">%s</div>
<script>document.getElementById('q').oninput=function(){var q=this.value.toLowerCase();document.querySelectorAll('li').forEach(function(l){l.style.display=l.dataset.k.indexOf(q)>=0?'':'none'})}</script></main></body></html>''' % (len(ok), ''.join(parts))
open(out, 'w', encoding='utf-8').write(doc); print('写出', out, len(ok), '站,', len(groups), '组')
