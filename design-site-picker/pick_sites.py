#!/usr/bin/env python3
"""设计网站筛选器：合并重复链接 → 按用途打标签 → 信息不足标待补 → 推荐最多 3 个。
纯 Python 3.8+ 标准库，不联网（除非加 --check）。
用法:
  python3 pick_sites.py 清单.csv --type 落地页 --stuck "配色老是不协调" --out 结果目录 [--top 3] [--check]
"""
import argparse, csv, io, json, os, re, sys, time, urllib.error, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = {
    'name': ['名称', '网站', 'name', 'title', '标题'],
    'url': ['网址', '链接', 'url', 'link', 'href'],
    'desc': ['简介', '描述', '备注', 'description', 'desc', 'note', 'notes'],
    'cat': ['分类', '标签', '类别', 'category', 'tags', 'tag'],
}

def norm_url(u):
    u = u.strip()
    p = urllib.parse.urlsplit(u if '://' in u else 'http://' + u)
    host = p.netloc.lower()
    if host.startswith('www.'): host = host[4:]
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(('utm_', 'ref', 'fbclid'))]
    path = p.path.rstrip('/')
    return host + path + ('?' + urllib.parse.urlencode(q) if q else '')

def die(msg):
    sys.exit('出错了：' + msg)

def read_text(path):
    """读文件。先按 UTF-8，不行再按 GB18030（国内 Excel 另存的 CSV 常见），都不行给人话提示。"""
    if not os.path.exists(path): die('找不到文件「%s」。请检查路径和文件名（带空格的路径要用引号括起来）。' % path)
    if os.path.isdir(path): die('「%s」是个文件夹，需要的是 .csv 文件。' % path)
    try: raw = open(path, 'rb').read()
    except OSError as e: die('读不了「%s」：%s' % (path, e.strerror or e))
    if b'\x00' in raw[:4000]: die('「%s」不是文本文件（可能是 xlsx / 图片 / 压缩包）。请在 Excel 或 Numbers 里「另存为 CSV（UTF-8）」再试。' % path)
    for enc in ('utf-8-sig', 'gb18030'):
        try:
            txt = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc != 'utf-8-sig': print('提示：这个文件不是 UTF-8，已按 GBK/GB18030 读取。建议另存为 UTF-8 的 CSV。', file=sys.stderr)
        return txt
    die('「%s」读不出文字（不是 UTF-8 也不是 GBK）。请在 Excel 或 Numbers 里「另存为 CSV（UTF-8）」再试。' % path)

def read_rows(path):
    txt = read_text(path)
    if not txt.strip(): die('「%s」是空文件。表头至少要有「网址」一列，例子见 templates/设计网站导入模板.csv。' % path)
    csv.field_size_limit(2**31 - 1)
    first = txt.lstrip().split('\n', 1)[0]
    delim = max([',', ';', '\t'], key=first.count)
    try:
        rd = csv.DictReader(io.StringIO(txt, newline=''), delimiter=delim)
        head = {h.strip().lower(): h for h in (rd.fieldnames or []) if h}
        pick = {}
        for k, names in COLS.items():
            for n in names:
                if n.lower() in head: pick[k] = head[n.lower()]; break
        if 'url' not in pick:
            die('找不到网址列。第一行必须是表头，且包含「网址」/ url / link 之一。当前读到的表头：%s。例子见 templates/设计网站导入模板.csv。' % (list(head)[:6] or '（空）'))
        out = []
        for r in rd:
            u = (r.get(pick['url']) or '').strip()
            if not u: continue
            g = lambda k: ((r.get(pick[k]) or '') if k in pick else '').strip()
            out.append({'name': g('name')[:200], 'url': u[:500], 'desc': g('desc')[:2000], 'cat': g('cat')[:200]})
    except csv.Error as e:
        die('CSV 格式读不下去（%s）。常见原因：引号没成对、文件其实不是 CSV。请用 Excel/Numbers 重新另存为 CSV（UTF-8）。' % e)
    if not out: die('表头没问题，但没有任何一行填了网址。请在「网址」列里填内容后再跑。')
    return out

def merge(rows):
    seen, order = {}, []
    for r in rows:
        k = norm_url(r['url'])
        if k not in seen:
            seen[k] = dict(r, key=k, dup=0, cats=[r['cat']] if r['cat'] else []); order.append(k)
        else:
            s = seen[k]; s['dup'] += 1
            if len(r['desc']) > len(s['desc']): s['desc'] = r['desc']
            if len(r['name']) > len(s['name']) and not s['name']: s['name'] = r['name']
            if r['cat'] and r['cat'] not in s['cats']: s['cats'].append(r['cat'])
    return [seen[k] for k in order]

def has(text, w):
    w = w.lower()
    if re.match(r'^[a-z0-9 .\-]+$', w):
        return re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?:s|es)?(?![a-z0-9])', text) is not None
    return w in text

