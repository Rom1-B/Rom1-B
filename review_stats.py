# Finds every PR reviewed by USERNAME via the GitHub Search API, then fetches
# each PR's review list concurrently to count actual review submissions (not
# deduplicated per PR, unlike GitHub's contribution graph), bucketed by ISO
# week. Renders a bar chart in reviews_by_week.svg.

import argparse
import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

GITHUB_SEARCH_LIMIT = 1000
MAX_WORKERS = 10
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


def collect_reviewed_prs() -> list[str]:
    """Returns repo full names paired with PR numbers reviewed by USERNAME."""
    prs: list[tuple[str, int]] = []
    page = 1
    while True:
        search_url = (
            f"https://api.github.com/search/issues"
            f"?q=is:pr+reviewed-by:{USERNAME}&sort=updated&order=desc&per_page=100&page={page}"
        )
        data = fetch_with_retry(search_url)
        if not data:
            break

        items = data.get('items', [])
        if not items:
            break

        for item in items:
            repo_full_name = item['repository_url'].removeprefix('https://api.github.com/repos/')
            prs.append((repo_full_name, item['number']))

        total_items = data.get('total_count', 0)
        if len(prs) >= GITHUB_SEARCH_LIMIT or page * 100 >= total_items:
            if len(prs) >= GITHUB_SEARCH_LIMIT:
                print(f"  [GitHub Search API limit reached at {GITHUB_SEARCH_LIMIT} PRs]")
            break
        page += 1

    return prs[:GITHUB_SEARCH_LIMIT]


def process_pr(repo_full_name: str, number: int) -> list[str]:
    reviews = fetch_with_retry(f"https://api.github.com/repos/{repo_full_name}/pulls/{number}/reviews?per_page=100")
    if not reviews:
        return []
    return [
        review['submitted_at'][:10]
        for review in reviews
        if review.get('user', {}).get('login') == USERNAME and review.get('submitted_at')
    ]


def fetch_reviews() -> list[str]:
    prs = collect_reviewed_prs()
    print(f"  [{len(prs)} reviewed PRs found, fetching review details...]")

    dates: list[str] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_pr, repo, number) for repo, number in prs]
        for i, future in enumerate(as_completed(futures), start=1):
            dates.extend(future.result())
            if i % 100 == 0:
                print(f"  [{i} PRs processed]")

    return dates


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


def generate_svg(daily: list[tuple[str, int]], total: int, period: str, updated_at: str) -> str:
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
        f'aria-label="PR reviews per week: {period}">'
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
        f'PR reviews per week · {total} total · {period}</text>'
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Chart PR reviews per week from GitHub.")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD), default: 1 year ago")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD), default: today")
    parser.add_argument("--output", default="reviews_by_week.svg", help="Output SVG path")
    args = parser.parse_args()

    to_dt = datetime.fromisoformat(args.to_date) if args.to_date else datetime.now(timezone.utc).replace(tzinfo=None)
    from_dt = (
        datetime.fromisoformat(args.from_date)
        if args.from_date
        else to_dt - timedelta(days=365)
    )

    print(f"Fetching PR reviews for {USERNAME} from {from_dt.date()} to {to_dt.date()}...")
    dates = fetch_reviews()
    daily = build_daily_counts(dates, from_dt, to_dt)
    weekly = build_weekly_counts(daily)
    total = sum(count for _, count in daily)

    period_label = f"{from_dt.date()} to {to_dt.date()}"
    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    svg_content = generate_svg(weekly, total, period_label, updated_at)

    with open(args.output, "w") as f:
        f.write(svg_content)

    print(f"✓ {total} reviews found")
    print(f"✓ {args.output} generated")
    busiest = max(weekly, key=lambda d: d[1], default=None)
    if busiest and busiest[1]:
        print(f"✓ Busiest week of {busiest[0]}: {busiest[1]} reviews")


if __name__ == "__main__":
    main()
