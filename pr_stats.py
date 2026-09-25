# Finds every PR authored by USERNAME via the GitHub Search API, bucketed by
# ISO week using each PR's created_at date (single search call, no per-PR
# fetch needed). Renders a bar chart in prs_by_week.svg.

import argparse
from datetime import datetime, timedelta, timezone

from stats_common import (
    GITHUB_SEARCH_LIMIT,
    USERNAME,
    build_daily_counts,
    build_weekly_counts,
    fetch_with_retry,
    generate_svg,
)


def collect_created_prs() -> list[str]:
    """Returns created_at dates (YYYY-MM-DD) of PRs authored by USERNAME."""
    dates: list[str] = []
    page = 1
    while True:
        search_url = (
            f"https://api.github.com/search/issues"
            f"?q=is:pr+author:{USERNAME}&sort=created&order=desc&per_page=100&page={page}"
        )
        data = fetch_with_retry(search_url)
        if not data:
            break

        items = data.get('items', [])
        if not items:
            break

        dates.extend(item['created_at'][:10] for item in items)

        total_items = data.get('total_count', 0)
        if len(dates) >= GITHUB_SEARCH_LIMIT or page * 100 >= total_items:
            if len(dates) >= GITHUB_SEARCH_LIMIT:
                print(f"  [GitHub Search API limit reached at {GITHUB_SEARCH_LIMIT} PRs]")
            break
        page += 1

    return dates[:GITHUB_SEARCH_LIMIT]


def main() -> None:
    parser = argparse.ArgumentParser(description="Chart PRs created per week from GitHub.")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD), default: 1 year ago")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD), default: today")
    parser.add_argument("--output", default="prs_by_week.svg", help="Output SVG path")
    args = parser.parse_args()

    to_dt = datetime.fromisoformat(args.to_date) if args.to_date else datetime.now(timezone.utc).replace(tzinfo=None)
    from_dt = (
        datetime.fromisoformat(args.from_date)
        if args.from_date
        else to_dt - timedelta(days=365)
    )

    print(f"Fetching PRs created by {USERNAME} from {from_dt.date()} to {to_dt.date()}...")
    dates = collect_created_prs()
    daily = build_daily_counts(dates, from_dt, to_dt)
    weekly = build_weekly_counts(daily)
    total = sum(count for _, count in daily)

    period_label = f"{from_dt.date()} to {to_dt.date()}"
    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    svg_content = generate_svg(weekly, total, period_label, updated_at, metric_label="PRs created")

    with open(args.output, "w") as f:
        f.write(svg_content)

    print(f"✓ {total} PRs found")
    print(f"✓ {args.output} generated")
    busiest = max(weekly, key=lambda d: d[1], default=None)
    if busiest and busiest[1]:
        print(f"✓ Busiest week of {busiest[0]}: {busiest[1]} PRs")


if __name__ == "__main__":
    main()