def tag(sites, rules):
    minc = rules.get('min_desc_chars', 12)
    for s in sites:
        text = (s['name'] + ' ' + s['desc'] + ' ' + ' '.join(s['cats'])).lower()
        s['tags'] = [p for p, ws in rules['purposes'].items() if any(has(text, w) for w in ws)]
        why = []
        if len(s['desc']) < minc: why.append('简介少于%d字' % minc)
        if not s['tags']: why.append('名称/简介/分类里没出现任何用途关键词')
        bad = [x for x in rules.get('exclude_phrases', []) if x in text]
        if bad: why.append('简介提示已不可用：' + bad[0])
        s['pending'] = '；'.join(why)
    return sites

def want_purposes(rules, ptype, stuck):
    w = {}
    low = stuck.lower()
    hit = [p for p, ws in rules['stuck_words'].items() if any(x.lower() in low for x in ws)]
    for p in hit: w[p] = w.get(p, 0) + 5
    for p, v in rules['project_types'].get(ptype, {}).items(): w[p] = w.get(p, 0) + v
    return w, hit

def score(s, w, rules=None):
    sc = sum(w.get(t, 0) for t in s['tags'])
    catlow = ' '.join(s['cats']).lower()
    for p, ws in (rules or {}).get('purposes', {}).items():          # 站所在分类命中的用途，加倍
        if p in w and any(has(catlow, x) for x in ws): sc += 2 * w[p]
    if '学习教程' not in w and any(d in catlow for d in (rules or {}).get('demote_categories', [])): sc -= 6
    sc += min(len(s['desc']), 160) / 160.0           # 简介越详细越可信
    sc -= 0.3 * max(0, len(s['tags']) - 4)           # 什么都沾的泛站略降权
    return sc

def recommend(sites, w, hit, top, skip=(), rules=None):
    ok = [s for s in sites if not s['pending'] and s['key'] not in skip and any(t in w for t in s['tags'])]
    ranked = sorted(ok, key=lambda s: -score(s, w, rules))
    chosen, covered = [], set()
    focus = hit or [p for p, _ in sorted(w.items(), key=lambda x: -x[1])[:2]]
    # 先保证每个卡点用途至少有一个站，再补高分站
    for p in focus:
        pool = [s for s in ranked if p in s['tags'] and s not in chosen]
        # 该用途下：站点所在分类就是这个用途的优先，其次看总分；已经覆盖多个卡点的站放后面，给别的用途留位置
        pool.sort(key=lambda s: (-(any(has(' '.join(s['cats']).lower(), x) for x in (rules or {}).get('purposes', {}).get(p, []))),
                                 len([t for t in s['tags'] if t in covered]) > 0, -score(s, w, rules)))
        if pool and len(chosen) < top:
            chosen.append(pool[0]); covered.update(t for t in pool[0]['tags'] if t in focus)
    for s in ranked:
        if len(chosen) >= top: break
        if s not in chosen: chosen.append(s)
    return chosen

