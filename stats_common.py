# Shared building blocks for the weekly-bar-chart SVG stats scripts
# (review_stats.py, pr_stats.py): retrying HTTP fetch, daily/weekly
# bucketing, and SVG rendering.

import os
import time
from collections import Counter
from datetime import datetime, timedelta

import requests

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

GITHUB_SEARCH_LIMIT = 1000
MAX_RETRIES = 3

headers = {"Authorization": f"token {GITHUB_TOKEN}"}


def fetch_with_retry(url: str) -> dict | list | None:
    for attempt in range(MAX_RETRIES):
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        if response.status_code in (429, 503):
            wait = 2 ** attempt
            print(f"  [Rate limited, retrying in {wait}s...]")
            time.sleep(wait)
            continue
        print(f"  [HTTP {response.status_code} for {url}]")
        return None
    print(f"  [Giving up after {MAX_RETRIES} retries: {url}]")
    return None


def build_daily_counts(dates: list[str], from_dt: datetime, to_dt: datetime) -> list[tuple[str, int]]:
    from_key, to_key = from_dt.date().isoformat(), to_dt.date().isoformat()
    counts = Counter(d for d in dates if from_key <= d <= to_key)
    days = []
    cursor = from_dt.date()
    end = to_dt.date()
    while cursor <= end:
        key = cursor.isoformat()
        days.append((key, counts.get(key, 0)))
        cursor += timedelta(days=1)
    return days


def build_weekly_counts(daily: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Buckets daily counts into ISO weeks (Monday start), preserving order."""
    weekly: dict[str, int] = {}
    for day_str, count in daily:
        d = datetime.fromisoformat(day_str).date()
        week_start = (d - timedelta(days=d.weekday())).isoformat()
        weekly[week_start] = weekly.get(week_start, 0) + count
    return list(weekly.items())


def generate_svg(daily: list[tuple[str, int]], total: int, period: str, updated_at: str, metric_label: str) -> str:
    pad_x = 24
    pad_top = 50
    bar_area_h = 120
    axis_y = pad_top + bar_area_h
    height = axis_y + 34

    max_count = max((c for _, c in daily), default=0)
    n = len(daily)

    # Bar width must fit its own count label (up to 3 digits at font-size 10).
    label_chars = len(str(max_count)) if max_count else 1
    bar_w = max(label_chars * 6 + 4, 14)
    inner_w = bar_w * n
    width = pad_x * 2 + inner_w
    max_count = max_count or 1

    lines: list[str] = []
    lines.append(
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{metric_label} per week: {period}">'
    )

    lines.append('<style>')
    lines.append('.bg { fill: #fcfcfb; stroke: rgba(11,11,11,0.10); }')
    lines.append('.title { fill: #0b0b0b; }')
    lines.append('.axis-label { fill: #898781; }')
    lines.append('.baseline { stroke: #c3c2b7; }')
    lines.append('.bar { fill: #2a78d6; }')
    lines.append('.bar-label { fill: #52514e; }')
    lines.append('.footer { fill: #898781; }')
    lines.append('@media (prefers-color-scheme: dark) {')
    lines.append('  .bg { fill: #1a1a19; stroke: rgba(255,255,255,0.10); }')
    lines.append('  .title { fill: #ffffff; }')
    lines.append('  .axis-label { fill: #c3c2b7; }')
    lines.append('  .baseline { stroke: #383835; }')
    lines.append('  .bar { fill: #3987e5; }')
    lines.append('  .bar-label { fill: #c3c2b7; }')
    lines.append('  .footer { fill: #c3c2b7; }')
    lines.append('}')
    lines.append('</style>')

    lines.append(f'<rect class="bg" width="{width}" height="{height}" rx="12" stroke-width="1"/>')

    lines.append(
        f'<text x="{pad_x}" y="26" font-family="system-ui,-apple-system,\'Segoe UI\',sans-serif" '
        f'font-size="13" font-weight="500" class="title">'
        f'{metric_label} per week · {total} total · {period}</text>'
    )

    for i, (day, count) in enumerate(daily):
        bar_h = (count / max_count) * bar_area_h if count else 0
        x = pad_x + i * bar_w
        y = axis_y - bar_h
        w = max(bar_w - 2, 1)
        if count:
            lines.append(f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{bar_h:.2f}"/>')
            lx = x + bar_w / 2
            ly = y - 6
            lines.append(
                f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="middle" '
                f'font-family="system-ui,-apple-system,\'Segoe UI\',sans-serif" '
                f'font-size="10" class="bar-label">{count}</text>'
            )

    lines.append(f'<line class="baseline" x1="{pad_x}" y1="{axis_y}" x2="{width - pad_x}" y2="{axis_y}"/>')

    last_month: str | None = None
    for i, (day, _count) in enumerate(daily):
        month_key = day[:7]
        if month_key != last_month:
            last_month = month_key
            x = pad_x + i * bar_w
            label = datetime.fromisoformat(day).strftime('%b')
            lines.append(
                f'<text x="{x:.2f}" y="{axis_y + 14}" '
                f'font-family="system-ui,-apple-system,\'Segoe UI\',sans-serif" '
                f'font-size="10" class="axis-label">{label}</text>'
            )

    lines.append(
        f'<text x="{pad_x}" y="{height - 8}" '
        f'font-family="system-ui,-apple-system,\'Segoe UI\',sans-serif" '
        f'font-size="10" class="footer">Updated {updated_at} UTC</text>'
    )

    lines.append('</svg>')
    return '\n'.join(lines)
