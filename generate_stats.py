import requests
import matplotlib.pyplot as plt
from collections import defaultdict
import os
from datetime import datetime, timedelta

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

# Configuration
DAYS_PERIOD = 180  # Change this to adjust the period (e.g., 30, 90, 180, 365)

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

# Fetch commits from last N days
since_date = (datetime.now() - timedelta(days=DAYS_PERIOD)).isoformat()
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
        commit_response = requests.get(commit_url, headers=headers)
        commit_data = commit_response.json()
        
        # Browse commit files
        for file in commit_data.get('files', []):
            filename = file['filename']
            # Detect language by extension
            for ext, lang in LANGUAGE_MAP.items():
                if filename.endswith(ext):
                    # Count additions
                    additions = file.get('additions', 0)
                    languages[lang] += additions
                    break
        
        total_commits += 1
    
    if (page - 1) % 5 == 0:
        print(f"  [{total_commits} commits processed]")
    
    total_items = data.get('total_count', 0)
    if page * 100 >= total_items or total_items > 1000:
        break
    
    page += 1

print(f"✓ {total_commits} commits analyzed")
print(f"✓ {sum(languages.values())} lines of code added")

# Filter out 0% languages and sort
sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
total_lines = sum(count for _, count in sorted_langs)

# Keep only languages with > 0%
sorted_langs = [(lang, count) for lang, count in sorted_langs if count > 0]

# Generate markdown table with blue squares
table_content = "| Language | Usage |\n|----------|-------|\n"

for lang, count in sorted_langs:
    percentage = (count / total_lines * 100) if total_lines > 0 else 0
    num_squares = max(1, round(percentage / 5))
    bar = "▌" * num_squares
    table_content += f"| {lang} | {bar} {percentage:.1f}% |\n"

# Generate stats section
stats_section = f"""---

### 📊 GitHub Stats (Last {DAYS_PERIOD} days)

{table_content}
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*
"""

# Lire le README existant
with open("README.md", "r") as f:
    readme_content = f.read()

# Find existing stats section marker
marker_start = "### 📊 GitHub Stats"
marker_end = "\n*Last updated:"

if marker_start in readme_content:
    # Replace existing stats section
    start_idx = readme_content.find(marker_start)
    end_idx = readme_content.find(marker_end, start_idx)
    if end_idx != -1:
        end_idx = readme_content.find("\n", end_idx) + 1
        readme_content = readme_content[:start_idx-4] + stats_section + readme_content[end_idx:]
else:
    # Add stats section at the end
    readme_content += "\n" + stats_section

with open("README.md", "w") as f:
    f.write(readme_content)

print("✓ README.md updated")
print(f"\nTop languages ({DAYS_PERIOD} days):")
for lang, count in sorted_langs[:5]:
    print(f"  {lang}: {count:,} lines")