def fetch_check(url, kws, timeout=12):
    t0 = time.time()
    try:
        req = urllib.request.Request(url if '://' in url else 'http://' + url,
                                     headers={'User-Agent': 'Mozilla/5.0 design-site-picker'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(400000).decode('utf-8', 'ignore').lower()
            code = r.status; final = r.geturl()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 503):
            return {'ok': True, 'unverified': True, 'detail': 'HTTP %s：对方拒绝脚本访问（常见于反爬），没法自动核对，请你在浏览器里点开确认' % e.code, 'secs': round(time.time() - t0, 1)}
        return {'ok': False, 'detail': '打不开：HTTP %s' % e.code, 'secs': round(time.time() - t0, 1)}
    except Exception as e:
        return {'ok': False, 'detail': '打不开：%s' % str(e)[:60], 'secs': round(time.time() - t0, 1)}
    text = re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', body, flags=re.S)
    n = len(re.sub(r'\s+', '', text))
    found = [k for k in kws if k.lower() in body]
    if 'cloudflare' in body and any(x in body for x in ('just a moment', 'security verification', 'challenge-platform', 'cf-chl')) and n < 1500:
        return {'ok': True, 'unverified': True, 'detail': 'HTTP %s：返回的是 Cloudflare 人机验证页，没法自动核对，请你在浏览器里点开确认' % code, 'secs': round(time.time() - t0, 1)}
    moved = ''
    if norm_url(final).split('/')[0] != norm_url(url).split('/')[0]: moved = '；注意：已跳转到 ' + final
    ok = code < 400 and n >= 300
    return {'ok': ok, 'detail': 'HTTP %s，正文约 %d 字，命中词：%s%s' % (code, n, '、'.join(found) or '无', moved), 'secs': round(time.time() - t0, 1)}

def reason(s, w, hit):
    fits = [t for t in s['tags'] if t in (hit or w)]
    fits = fits or s['tags'][:2]
    d = s['desc'][:110] + ('…' if len(s['desc']) > 110 else '')
    return '适合解决：' + '、'.join(fits) + '。依据（来自你清单里的简介）：' + d

def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def main():
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')   # Windows 控制台中文
    ap = argparse.ArgumentParser()
    ap.add_argument('csv'); ap.add_argument('--type', default='落地页', help='项目类型：落地页 / 产品界面 / 运营图（可在 rules.json 增加）')
    ap.add_argument('--stuck', default='', help='眼下卡点，一句话')
    ap.add_argument('--top', type=int, default=3); ap.add_argument('--out', default='out')
    ap.add_argument('--rules', default=os.path.join(HERE, 'rules.json'))
    ap.add_argument('--check', action='store_true', help='联网核对推荐站能不能打开，打不开的换下一个')
    a = ap.parse_args(); a.top = min(a.top, 3)
    t0 = time.time()
    try: rules = json.load(open(a.rules, encoding='utf-8'))
    except FileNotFoundError: die('找不到规则文件「%s」。不加 --rules 就用 kit 里自带的 rules.json。' % a.rules)
    except ValueError as e: die('规则文件「%s」不是合法 JSON（%s）。多半是改 rules.json 时漏了逗号或引号。' % (a.rules, e))
    if a.type not in rules['project_types']:
        print('提示：项目类型「%s」不在 rules.json 里，只按卡点推荐。可选：%s' % (a.type, ' / '.join(rules['project_types'])), file=sys.stderr)
    if not a.stuck.strip():
        print('提示：没填 --stuck（眼下卡点），只按项目类型的默认用途推荐，会比较泛。', file=sys.stderr)
    rows = read_rows(a.csv)
    sites = tag(merge(rows), rules)
    w, hit = want_purposes(rules, a.type, a.stuck)
    try: os.makedirs(a.out, exist_ok=True)
    except OSError as e: die('建不了输出目录「%s」：%s' % (a.out, e.strerror or e))
    skip, checks = set(), {}
    chosen = recommend(sites, w, hit, a.top, rules=rules)
    if a.check:
        kws = [x for p in (hit or list(w)) for x in rules['purposes'].get(p, [])[:6]]
        for _ in range(12):
            bad = False
            for s in list(chosen):
                if s['key'] not in checks: checks[s['key']] = fetch_check(s['url'], kws)
                if not checks[s['key']]['ok']:
                    skip.add(s['key']); bad = True
            if not bad: break
            chosen = recommend(sites, w, hit, a.top, skip, rules)
    pend = [s for s in sites if s['pending']]
    write_csv(os.path.join(a.out, '清单整理.csv'), ['名称', '网址', '简介', '用途标签', '状态', '合并重复次数', '待补原因'],
              [[s['name'], s['url'], s['desc'], '/'.join(s['tags']), '待补' if s['pending'] else '可用', s['dup'], s['pending']] for s in sites])
    write_csv(os.path.join(a.out, '待补清单.csv'), ['名称', '网址', '待补原因', '你来补：这个站解决什么问题'],
              [[s['name'], s['url'], s['pending'], ''] for s in pend])
    skipped = [s for s in sites if s['key'] in skip]
    L = ['# 推荐结果', '', '- 项目类型：%s' % a.type, '- 眼下卡点：%s' % (a.stuck or '（未填）'),
         '- 识别到的卡点用途：%s' % ('、'.join(hit) or '（没识别到，按项目类型默认用途推荐）'),
         '- 输入 %d 行 → 合并重复后 %d 个站（合并掉 %d 行）→ 待补 %d 个' % (len(rows), len(sites), len(rows) - len(sites), len(pend)), '']
    if not chosen: L.append('没有找到符合的站：多半是清单里相关简介太少，先看「待补清单.csv」。')
    for i, s in enumerate(chosen, 1):
        L += ['## %d. %s' % (i, s['name'] or s['url']), '- 网址：%s' % s['url'], '- 用途标签：%s' % '、'.join(s['tags']),
              '- %s' % reason(s, w, hit)]
        if s['key'] in checks: L.append('- 联网核对：%s' % checks[s['key']]['detail'])
        L.append('')
    if skipped:
        L += ['## 被换掉的站（联网核对没通过）'] + ['- %s %s — %s' % (s['name'], s['url'], checks[s['key']]['detail']) for s in skipped] + ['']
    open(os.path.join(a.out, '推荐.md'), 'w', encoding='utf-8').write('\n'.join(L))
    write_csv(os.path.join(a.out, '素材清单.csv'), ['项目类型', '眼下卡点', '推荐站', '网址', '去站上找什么', '找到的具体链接（你填）', '授权已核对（你填）'],
              [[a.type, a.stuck, s['name'], s['url'], '、'.join(t for t in s['tags'] if t in (hit or w)), '', ''] for s in chosen])
    json.dump({'type': a.type, 'stuck': a.stuck, 'hit': hit, 'rows_in': len(rows), 'sites': len(sites), 'pending': len(pend),
               'recommend': [{'name': s['name'], 'url': s['url'], 'tags': s['tags'], 'reason': reason(s, w, hit), 'check': checks.get(s['key'])} for s in chosen],
               'skipped': [{'name': s['name'], 'url': s['url'], 'check': checks[s['key']]} for s in skipped],
               'secs': round(time.time() - t0, 2)}, open(os.path.join(a.out, 'result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n'.join(L)); print('\n耗时 %.2f 秒，输出在 %s' % (time.time() - t0, a.out))

if __name__ == '__main__':
    main()
