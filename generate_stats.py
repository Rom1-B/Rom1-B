import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
from datetime import datetime

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

GITHUB_SEARCH_LIMIT = 1000
MAX_WORKERS = 10
MAX_RETRIES = 3

print(f"Generating stats for {USERNAME}...")

headers = {"Authorization": f"token {GITHUB_TOKEN}"}

LANGUAGE_MAP = {
    '.php': 'PHP',
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.go': 'Go',
    '.rs': 'Rust',
    '.java': 'Java',
    '.c': 'C',
    '.cpp': 'C++',
    '.cs': 'C#',
    '.rb': 'Ruby',
    '.sh': 'Shell',
    '.vue': 'Vue',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.html': 'HTML',
    '.twig': 'Twig',
    '.json': 'JSON',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.sql': 'SQL',
    '.makefile': 'Makefile',
}

# GitHub Linguist-inspired colors
LANGUAGE_COLORS: dict[str, str] = {
    'PHP':        '#4F5D95',
    'Python':     '#3572A5',
    'JavaScript': '#F1E05A',
    'TypeScript': '#3178C6',
    'Go':         '#00ADD8',
    'Rust':       '#DEA584',
    'Java':       '#B07219',
    'C':          '#555555',
    'C++':        '#F34B7D',
    'C#':         '#178600',
    'Ruby':       '#701516',
    'Shell':      '#89E051',
    'Vue':        '#41B883',
    'CSS':        '#563D7C',
    'SCSS':       '#C6538C',
    'HTML':       '#E34C26',
    'Twig':       '#C1D026',
    'JSON':       '#292929',
    'YAML':       '#CB171E',
    'SQL':        '#E38C00',
    'Makefile':   '#427819',
}

FALLBACK_COLORS = [
    '#6E4ADB', '#0D9E75', '#D85A30', '#BA7517',
    '#378ADD', '#639922', '#D4537E', '#888780',
]


def fetch_with_retry(url: str) -> dict | None:
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


def process_commit(commit_url: str) -> tuple[dict[str, int], datetime | None]:
    data = fetch_with_retry(commit_url)
    if data is None:
        return {}, None

    langs: dict[str, int] = defaultdict(int)
    for file in data.get('files', []):
        filename = file['filename']
        for ext, lang in LANGUAGE_MAP.items():
            if filename.endswith(ext):
                langs[lang] += file.get('additions', 0)
                break

    date_str = data.get('commit', {}).get('author', {}).get('date')
    commit_date: datetime | None = None
    if date_str:
        commit_date = datetime.fromisoformat(
            date_str.replace('Z', '+00:00')
        ).replace(tzinfo=None)

    return dict(langs), commit_date


search_query = f"author:{USERNAME}"

print(f"Searching last {GITHUB_SEARCH_LIMIT} commits...")

languages: dict[str, int] = defaultdict(int)
page = 1
total_commits = 0
commit_urls: list[str] = []

# Collect all commit URLs first
while True:
    search_url = (
        f"https://api.github.com/search/commits"
        f"?q={search_query}&sort=committer-date&order=desc&per_page=100&page={page}"
    )
    data = fetch_with_retry(search_url)
    if data is None:
        break

    commits = data.get('items', [])
    if not commits:
        break

    commit_urls.extend(commit['url'] for commit in commits)
    total_items = data.get('total_count', 0)

    if len(commit_urls) >= GITHUB_SEARCH_LIMIT or page * 100 >= total_items:
        if len(commit_urls) >= GITHUB_SEARCH_LIMIT:
            print(f"  [GitHub Search API limit reached at {GITHUB_SEARCH_LIMIT} commits]")
        break

    page += 1

commit_urls = commit_urls[:GITHUB_SEARCH_LIMIT]

# Fetch commit details concurrently
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(process_commit, url): url for url in commit_urls}
    for future in as_completed(futures):
        langs, _ = future.result()
        for lang, count in langs.items():
            languages[lang] += count
        total_commits += 1
        if total_commits % 100 == 0:
            print(f"  [{total_commits} commits processed]")

# Commits are sorted desc by date, so the last URL is the oldest
_, oldest_commit_date = process_commit(commit_urls[-1]) if commit_urls else ({}, None)

print(f"✓ {total_commits} commits analyzed")
print(f"✓ {sum(languages.values())} lines of code added")

total_lines = sum(languages.values())
sorted_langs = [
    (lang, count)
    for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True)
    if count > 0 and count / total_lines * 100 >= 0.1
]

if oldest_commit_date is not None:
    period_label = f"Last {total_commits} commits · since {oldest_commit_date.strftime('%Y-%m-%d')}"
else:
    period_label = f"Last {total_commits} commits"


def lang_color(lang: str, index: int) -> str:
    return LANGUAGE_COLORS.get(lang, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])


