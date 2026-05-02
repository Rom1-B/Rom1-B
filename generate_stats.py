import requests
import matplotlib.pyplot as plt
from collections import defaultdict
import os
from datetime import datetime, timedelta

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

print(f"Generating stats for {USERNAME}...")

headers = {"Authorization": f"token {GITHUB_TOKEN}"}

# Mapping extension → langage
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

# Récupérer les commits des 90 derniers jours
since_date = (datetime.now() - timedelta(days=90)).isoformat()
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

print(f"✓ {total_commits} commits analysés")
print(f"✓ {sum(languages.values())} lignes de code ajoutées")

# Trier par importance
sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)

# Générer le graphique (top 10)
langs = [item[0] for item in sorted_langs[:10]]
counts = [item[1] for item in sorted_langs[:10]]

plt.figure(figsize=(12, 7))
colors = plt.cm.Set3(range(len(langs)))
plt.barh(langs, counts, color=colors)
plt.xlabel("Lignes de code ajoutées")
plt.title(f"Langages - 90 derniers jours - {USERNAME}")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("languages.png", dpi=300, bbox_inches='tight')
print("✓ Graphique généré")

# Générer le contenu des stats
stats_section = f"""---

### 📊 GitHub Stats (90 jours)

![Languages](languages.png)

| Langage | Lignes | % |
|---------|--------|-----|
"""

total_lines = sum(count for _, count in sorted_langs)

for lang, count in sorted_langs:
    percentage = (count / total_lines * 100) if total_lines > 0 else 0
    stats_section += f"| {lang} | {count:,} | {percentage:.1f}% |\n"

stats_section += f"""
*Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*
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

print("✓ README.md mis à jour")
print("\nTop langages (90 jours):")
for lang, count in sorted_langs[:5]:
    print(f"  {lang}: {count:,} lignes")
