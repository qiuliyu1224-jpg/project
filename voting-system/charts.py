"""Dependency-free, escaped SVG charts of an existing result snapshot.

The original count result is not changed by chart selection. All values are
labelled comparisons between entries, not inferred changes over time.
"""
import hashlib
import html
import math


KINDS = {'bar', 'horizontal', 'line'}


def chart_data(result, lang='en', rcv_round=None, labels=None):
    """Return chart rows without changing the count result.

    ``labels`` may map candidate IDs to already-translated names. ``rcv_round``
    selects a one-based IRV count iteration within this ballot round; by default
    the final available count is shown. Eliminated entries have value None.
    """
    t = lambda zh, en: zh if lang == 'zh' else en
    method = result['method']
    label_map = labels or {}
    step = None
    count_number = None
    if method == 'RCV':
        rounds = result.get('rounds', [])
        if rounds:
            try:
                count_number = len(rounds) if rcv_round is None else int(rcv_round)
            except (ValueError, TypeError):
                raise ValueError('Invalid RCV count number') from None
            if not 1 <= count_number <= len(rounds):
                raise ValueError('Invalid RCV count number')
            step = rounds[count_number - 1]
        elif rcv_round is not None:
            raise ValueError('No RCV counts available')
    rows = []
    for source in result.get('rows', []):
        name = str(label_map.get(source['id'], label_map.get(str(source['id']), source['name'])))
        n = source.get('n', 0)
        if method == 'SCORE':
            value = source.get('average') if n else None
            note = t(f'{n} 人评分', f'{n} ratings') if n else t('未评分', 'Not rated')
        elif method == 'RCV':
            tally = step['counts'] if step else {}
            value = tally.get(source['id'], tally.get(str(source['id'])))
            note = t('不在本次计票中', 'Not active in this count') if value is None else t('当前有效偏好票', 'Continuing preference votes')
        else:
            value = source.get('total', 0)
            note = t('得票数', 'Votes')
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('Chart values must be finite non-negative numbers')
            if method == 'SCORE' and value > 5:
                raise ValueError('Average rating must be between zero and five')
        rows.append({'id': source['id'], 'name': name, 'value': value, 'n': n, 'note': note})
    if method == 'SCORE':
        metric = t('平均评分（满分 5 分）', 'Average rating (out of 5)')
        maximum = 5
        caption = t('未评分不当作零分；每个作品同时显示评分人数。', 'Unrated entries are not zero. Rating counts are included for each entry.')
    elif method == 'RCV':
        metric = t(f'RCV 第 {count_number or 0} 次计票的有效偏好票', f'Continuing preference votes in RCV count {count_number or 0}')
        maximum = max([1] + [r['value'] for r in rows if r['value'] is not None])
        caption = t('这里的计票次数来自同一批排序选票，不是再次投票。已淘汰作品不记为零票。', 'These counts reuse the same ranked ballots; voters do not vote again. Eliminated entries are not shown as zero votes.')
    else:
        metric = t('得票数', 'Votes')
        maximum = max([1] + [r['value'] for r in rows if r['value'] is not None])
        caption = t('每个选中作品各计 1 票；多选活动的合计票数可以超过选票张数。', 'Each selected entry receives one vote. In multiple-choice events, total selections may exceed the number of ballots.') if method == 'SINGLE' else t('每张选票只计给 1 个作品。', 'Each ballot counts for one entry.')
    return {'rows': rows, 'metric': metric, 'maximum': maximum, 'caption': caption,
            'method': method, 'rcv_round': count_number}