def generate_svg(
    langs: list[tuple[str, int]],
    total: int,
    period: str,
    updated_at: str,
) -> str:
    width = 500
    pad_x = 24
    inner_w = width - pad_x * 2

    bar_y = 52
    bar_h = 10
    bar_r = 5
    gap = 2

    legend_cols = 3
    legend_row_h = 24
    legend_rows = -(-len(langs) // legend_cols)
    legend_top = bar_y + bar_h + 20

    footer_y = legend_top + legend_rows * legend_row_h + 18
    height = footer_y + 22

    lines: list[str] = []
    lines.append(
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="GitHub language stats: {period}">'
    )

    lines.append(
        f'<rect width="{width}" height="{height}" rx="12" '
        f'fill="#ffffff" stroke="#e1e4e8" stroke-width="1"/>'
    )

    lines.append('<style>')
    lines.append('@media (prefers-color-scheme: dark) {')
    lines.append('  .bg { fill: #161b22; stroke: #30363d; }')
    lines.append('  .title { fill: #e6edf3; }')
    lines.append('  .legend-name { fill: #e6edf3; }')
    lines.append('  .legend-pct { fill: #8b949e; }')
    lines.append('  .footer { fill: #8b949e; }')
    lines.append('  .track { fill: #21262d; }')
    lines.append('}')
    lines.append('</style>')

    lines.append(
        f'<rect class="bg" width="{width}" height="{height}" rx="12" '
        f'fill="#ffffff" stroke="#e1e4e8" stroke-width="1"/>'
    )

    lines.append(
        f'<text x="{pad_x}" y="30" font-family="\'Segoe UI\',system-ui,sans-serif" '
        f'font-size="13" font-weight="500" fill="#57606a" class="title">'
        f'📊 GitHub Stats · {period}</text>'
    )

    lines.append(
        f'<rect class="track" x="{pad_x}" y="{bar_y}" width="{inner_w}" height="{bar_h}" '
        f'rx="{bar_r}" fill="#eaeef2"/>'
    )

    cursor_x = pad_x
    for i, (lang, count) in enumerate(langs):
        pct = count / total
        seg_w = round(pct * inner_w)
        if seg_w < 2:
            seg_w = 2
        color = lang_color(lang, i)

        if i == 0:
            lines.append(
                f'<rect x="{cursor_x}" y="{bar_y}" width="{seg_w}" height="{bar_h}" '
                f'rx="{bar_r}" fill="{color}"/>'
                f'<rect x="{cursor_x + bar_r}" y="{bar_y}" '
                f'width="{seg_w - bar_r}" height="{bar_h}" fill="{color}"/>'
            )
        elif i == len(langs) - 1:
            sq_w = max(0, seg_w - bar_r)
            lines.append(
                f'<rect x="{cursor_x}" y="{bar_y}" width="{seg_w}" height="{bar_h}" '
                f'rx="{bar_r}" fill="{color}"/>'
            )
            if sq_w > 0:
                lines.append(
                    f'<rect x="{cursor_x}" y="{bar_y}" '
                    f'width="{sq_w}" height="{bar_h}" fill="{color}"/>'
                )
        else:
            lines.append(
                f'<rect x="{cursor_x}" y="{bar_y}" width="{seg_w}" height="{bar_h}" '
                f'fill="{color}"/>'
            )

        cursor_x += seg_w + gap

    col_w = inner_w // legend_cols
    for i, (lang, count) in enumerate(langs):
        col = i % legend_cols
        row = i // legend_cols
        x = pad_x + col * col_w
        y = legend_top + row * legend_row_h
        color = lang_color(lang, i)
        pct = count / total * 100

        lines.append(f'<circle cx="{x + 5}" cy="{y + 8}" r="4" fill="{color}"/>')
        lines.append(
            f'<text x="{x + 14}" y="{y + 13}" '
            f'font-family="\'Segoe UI\',system-ui,sans-serif" '
            f'font-size="12" fill="#24292f" class="legend-name">{lang}</text>'
        )
        lines.append(
            f'<text x="{x + col_w - 8}" y="{y + 13}" text-anchor="end" '
            f'font-family="\'Segoe UI\',system-ui,sans-serif" '
            f'font-size="12" fill="#57606a" class="legend-pct">{pct:.1f}%</text>'
        )

    lines.append(
        f'<text x="{pad_x}" y="{footer_y}" '
        f'font-family="\'Segoe UI\',system-ui,sans-serif" '
        f'font-size="11" fill="#8c959f" class="footer">'
        f'Updated {updated_at} UTC</text>'
    )

    lines.append('</svg>')
    return '\n'.join(lines)


updated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
svg_content = generate_svg(sorted_langs, total_lines, period_label, updated_at)

with open("languages.svg", "w") as f:
    f.write(svg_content)

print("✓ languages.svg generated")
print(f"\nTop languages ({period_label}):")
for lang, count in sorted_langs[:5]:
    print(f"  {lang}: {count:,} lines")
