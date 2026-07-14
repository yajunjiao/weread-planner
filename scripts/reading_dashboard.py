#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reading_dashboard.py — 微信读书管理与规划 · 仪表盘生成器

读取结构化 reading-log（JSON 或 CSV，字段见 references/data_model.md），
生成一个**自包含、离线可用**的 HTML 仪表盘（内联 SVG 图表，无外部 CDN 依赖）。

用法:
    python reading_dashboard.py --input reading_log.json --output dashboard.html
    python reading_dashboard.py --input reading_log.csv --output dashboard.html --title "我的 2026 阅读" --year 2026

数据来源两种模式:
  A. 逐书模式（默认）：reading-log 的 books[] 提供每本书的状态/时长/分类，
     脚本据此计算月度趋势、分类分布与汇总。
  B. 聚合模式（可选）：reading-log 顶层提供 aggregates 块（来自微信读书统计接口），
     用真实聚合值驱动图表与卡片，books[] 仅用于书籍清单展示。aggregates 结构:
       {
         "summary": {"finished":70,"read_count":154,"total_minutes":24544,"read_days":364,"notes":53000},
         "monthly": {"2026-01": 166678, ...},        # 值单位：秒
         "categoryMinutes": {"经济理财": 515476, ...} # 值单位：秒
       }
     聚合模式与逐书模式可共存；aggregates 优先用于图表与卡片，books 用于清单。