def render_chart(result, kind='bar', lang='en', rcv_round=None, labels=None):
    """Return accessible inline SVG plus a localized explanatory caption.

    Call only after the normal result permission checks. No external scripts,
    network requests or personal ballot identities are included.
    """
    if kind not in KINDS:
        raise ValueError('Unknown chart type')
    data = chart_data(result, lang=lang, rcv_round=rcv_round, labels=labels)
    rows, metric = data['rows'], data['metric']
    t = lambda zh, en: zh if lang == 'zh' else en
    esc = lambda text: html.escape(str(text), quote=True)
    fmt = lambda value: f'{value:.2f}' if data['method'] == 'SCORE' else f'{value:g}'
    shorten = lambda text, n: text if len(text) <= n else text[:n-1] + '…'
    count = len(rows)
    chart_name = {'bar': t('柱状图', 'Column chart'), 'horizontal': t('横向柱状图', 'Horizontal bar chart'), 'line': t('折线图', 'Line chart')}[kind]
    description = metric + '. ' + data['caption']
    if kind == 'line':
        description += ' ' + t('连线只用于比较不同作品，不表示随时间变化；未评分或已淘汰项不连线。', 'The line connects entry categories, not changes over time. Unrated or eliminated entries break the line.')
    uid = hashlib.sha256((str(result.get('ballots', 0)) + kind + lang + metric).encode()).hexdigest()[:10]
    width = max(760, count * (76 if kind != 'horizontal' else 0) + 100)
    height = max(330, count * 45 + 105) if kind == 'horizontal' else 445
    pieces = [f'<div class="result-chart" style="overflow-x:auto"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" role="img" aria-labelledby="chart-title-{uid} chart-desc-{uid}" style="display:block;width:{width}px;max-width:none;height:auto;min-width:620px;font-family:system-ui,sans-serif">',
              f'<title id="chart-title-{uid}">{esc(chart_name + ": " + metric)}</title>',
              f'<desc id="chart-desc-{uid}">{esc(description)}</desc>',
              f'<rect width="{width}" height="{height}" fill="#fff"/>',
              f'<text x="24" y="28" font-size="16" fill="#183a33">{esc(metric)}</text>']
    if not rows:
        pieces.append(f'<text x="24" y="70" font-size="15">{esc(t("暂无作品", "No entries available"))}</text>')
    elif kind == 'horizontal':
        left, right, top = 215, width - 95, 65
        plot = right - left
        for i, row in enumerate(rows):
            y = top + i * 45
            pieces.append(f'<text x="{left-12}" y="{y+4}" text-anchor="end" fill="#263a36" font-size="13"><title>{esc(row["name"])}</title>{esc(shorten(row["name"], 23))}</text>')
            if row['value'] is None:
                pieces.append(f'<text x="{left+5}" y="{y+4}" fill="#5b6661" font-size="12">{esc(row["note"])}</text>')
                continue
            size = plot * row['value'] / data['maximum']
            title = f'{row["name"]}: {fmt(row["value"])}; {row["note"]}'
            pieces.append(f'<rect x="{left}" y="{y-13}" width="{size:.2f}" height="25" fill="#236857"><title>{esc(title)}</title></rect>')
            pieces.append(f'<text x="{left+size+7:.2f}" y="{y+4}" font-size="13" fill="#183a33">{esc(fmt(row["value"]))}</text>')
            if data['method'] == 'SCORE':
                pieces.append(f'<text x="{left}" y="{y+26}" font-size="11" fill="#5b6661">{esc(row["note"])}</text>')
        pieces.append(f'<line x1="{left}" y1="45" x2="{left}" y2="{top+(count-1)*45+31}" stroke="#8c9b94"/>')
    else:
        left, right, top, bottom = 65, width-25, 68, 310
        plot_width, plot_height = right-left, bottom-top
        maximum = data['maximum']
        if data['method'] == 'SCORE':
            ticks = [0, 1, 2, 3, 4, 5]
        else:
            step = max(1, math.ceil(maximum / 5))
            maximum = max(step, math.ceil(maximum/step)*step)
            ticks = list(range(0, int(maximum)+1, step))
        for tick in ticks:
            y = bottom - plot_height*tick/maximum
            pieces.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="#e1e7e3"/><text x="{left-10}" y="{y+4:.2f}" text-anchor="end" fill="#56645d" font-size="12">{tick}</text>')
        cell = plot_width/max(1, count)
        points = []
        segments = []
        for i, row in enumerate(rows):
            x = left+cell*(i+.5)
            pieces.append(f'<text x="{x:.2f}" y="{bottom+23}" text-anchor="end" transform="rotate(-24 {x:.2f} {bottom+23})" fill="#263a36" font-size="12"><title>{esc(row["name"])}</title>{esc(shorten(row["name"], 20))}</text>')
            if row['value'] is None:
                if points:
                    segments.append(points)
                    points = []
                pieces.append(f'<text x="{x:.2f}" y="{bottom-9}" text-anchor="middle" fill="#68746d" font-size="11">—<title>{esc(row["note"])}</title></text>')
                continue
            y = bottom-plot_height*row['value']/maximum
            title = f'{row["name"]}: {fmt(row["value"])}; {row["note"]}'
            if kind == 'bar':
                bw = min(52, cell*.65)
                pieces.append(f'<rect x="{x-bw/2:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{bottom-y:.2f}" fill="#236857"><title>{esc(title)}</title></rect>')
            else:
                points.append((x,y,title))
            pieces.append(f'<text x="{x:.2f}" y="{y-9:.2f}" text-anchor="middle" fill="#183a33" font-size="12">{esc(fmt(row["value"]))}</text>')
            if data['method'] == 'SCORE':
                pieces.append(f'<text x="{x:.2f}" y="{bottom+84}" text-anchor="middle" fill="#56645d" font-size="11">{esc(row["note"])}</text>')
        if points:
            segments.append(points)
        for segment in segments:
            if len(segment) > 1:
                coords=' '.join(f'{x:.2f},{y:.2f}' for x,y,_ in segment)
                pieces.append(f'<polyline points="{coords}" fill="none" stroke="#236857" stroke-width="2.5"/>')
            for x,y,title in segment:
                pieces.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#236857"><title>{esc(title)}</title></circle>')
        pieces.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#8c9b94"/>')
    pieces.extend(['</svg></div>', f'<p class="helper chart-caption">{esc(description)}</p>'])
    return ''.join(pieces)
