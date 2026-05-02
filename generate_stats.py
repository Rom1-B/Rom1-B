import requests
import matplotlib.pyplot as plt
from collections import defaultdict
import os
from datetime import datetime

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = os.getenv('GITHUB_ACTOR')

print(f"Generating stats for {USERNAME}...")

headers = {"Authorization": f"token {GITHUB_TOKEN}"}

# Récupérer tous les repos
all_repos = []
page = 1
while True:
    repos_url = f"https://api.github.com/user/repos?page={page}&per_page=100&affiliation=owner,collaborator"
    response = requests.get(repos_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Erreur API: {response.status_code}")
        break
    
    repos = response.json()
    if not repos:
        break
    
    all_repos.extend(repos)
    page += 1

print(f"✓ {len(all_repos)} repos trouvés")

# Compter les langages
languages = defaultdict(int)

for i, repo in enumerate(all_repos):
    lang_url = repo["languages_url"]
    lang_response = requests.get(lang_url, headers=headers)
    lang_data = lang_response.json()
    
    for lang, bytes_count in lang_data.items():
        languages[lang] += bytes_count
    
    if (i + 1) % 10 == 0:
        print(f"  [{i+1}/{len(all_repos)}]")

print(f"✓ {len(all_repos)} repos traités")

# Trier par importance
sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)

# Générer le graphique
langs = [item[0] for item in sorted_langs[:12]]
counts = [item[1] for item in sorted_langs[:12]]

plt.figure(figsize=(12, 7))
colors = plt.cm.Set3(range(len(langs)))
plt.barh(langs, counts, color=colors)
plt.xlabel("Octets de code")
plt.title(f"Langages utilisés sur GitHub - {USERNAME}")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("languages.png", dpi=300, bbox_inches='tight')
print("✓ Graphique généré")

# Générer le contenu des stats
stats_section = f"""---

### 📊 GitHub Stats

![Languages](languages.png)

| Langage | Octets | % |
|---------|--------|-----|
"""

total_bytes = sum(count for _, count in sorted_langs)

for lang, count in sorted_langs:
    percentage = (count / total_bytes * 100)
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
print("\nTop langages:")
for lang, count in sorted_langs[:5]:
    print(f"  {lang}: {count:,} octets")