依赖: 仅 Python 标准库 (argparse, json, csv, datetime, html, statistics)
"""

import argparse
import csv
import json
import html
import sys
from datetime import datetime
from collections import defaultdict, OrderedDict

# 默认阅读速度（页/小时），用于缺时长时回填估算
DEFAULT_PAGES_PER_HOUR = 30


# ---------------------------------------------------------------------------
# 数据加载与规整
# ---------------------------------------------------------------------------

def load_data(path):
    """加载 JSON 或 CSV，返回 {'meta': {...}, 'books': [...], 'aggregates': {...}}。"""
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    stripped = raw.lstrip()
    if stripped.startswith('{') or stripped.startswith('['):
        return _load_json(raw)
    return _load_csv(path)


def _load_json(raw):
    data = json.loads(raw)
    if isinstance(data, list):
        data = {'books': data}
    data.setdefault('meta', {})
    data.setdefault('books', [])
    data.setdefault('aggregates', {})
    return data


def _load_csv(path):
    books = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k: (v if v not in ('', None) else None) for k, v in row.items()}
            books.append(row)
    return {'meta': {}, 'books': books, 'aggregates': {}}


def _to_int(v):
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_dt(v):
    """把各种形态的阅读时间解析为 datetime，失败返回 None。

    支持：10 位/13 位时间戳（秒/毫秒）、ISO 字符串、已为 datetime 的对象。
    """
    if v is None or v == '':
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        try:
            n = float(v)
            if n > 1e12:      # 毫秒
                n /= 1000
            return datetime.fromtimestamp(n)
        except (ValueError, TypeError, OSError):
            return None
    if isinstance(v, str):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.strptime(v[:19], fmt)
            except ValueError:
                continue
    return None



def normalize_book(b):
    """规整单本书：补全页数、时长、进度百分比。"""
    total_pages = _to_int(b.get('total_pages'))
    total_words = _to_int(b.get('total_words'))
    if not total_pages and total_words:
        total_pages = round(total_words / 500)
    read_pages = _to_int(b.get('read_pages')) or 0
    minutes = _to_int(b.get('minutes'))

    if minutes is None and read_pages and total_pages:
        minutes = int(read_pages / DEFAULT_PAGES_PER_HOUR * 60)
    # 缺失时保留 None（仪表盘显示「—」），不伪造 0

    status = (b.get('status') or 'want').lower()
    if status not in ('want', 'reading', 'finished'):
        status = 'want'

    pct = 0
    if status == 'finished':
        pct = 100
    elif total_pages:
        pct = min(100, round(read_pages / total_pages * 100))

    return {
        'book_id': b.get('book_id') or '',
        'title': b.get('title') or '未命名',
        'author': b.get('author') or '',
        'status': status,
        'category': b.get('category') or '未分类',
        'total_pages': total_pages or 0,
        'read_pages': read_pages,
        'start_date': b.get('start_date') or '',
        'finish_date': b.get('finish_date') or '',
        'read_update_time': _parse_dt(
            b.get('read_update_time') or b.get('readUpdateTime') or b.get('reading_time')
        ),
        'minutes': minutes,
        'rating': _to_int(b.get('rating')) or 0,
        'note_count': _to_int(b.get('note_count')) or 0,
        'deep_link': b.get('deep_link') or '',
        'pct': pct,
    }


# ---------------------------------------------------------------------------
# 指标计算
# ---------------------------------------------------------------------------

def compute_stats(data):
    books = [normalize_book(b) for b in data['books']]
    meta = data.get('meta', {})
    agg = data.get('aggregates', {})
    summary = agg.get('summary', {}) or {}

    finished = [b for b in books if b['status'] == 'finished']
    reading = [b for b in books if b['status'] == 'reading']
    want = [b for b in books if b['status'] == 'want']

    # ---- 月度趋势 ----
    if agg.get('monthly'):
        monthly = OrderedDict(
            (k, int(v) // 60) for k, v in sorted(agg['monthly'].items())
        )
    else:
        monthly = defaultdict(int)
        for b in books:
            d = b['finish_date'] or b['start_date']
            if d:
                try:
                    m = datetime.strptime(d[:10], '%Y-%m-%d').strftime('%Y-%m')
                    monthly[m] += b['minutes']
                except ValueError:
                    pass
        monthly = OrderedDict(sorted(monthly.items()))

    # ---- 分类分布 ----
    if agg.get('categoryMinutes'):
        cat_minutes = {k: int(v) // 60 for k, v in agg['categoryMinutes'].items()}
        categories = sorted(cat_minutes.items(), key=lambda x: x[1], reverse=True)
    else:
        cat_minutes = defaultdict(int)
        for b in books:
            cat_minutes[b['category']] += b['minutes']
        categories = sorted(cat_minutes.items(), key=lambda x: x[1], reverse=True)

    # ---- 汇总 ----
    if summary:
        total_minutes = _to_int(summary.get('total_minutes'))
        if total_minutes is None:
            total_minutes = sum(b['minutes'] or 0 for b in books)
        total_notes = _to_int(summary.get('notes'))
        if total_notes is None:
            total_notes = sum(b['note_count'] for b in books)
        active_days = _to_int(summary.get('read_days'))
        if active_days is None:
            active_days = 0
        counts = {
            'finished': _to_int(summary.get('finished')),
            'reading': _to_int(summary.get('reading')),
            'want': _to_int(summary.get('want')),
            'total': len(books),
        }
    else:
        total_minutes = sum(b['minutes'] or 0 for b in books)
        total_notes = sum(b['note_count'] for b in books)
        active_days = len({d[:10] for b in books for d in (b['start_date'], b['finish_date']) if d})
        counts = {'finished': len(finished), 'reading': len(reading), 'want': len(want), 'total': len(books)}

    total_pages = sum(b['total_pages'] for b in books)

    ratings = [b['rating'] for b in finished if b['rating'] > 0]

    goal = _to_int(meta.get('goal_books'))
    goal_progress = None
    if goal and counts['finished']:
        goal_progress = round(counts['finished'] / goal * 100)

    return {
        'books': books,
        'meta': meta,
        'summary': summary,
        'finished': finished,
        'reading': reading,
        'want': want,
        'counts': counts,
        'total_minutes': total_minutes,
        'total_pages': total_pages,
        'total_notes': total_notes,
        'monthly': monthly,
        'categories': categories,
        'cat_minutes': cat_minutes,
        'ratings': ratings,
        'active_days': active_days,
        'goal': goal,
        'goal_progress': goal_progress,
    }


# ---------------------------------------------------------------------------
# SVG 图表
# ---------------------------------------------------------------------------

def _esc(s):
    return html.escape(str(s))


def svg_vbars(labels, values, width=720, height=220, color='#4f7cff'):
    if not values:
        return '<p class="empty">暂无数据</p>'
    max_v = max(values) or 1
    n = len(values)
    pad = 30
    plot_w = width - pad * 2
    plot_h = height - pad * 2
    gap = plot_w / n if n else plot_w
    bar_w = gap * 0.6
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" preserveAspectRatio="xMidYMid meet" role="img">']
    parts.append(f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#e2e8f0" />')
    for i, (lab, val) in enumerate(zip(labels, values)):
        x = pad + gap * i + (gap - bar_w) / 2
        h = val / max_v * plot_h
        y = height - pad - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{color}"><title>{_esc(lab)}: {val}</title></rect>')
        parts.append(f'<text x="{x+bar_w/2:.1f}" y="{y-5:.1f}" text-anchor="middle" font-size="11" fill="#475569">{val}</text>')
        short = _esc(lab[-5:]) if len(str(lab)) > 5 else _esc(lab)
        parts.append(f'<text x="{x+bar_w/2:.1f}" y="{height-pad+16:.1f}" text-anchor="middle" font-size="10" fill="#94a3b8">{short}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def svg_hbars(items, width=720, color='#22c55e'):
    if not items:
        return '<p class="empty">暂无数据</p>'
    max_v = max(v for _, v in items) or 1
    row_h = 30
    height = len(items) * row_h + 10
    label_w = 110
    bar_area = width - label_w - 70
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for i, (lab, val) in enumerate(items):
        y = i * row_h + 6
        w = val / max_v * bar_area
        lbl = _esc(lab)
        if len(lbl) > 7:
            lbl = lbl[:7] + '…'
        parts.append(f'<text x="{label_w-8}" y="{y+row_h/2:.1f}" text-anchor="end" font-size="12" fill="#475569">{lbl}</text>')
        parts.append(f'<rect x="{label_w}" y="{y:.1f}" width="{w:.1f}" height="{row_h-10}" rx="4" fill="{color}"><title>{_esc(lab)}: {val}</title></rect>')
        parts.append(f'<text x="{label_w+w+6:.1f}" y="{y+row_h/2:.1f}" font-size="11" fill="#64748b">{val}</text>')
    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# HTML 渲染
# ---------------------------------------------------------------------------

def _fmt_minutes(m):
    m = int(m)
    h = m // 60
    mm = m % 60
    if h:
        return f'{h} 小时 {mm} 分钟' if mm else f'{h} 小时'
    return f'{mm} 分钟'


def _build_cards(stats):
    summary = stats['summary'] or {}
    cards = []
    daily_min = round(stats['total_minutes'] / stats['active_days']) if stats['active_days'] else 0
    if 'finished' in summary:
        cards.append(('读完', f"{summary['finished']} 本", '#4f7cff'))
    if 'read_count' in summary:
        cards.append(('读过', f"{summary['read_count']} 本", '#06b6d4'))
    cards.append(('总时长', _fmt_minutes(stats['total_minutes']), '#22c55e'))
    cards.append(('日均时长', _fmt_minutes(daily_min), '#06b6d4'))
    if 'notes' in summary and summary['notes'] is not None:
        cards.append(('笔记', f"{summary['notes']:,} 条", '#ef4444'))
    elif 'notes' in summary:
        cards.append(('笔记', '暂无数据', '#ef4444'))
    if 'read_days' in summary:
        cards.append(('活跃天数', f"{summary['read_days']} 天", '#a855f7'))
    # 无聚合汇总时回退到逐书计数
    if not cards:
        c = stats['counts']
        cards = [
            ('读完', f"{c['finished']} 本", '#4f7cff'),
            ('在读', f"{c['reading']} 本", '#f59e0b'),
            ('想读', f"{c['want']} 本", '#94a3b8'),
            ('总时长', _fmt_minutes(stats['total_minutes']), '#22c55e'),
            ('日均时长', _fmt_minutes(daily_min), '#06b6d4'),
            ('总页数', f"{stats['total_pages']:,}", '#a855f7'),
            ('笔记', f"{stats['total_notes']} 条", '#ef4444'),
            ('活跃天数', f"{stats['active_days']} 天", '#06b6d4'),
        ]
    return cards


def render_html(stats, title):
    owner = stats['meta'].get('owner', '')
    year = stats['meta'].get('year', '')
    page_title = title or f'{owner}{year} 阅读仪表盘'.strip() or '微信读书阅读仪表盘'

    cards = _build_cards(stats)
    cards_html = ''.join(
        f'<div class="card"><div class="card-val" style="color:{col}">{val}</div><div class="card-label">{lab}</div></div>'
        for lab, val, col in cards
    )

    # ─── 时长英雄区 ───
    total_minutes = stats['total_minutes']
    total_hours = total_minutes / 60.0
    active_days = stats['active_days'] or 0
    daily_min = round(total_minutes / active_days) if active_days else 0
    equiv_days = total_hours / 24.0
    hero_html = f'''
    <div class="hero">
      <div class="hero-main">
        <div class="hero-val">{total_hours:,.1f}<span class="hero-unit"> 小时</span></div>
        <div class="hero-label">累计阅读时长（{year or '全部'}）</div>
      </div>
      <div class="hero-sub">
        <div class="hero-sub-item"><b>{daily_min}</b> 分钟 <span>日均投入</span></div>
        <div class="hero-sub-item"><b>{active_days}</b> 天 <span>阅读日</span></div>
        <div class="hero-sub-item"><b>{equiv_days:,.1f}</b> 天 <span>≈ 不眠不休时长</span></div>
      </div>
    </div>'''

    monthly_labels = list(stats['monthly'].keys())
    monthly_vals = list(stats['monthly'].values())
    monthly_html = svg_vbars(monthly_labels, monthly_vals)

    cat_items = [(cat, stats['cat_minutes'][cat]) for cat, _ in stats['categories']]
    cat_html = svg_hbars(cat_items)

    rows = []
    for b in sorted(stats['books'], key=lambda x: (0 if x['status'] == 'finished' else 1, x['minutes'] or 0), reverse=True):
        status_map = {'finished': '已读', 'reading': '在读', 'want': '想读'}
        link = f'<a href="{_esc(b["deep_link"])}" target="_blank">打开</a>' if b['deep_link'] else '—'

        # 进度：读完即 100%；有页数按页数比；否则按状态
        if b['status'] == 'finished':
            prog = '100%'
        elif b['total_pages']:
            prog = f"{min(100, round(b['read_pages'] / b['total_pages'] * 100))}%"
        else:
            prog = '—'
        page_txt = f"{b['read_pages']}/{b['total_pages']} 页" if b['total_pages'] else '—'
        mins = b['minutes']
        if not mins:
            dur_txt = '—'
        elif b.get('estimated'):
            dur_txt = '≈' + _fmt_minutes(mins)
        else:
            dur_txt = _fmt_minutes(mins)
        rows.append(f'''<tr>
          <td>{_esc(b["title"])}<br><span class="muted">{_esc(b["author"])}</span></td>
          <td>{status_map[b['status']]}</td>
          <td>{_esc(b['category'])}</td>
          <td>{prog}<br><span class="muted">{page_txt}</span></td>
          <td>{dur_txt}</td>
          <td>{link}</td>
        </tr>''')
    book_table = ''.join(rows) or '<tr><td colspan="6" class="muted">暂无书籍记录</td></tr>'

    agg_note = '数据来源：微信读书阅读统计接口（聚合模式）' if stats['summary'] else '数据来源：逐书 reading-log'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(page_title)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background:#f1f5f9; color:#1e293b; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }}
  header h1 {{ margin:0 0 4px; font-size: 26px; }}
  header .sub {{ color:#64748b; font-size: 14px; }}
  .cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(120px,1fr)); gap:14px; margin:22px 0; }}
  .card {{ background:#fff; border-radius:14px; padding:18px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
  .card-val {{ font-size:22px; font-weight:700; }}
  .card-label {{ font-size:13px; color:#64748b; margin-top:4px; }}
  .hero {{ background:linear-gradient(120deg,#22c55e,#06b6d4); border-radius:18px; padding:30px 28px; color:#fff;
          box-shadow:0 6px 20px rgba(34,197,94,.25); margin:22px 0; display:flex; flex-wrap:wrap; align-items:flex-end; gap:24px; }}
  .hero-main {{ flex:1 1 240px; }}
  .hero-val {{ font-size:54px; font-weight:800; line-height:1; }}
  .hero-unit {{ font-size:24px; font-weight:600; }}
  .hero-label {{ font-size:14px; opacity:.92; margin-top:8px; }}
  .hero-sub {{ display:flex; gap:26px; flex-wrap:wrap; }}
  .hero-sub-item {{ font-size:13px; opacity:.95; }}
  .hero-sub-item b {{ font-size:22px; display:block; font-weight:700; }}
  .panel {{ background:#fff; border-radius:14px; padding:20px; margin:18px 0; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
  .panel h2 {{ margin:0 0 14px; font-size:17px; }}
  .progress {{ background:#e2e8f0; border-radius:999px; height:14px; overflow:hidden; }}
  .progress-bar {{ background:linear-gradient(90deg,#4f7cff,#22c55e); height:100%; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:9px 8px; border-bottom:1px solid #f1f5f9; }}
  th {{ color:#64748b; font-weight:600; }}
  .muted {{ color:#94a3b8; font-size:12px; }}
  .empty {{ color:#94a3b8; }}
  a {{ color:#4f7cff; text-decoration:none; }}
  .src {{ text-align:center; color:#94a3b8; font-size:12px; margin-top:18px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{_esc(page_title)}</h1>
    <div class="sub">微信读书管理与规划 · 离线仪表盘 · 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
  </header>

  {hero_html}

  <div class="cards">{cards_html}</div>

  <div class="panel">
    <h2>月度阅读时长（小时）</h2>
    {monthly_html}
  </div>

  <div class="panel">
    <h2>主题分布（按阅读时长·小时）</h2>
    {cat_html}
  </div>

  <div class="panel">
    <h2>书籍清单（按阅读时长排序）</h2>
    <table>
      <thead><tr><th>书名</th><th>状态</th><th>主题</th><th>进度</th><th>时长</th><th>链接</th></tr></thead>
      <tbody>{book_table}</tbody>
    </table>
    <p class="muted">标注 ≈ 的时长为按所属分类均值估算（微信读书接口仅返回「读得最久的 10 本」实测时长）；未标注为实测值。</p>
  </div>

  <div class="src">{agg_note} · 由 weread-planner 生成</div>
</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='微信读书 reading-log → HTML 仪表盘')
    ap.add_argument('--input', '-i', required=True, help='reading-log 文件 (JSON 或 CSV)')
    ap.add_argument('--output', '-o', default='dashboard.html', help='输出 HTML 路径')
    ap.add_argument('--title', '-t', default='', help='仪表盘标题')
    ap.add_argument('--year', '-y', type=int, default=None, help='统计年份（覆盖 meta）')
    args = ap.parse_args()

    try:
        data = load_data(args.input)
    except FileNotFoundError:
        sys.exit('错误：找不到输入文件 ' + args.input)
    except Exception as e:
        sys.exit('错误：解析失败 - ' + str(e))

    if args.year:
        data.setdefault('meta', {})['year'] = args.year

    stats = compute_stats(data)
    out = render_html(stats, args.title)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(out)
    print('[OK] 仪表盘已生成: ' + args.output)
    print('     书籍 ' + str(stats['counts']['total']) + ' 本 | 总时长 ' + _fmt_minutes(stats['total_minutes']))


if __name__ == '__main__':
    main()
