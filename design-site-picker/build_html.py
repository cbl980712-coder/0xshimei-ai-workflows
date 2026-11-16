#!/usr/bin/env python3
"""把 rules.json + templates/core.js + 示例清单.csv 打成一个单文件 设计站筛选器.html（双击就能用，不联网）。"""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '设计站筛选器.html')
rules = open(os.path.join(H, 'rules.json'), encoding='utf-8').read()
core = open(os.path.join(H, 'templates', 'core.js'), encoding='utf-8').read()
sample = open(os.path.join(H, 'templates', '示例清单.csv'), encoding='utf-8-sig').read()
tpl = open(os.path.join(H, 'templates', 'tool.html'), encoding='utf-8').read()
html = tpl.replace('/*__CORE__*/', core).replace('__RULES__', rules).replace('__SAMPLE__', json.dumps(sample, ensure_ascii=False))
open(out, 'w', encoding='utf-8').write(html); print('写出', out, len(html), '字节')
