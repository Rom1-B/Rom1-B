import requests
import matplotlib.pyplot as plt
from collections import defaultdict
import os
from datetime import datetime, timedelta

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

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

# Fetch commits from last 180 days
since_date = (datetime.now() - timedelta(days=180)).isoformat()
search_query = f"author:{USERNAME} committer-date:>{since_date}"

print(f"Searching commits since {since_date[:10]}...")

languages = defaultdict(int)
page = 1
total_commits = 0

while True:
    search_url = f"https://api.github.com/search/commits?q={search_query}&per_page=100&page={page}"
    response = requests.get(search_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Erreur API: {response.status_code}")
        break
    
    data = response.json()
    commits = data.get('items', [])
    
    if not commits:
        break
    
    for commit in commits:
        commit_url = commit['url']
        commit_response = requests.get(commit_url, headers=headers)
        commit_data = commit_response.json()
        
        # Parcourir les fichiers du commit
        for file in commit_data.get('files', []):
            filename = file['filename']
            # Déterminer l'extension
            for ext, lang in LANGUAGE_MAP.items():
                if filename.endswith(ext):
                    # Compter les additions
                    additions = file.get('additions', 0)
                    languages[lang] += additions
                    break
        
        total_commits += 1
    
    if (page - 1) % 5 == 0:
        print(f"  [{total_commits} commits traités]")
    
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

# Generate HTML list with progress bars
html_content = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 500px; margin: 20px 0;">
"""

colors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
    '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A9DFBF'
]

for idx, (lang, count) in enumerate(sorted_langs):
    percentage = (count / total_lines * 100) if total_lines > 0 else 0
    color = colors[idx % len(colors)]
    
    html_content += f"""  <div style="margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
      <span style="font-weight: 500; color: #333;">{lang}</span>
      <span style="color: #666; font-size: 14px;">{percentage:.1f}%</span>
    </div>
    <div style="width: 100%; height: 8px; background: #eee; border-radius: 4px; overflow: hidden;">
      <div style="width: {percentage}%; height: 100%; background: {color}; transition: width 0.3s ease;"></div>
    </div>
  </div>
"""

html_content += """</div>"""

# Générer le contenu des stats
stats_section = f"""---

### 📊 GitHub Stats (Last 6 months)

{html_content}

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*
"""

# Lire le README existant
with open("README.md", "r") as f:
    readme_content = f.read()

# Chercher le marqueur ou la section existante
marker_start = "### 📊 GitHub Stats"
marker_end = "\n*Dernière mise à jour:"

if marker_start in readme_content:
    # Supprimer l'ancienne section stats
    start_idx = readme_content.find(marker_start)
    end_idx = readme_content.find(marker_end, start_idx)
    if end_idx != -1:
        end_idx = readme_content.find("\n", end_idx) + 1
        readme_content = readme_content[:start_idx-4] + stats_section + readme_content[end_idx:]
else:
    # Ajouter la section stats à la fin
    readme_content += "\n" + stats_section

with open("README.md", "w") as f:
    f.write(readme_content)

print("✓ README.md updated")
print("\nTop languages (6 months):")
for lang, count in sorted_langs[:5]:
    print(f"  {lang}: {count:,} lines")
