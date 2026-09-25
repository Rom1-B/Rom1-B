# Finds every PR reviewed by USERNAME via the GitHub Search API, then fetches
# each PR's review list concurrently to count actual review submissions (not
# deduplicated per PR, unlike GitHub's contribution graph), bucketed by ISO
# week. Renders a bar chart in reviews_by_week.svg.

import argparse
from datetime import datetime, timedelta, timezone

from concurrent.futures import ThreadPoolExecutor, as_completed

from stats_common import (
    GITHUB_SEARCH_LIMIT,
    USERNAME,
    build_daily_counts,
    build_weekly_counts,
    fetch_with_retry,
    generate_svg,
)

MAX_WORKERS = 10


def collect_reviewed_prs() -> list[tuple[str, int]]:
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
    svg_content = generate_svg(weekly, total, period_label, updated_at, metric_label="PR reviews")

    with open(args.output, "w") as f:
        f.write(svg_content)

    print(f"✓ {total} reviews found")
    print(f"✓ {args.output} generated")
    busiest = max(weekly, key=lambda d: d[1], default=None)
    if busiest and busiest[1]:
        print(f"✓ Busiest week of {busiest[0]}: {busiest[1]} reviews")


if __name__ == "__main__":
    main()
