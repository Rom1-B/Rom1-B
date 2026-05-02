import requests
import matplotlib.pyplot as plt
from collections import defaultdict
import os
from datetime import datetime, timedelta

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

# Configuration
MONTHS_PERIOD = 6
DAYS_PERIOD = int(MONTHS_PERIOD * 365 / 12)  # ~183 days

print(f"Generating stats for {USERNAME}...")

headers = {"Authorization": f"token {GITHUB_TOKEN}"}

# Language extension mapping
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

# Fix: use date only, not full ISO datetime (GitHub Search API rejects datetime)
since_date = (datetime.now() - timedelta(days=DAYS_PERIOD)).strftime('%Y-%m-%d')
search_query = f"author:{USERNAME} committer-date:>{since_date}"

print(f"Searching commits from last {DAYS_PERIOD} days...")

languages = defaultdict(int)
page = 1
total_commits = 0

while True:
    search_url = f"https://api.github.com/search/commits?q={search_query}&per_page=100&page={page}"
    response = requests.get(search_url, headers=headers)

    if response.status_code != 200:
        print(f"API Error: {response.status_code}")
        break

    data = response.json()
    commits = data.get('items', [])

    if not commits:
        break

    for commit in commits:
        commit_url = commit['url']
        try:
            commit_response = requests.get(commit_url, headers=headers)
            if commit_response.status_code != 200:
                continue

            commit_data = commit_response.json()

            for file in commit_data.get('files', []):
                filename = file['filename']
                for ext, lang in LANGUAGE_MAP.items():
                    if filename.endswith(ext):
                        additions = file.get('additions', 0)
                        languages[lang] += additions
                        break

            total_commits += 1
        except Exception:
            continue

    if (page - 1) % 5 == 0:
        print(f"  [{total_commits} commits processed]")

    total_items = data.get('total_count', 0)
    if page * 100 >= total_items:
        break

    page += 1

print(f"✓ {total_commits} commits analyzed")
print(f"✓ {sum(languages.values())} lines of code added")

sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
total_lines = sum(count for _, count in sorted_langs)
sorted_langs = [(lang, count) for lang, count in sorted_langs if count > 0]

table_content = "| Language | Usage |\n|----------|-------|\n"

for lang, count in sorted_langs:
    percentage = (count / total_lines * 100) if total_lines > 0 else 0
    num_squares = max(1, round(percentage / 5))
    bar = "▌" * num_squares
    table_content += f"| {lang} | {bar} {percentage:.1f}% |\n"

stats_section = f"""---

### 📊 GitHub Stats (Last {MONTHS_PERIOD} months)

{table_content}
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*
"""

with open("README.md", "r") as f:
    readme_content = f.read()

marker_start = "### 📊 GitHub Stats"
marker_end_options = ["\n*Last updated:", "\n*Dernière mise à jour:"]

if marker_start in readme_content:
    start_idx = readme_content.find(marker_start)
    end_idx = -1
    for marker in marker_end_options:
        idx = readme_content.find(marker, start_idx)
        if idx != -1:
            end_idx = readme_content.find("\n", idx + 1) + 1
            break
    if end_idx != -1:
        readme_content = readme_content[:start_idx - 4] + stats_section + readme_content[end_idx:]
    else:
        readme_content = readme_content[:start_idx - 4] + stats_section
else:
    readme_content += "\n" + stats_section

with open("README.md", "w") as f:
    f.write(readme_content)

print("✓ README.md updated")
print(f"\nTop languages ({MONTHS_PERIOD} months):")
for lang, count in sorted_langs[:5]:
    print(f"  {lang}: {count:,} lines")
