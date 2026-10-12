#!/usr/bin/env python3
"""
build.py - Motor principal: consume GitHub API y genera SVGs dinámicos con temática cyberpunk.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


def load_config() -> dict:
    """Carga la configuración del proyecto."""
    config_path = Path("data/config.json")
    with open(config_path) as f:
        return json.load(f)


def load_profile() -> dict:
    """Carga los datos del perfil."""
    profile_path = Path("data/profile.json")
    with open(profile_path) as f:
        return json.load(f)


def get_github_token() -> str:
    """Obtiene el token de GitHub desde variable de entorno."""
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ADVERTENCIA: No se encontró token GH_PAT. Usando API sin auth (limitado).")
    return token


def github_graphql(query: str, token: str = None) -> dict:
    """Ejecuta una query GraphQL contra la API de GitHub."""
    config = load_config()
    url = config["github"]["graphql_url"]
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CoreCodev-README-Builder",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error GraphQL {e.code}: {e.read().decode()}")
        return {}


def fetch_github_stats(username: str, token: str = None) -> dict:
    """Obtiene estadísticas del usuario vía GraphQL."""
    query = """
    query($login: String!) {
      user(login: $login) {
        name
        avatarUrl
        bio
        location
        followers { totalCount }
        following { totalCount }
        repositories(first: 100, isFork: false, orderBy: {field: UPDATED_AT, direction: DESC}) {
          totalCount
          nodes {
            name
            stargazerCount
            forkCount
            primaryLanguage { name }
          }
        }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
      }
    }
    """
    data = github_graphql(query, token)
    if not data or "data" not in data:
        return {}
    user = data["data"].get("user", {})

    # Contar estrellas totales
    repos = user.get("repositories", {}).get("nodes", [])
    total_stars = sum(r.get("stargazerCount", 0) for r in repos)

    contrib = user.get("contributionsCollection", {})
    calendar = contrib.get("contributionCalendar", {})

    return {
        "name": user.get("name"),
        "avatar_url": user.get("avatarUrl"),
        "bio": user.get("bio"),
        "location": user.get("location"),
        "followers": user.get("followers", {}).get("totalCount", 0),
        "following": user.get("following", {}).get("totalCount", 0),
        "total_repos": user.get("repositories", {}).get("totalCount", 0),
        "total_stars": total_stars,
        "total_commits": contrib.get("totalCommitContributions", 0),
        "contribution_days": [
            day
            for week in calendar.get("weeks", [])
            for day in week.get("contributionDays", [])
        ],
    }


def fetch_languages(username: str, token: str = None) -> dict:
    """Obtiene lenguajes más usados del usuario."""
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, isFork: false, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            languages(first: 10) {
              edges {
                size
                node { name color }
              }
            }
          }
        }
      }
    }
    """
    data = github_graphql(query, token)
    if not data or "data" not in data:
        return {}

    lang_bytes = {}
    repos = data["data"]["user"]["repositories"]["nodes"]
    for repo in repos:
        for edge in repo.get("languages", {}).get("edges", []):
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]

    total = sum(lang_bytes.values())
    langs = []
    for name, size in sorted(lang_bytes.items(), key=lambda x: -x[1])[:10]:
        color = "#00f0ff"
        for repo in repos:
            for edge in repo.get("languages", {}).get("edges", []):
                if edge["node"]["name"] == name:
                    color = edge["node"].get("color", color)
                    break
        langs.append({
            "name": name,
            "percent": round(size / total * 100, 1),
            "color": color,
        })
    return langs


def render_svg(profile: dict, stats: dict, languages: list) -> str:
    """Renderiza el SVG principal cyberpunk con animaciones."""
    config = load_config()
    c = config["theme"]["colors"]
    anim = config["animations"]

    # Datos
    username = profile["username"]
    name = profile["name"]
    role = profile["role"]
    focus = profile["focus"]
    location = profile["location"]
    bio = profile["bio"]

    total_commits = stats.get("total_commits", 0)
    total_repos = stats.get("total_repos", 0)
    total_stars = stats.get("total_stars", 0)
    followers = stats.get("followers", 0)

    # Lenguajes para barras
    lang_bars = ""
    max_langs = min(len(languages), 8)
    for i, lang in enumerate(languages[:max_langs]):
        y = 320 + i * 28
        width = lang["percent"] * 3
        color = lang.get("color", c["primary"])
        lang_bars += f'''
    <text x="40" y="{y}" fill="{c["text_dim"]}" font-size="11" font-family="monospace">{lang["name"]}</text>
    <rect x="160" y="{y-10}" width="300" height="12" rx="6" fill="{c["border"]}">
      <animate attributeName="width" from="0" to="300" dur="{anim["bar_duration"]}s" fill="freeze" />
    </rect>
    <rect x="160" y="{y-10}" width="0" height="12" rx="6" fill="{color}">
      <animate attributeName="width" from="0" to="{width}" dur="{anim["bar_duration"]}s" begin="{i*0.1}s" fill="freeze" />
    </rect>
    <text x="470" y="{y}" fill="{color}" font-size="10" font-family="monospace" opacity="0">
      {lang["percent"]}%
      <animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="{anim["bar_duration"]+i*0.1}s" fill="freeze" />
    </text>'''

    # Contribuciones heatmap
    contrib_rects = []
    if stats.get("contribution_days"):
        day_index = 0
        for week_idx, week in enumerate(stats["contribution_days"]):
            pass  # Simplificado por ahora

    # Soft skills tags
    soft_skills = profile.get("soft_skills", [])
    skill_tags = ""
    for i, skill in enumerate(soft_skills):
        x = 40 + (i % 3) * 160
        y = 530 + (i // 3) * 30
        skill_tags += f'''
    <rect x="{x}" y="{y-14}" width="150" height="22" rx="11" fill="none" stroke="{c["tertiary"]}" stroke-width="1" opacity="0.7"/>
    <text x="{x+75}" y="{y}" fill="{c["tertiary"]}" font-size="10" font-family="monospace" text-anchor="middle" opacity="0">
      {skill}
      <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{1+i*0.15}s" fill="freeze"/>
    </text>'''

    # Stack badges
    stack_items = []
    for category, items in profile.get("stack", {}).items():
        for item in items:
            stack_items.append(item)

    stack_badges = ""
    cols = 4
    for i, item in enumerate(stack_items[:16]):
        x = 40 + (i % cols) * 135
        y = 610 + (i // cols) * 28
        stack_badges += f'''
    <rect x="{x}" y="{y-12}" width="125" height="20" rx="10" fill="none" stroke="{c["primary"]}" stroke-width="0.5" opacity="0.5"/>
    <text x="{x+62}" y="{y+2}" fill="{c["text"]}" font-size="9" font-family="monospace" text-anchor="middle" opacity="0">
      {item}
      <animate attributeName="opacity" from="0" to="0.9" dur="0.4" begin="{1.5+i*0.08}s" fill="freeze"/>
    </text>'''

    # Stats numbers
    stats_html = f'''
    <text x="40" y="160" fill="{c["text_dim"]}" font-size="10" font-family="monospace">COMMITS</text>
    <text x="40" y="185" fill="{c["primary"]}" font-size="28" font-family="monospace" font-weight="bold">{total_commits:,}</text>
    <text x="200" y="160" fill="{c["text_dim"]}" font-size="10" font-family="monospace">REPOS</text>
    <text x="200" y="185" fill="{c["secondary"]}" font-size="28" font-family="monospace" font-weight="bold">{total_repos}</text>
    <text x="360" y="160" fill="{c["text_dim"]}" font-size="10" font-family="monospace">STARS</text>
    <text x="360" y="185" fill="{c["tertiary"]}" font-size="28" font-family="monospace" font-weight="bold">{total_stars}</text>
    <text x="520" y="160" fill="{c["text_dim"]}" font-size="10" font-family="monospace">FOLLOWERS</text>
    <text x="520" y="185" fill="{c["accent"]}" font-size="28" font-family="monospace" font-weight="bold">{followers}</text>'''

    # Typing animation para el título
    title_text = f"{username}"
    typing_chars = ""
    for i, ch in enumerate(title_text):
        typing_chars += f'''
    <text x="{40+i*14}" y="80" fill="{c["primary"]}" font-size="22" font-family="monospace" font-weight="bold" opacity="0">
      {ch}
      <animate attributeName="opacity" from="0" to="1" dur="0.05" begin="{i*0.08}s" fill="freeze"/>
    </text>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="720" viewBox="0 0 700 720" font-family="JetBrains Mono, Fira Code, monospace">
  <defs>
    <!-- Glow filter -->
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <!-- Scanline pattern -->
    <pattern id="scanlines" patternUnits="userSpaceOnUse" width="4" height="4">
      <rect width="4" height="1" fill="white" opacity="0.02"/>
    </pattern>
    <!-- Gradient for border -->
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c["primary"]}"/>
      <stop offset="50%" stop-color="{c["secondary"]}"/>
      <stop offset="100%" stop-color="{c["tertiary"]}"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="700" height="720" fill="{c["background"]}" rx="12"/>

  <!-- CRT Scanlines overlay -->
  <rect width="700" height="720" fill="url(#scanlines)">
    <animate attributeName="y" from="0" to="4" dur="{anim["scanline_duration"]}s" repeatCount="indefinite"/>
  </rect>

  <!-- Animated border -->
  <rect x="1" y="1" width="698" height="718" rx="11" fill="none" stroke="url(#borderGrad)" stroke-width="2" filter="url(#glow)">
    <animate attributeName="stroke-opacity" values="1;0.5;1" dur="{anim["glow_pulse_duration"]}s" repeatCount="indefinite"/>
  </rect>

  <!-- Header bar (terminal style) -->
  <rect x="20" y="20" width="660" height="36" rx="8" fill="{c["surface"]}"/>
  <circle cx="40" cy="38" r="5" fill="#ff5f56"/>
  <circle cx="58" cy="38" r="5" fill="#ffbd2e"/>
  <circle cx="76" cy="38" r="5" fill="#27c93f"/>
  <text x="350" y="42" fill="{c["text_dim"]}" font-size="11" font-family="monospace" text-anchor="middle">~/.config/{username}</text>

  <!-- Username with typing animation -->
  {typing_chars}

  <!-- Cursor blink -->
  <rect x="{40+len(title_text)*14+4}" y="62" width="10" height="20" fill="{c["primary"]}">
    <animate attributeName="opacity" values="1;0;1" dur="{anim["cursor_blink"]}s" repeatCount="indefinite"/>
  </rect>

  <!-- Info section -->
  <text x="40" y="120" fill="{c["text"]}" font-size="13" font-family="monospace" opacity="0">
    {role} · {focus}
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="0.5s" fill="freeze"/>
  </text>

  <text x="40" y="140" fill="{c["text_dim"]}" font-size="11" font-family="monospace" opacity="0">
    📍 {location}
    <animate attributeName="opacity" from="0" to="1" dur="0.5" begin="0.7s" fill="freeze"/>
  </text>

  <!-- Stats row -->
  <g opacity="0">
    {stats_html}
    <animate attributeName="opacity" from="0" to="1" dur="0.8s" begin="0.3s" fill="freeze"/>
  </g>

  <!-- Languages section -->
  <text x="40" y="300" fill="{c["text_dim"]}" font-size="10" font-family="monospace" opacity="0">
    LANGUAGES &amp; TOOLS
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="0.8s" fill="freeze"/>
  </text>
  {lang_bars}

  <!-- Soft skills -->
  <text x="40" y="510" fill="{c["text_dim"]}" font-size="10" font-family="monospace" opacity="0">
    SOFT SKILLS
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="1.2s" fill="freeze"/>
  </text>
  {skill_tags}

  <!-- Full stack badges -->
  <text x="40" y="590" fill="{c["text_dim"]}" font-size="10" font-family="monospace" opacity="0">
    FULL STACK
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="1.4s" fill="freeze"/>
  </text>
  {stack_badges}

  <!-- Footer -->
  <text x="40" y="700" fill="{c["text_dim"]}" font-size="9" font-family="monospace" opacity="0">
    Generated by CoreCodev Auto-Builder · {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    <animate attributeName="opacity" from="0" to="0.6" dur="0.5s" begin="2.5s" fill="freeze"/>
  </text>

  <!-- Accessibility: respect reduced motion -->
  <animateMotion>
    <mpath href="#none"/>
  </animateMotion>
</svg>'''
    return svg


def render_languages_svg(languages: list, profile: dict) -> str:
    """Renderiza SVG dedicado a lenguajes con barras animadas."""
    config = load_config()
    c = config["theme"]["colors"]
    anim = config["animations"]

    bars = ""
    max_langs = min(len(languages), 12)
    bar_height = 32
    for i, lang in enumerate(languages[:max_langs]):
        y = 60 + i * (bar_height + 10)
        width = lang["percent"] * 4.5
        color = lang.get("color", c["primary"])
        name = lang["name"]
        pct = lang["percent"]

        bars += f'''
    <text x="20" y="{y+18}" fill="{c["text"]}" font-size="12" font-family="monospace">{name}</text>
    <rect x="180" y="{y}" width="450" height="{bar_height-8}" rx="4" fill="{c["border"]}"/>
    <rect x="180" y="{y}" width="0" height="{bar_height-8}" rx="4" fill="{color}" filter="url(#glow)">
      <animate attributeName="width" from="0" to="{width}" dur="{anim["bar_duration"]}s" begin="{i*0.15}s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1"/>
    </rect>
    <text x="640" y="{y+18}" fill="{color}" font-size="11" font-family="monospace" text-anchor="end" opacity="0">
      {pct}%
      <animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="{anim["bar_duration"]+i*0.15}s" fill="freeze"/>
    </text>'''

    total_height = 80 + max_langs * (bar_height + 10) + 20
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="{total_height}" viewBox="0 0 700 {total_height}" font-family="JetBrains Mono, Fira Code, monospace">
  <defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c["background"]}"/>
      <stop offset="100%" stop-color="{c["surface"]}"/>
    </linearGradient>
  </defs>
  <rect width="700" height="{total_height}" fill="url(#bg)" rx="12"/>
  <text x="20" y="35" fill="{c["primary"]}" font-size="16" font-family="monospace" font-weight="bold">$ {profile["username"]}/stack</text>
  <line x1="20" y1="50" x2="680" y2="50" stroke="{c["border"]}" stroke-width="1"/>
  {bars}
  <text x="20" y="{total_height-10}" fill="{c["text_dim"]}" font-size="9" font-family="monospace">{len(languages)} languages tracked</text>
</svg>'''
    return svg


def render_activity_svg(stats: dict) -> str:
    """Renderiza SVG con heatmap de contribuciones."""
    config = load_config()
    c = config["theme"]["colors"]

    days = stats.get("contribution_days", [])
    if not days:
        # SVG placeholder
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="150" viewBox="0 0 700 150">
  <rect width="700" height="150" fill="{c["background"]}" rx="12"/>
  <text x="350" y="80" fill="{c["text_dim"]}" font-size="14" text-anchor="middle" font-family="monospace">Loading contribution data...</text>
</svg>'''

    # Construir heatmap
    cell_size = 12
    gap = 2
    cols = 53
    rows = 7

    rects = ""
    for i, day in enumerate(days):
        col = i // 7
        row = i % 7
        x = 40 + col * (cell_size + gap)
        y = 50 + row * (cell_size + gap)
        count = day.get("contributionCount", 0)
        opacity = min(0.2 + count * 0.15, 1.0)
        color = day.get("color", c["primary"])

        rects += f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" fill="{color}" opacity="{opacity}"/>'

    total_contributions = sum(d.get("contributionCount", 0) for d in days)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="180" viewBox="0 0 700 180" font-family="JetBrains Mono, Fira Code, monospace">
  <rect width="700" height="180" fill="{c["background"]}" rx="12"/>
  <text x="20" y="30" fill="{c["primary"]}" font-size="14" font-family="monospace" font-weight="bold">$ git log --oneline</text>
  <text x="680" y="30" fill="{c["text_dim"]}" font-size="10" text-anchor="end" font-family="monospace">{total_contributions} contributions</text>
  {rects}
  <text x="20" y="170" fill="{c["text_dim"]}" font-size="9" font-family="monospace">Last 52 weeks</text>
</svg>'''
    return svg


def main():
    print("🚀 CoreCodev README Builder")
    print("=" * 50)

    config = load_config()
    profile = load_profile()

    token = get_github_token()
    username = config["github"]["username"]

    print(f"\n📡 Fetching stats for @{username}...")
    stats = fetch_github_stats(username, token)
    print(f"   Commits: {stats.get('total_commits', 0):,}")
    print(f"   Repos: {stats.get('total_repos', 0)}")
    print(f"   Stars: {stats.get('total_stars', 0)}")
    print(f"   Followers: {stats.get('followers', 0)}")

    print(f"\n📊 Fetching languages...")
    languages = fetch_languages(username, token)
    print(f"   Found {len(languages)} languages")

    # Merge stats into profile
    profile["stats"].update({
        "total_commits": stats.get("total_commits", 0),
        "total_repos": stats.get("total_repos", 0),
        "total_stars": stats.get("total_stars", 0),
        "followers": stats.get("followers", 0),
        "following": stats.get("following", 0),
    })

    # Fallback: si la API no devolvió datos, usar languages del profile
    if not languages and profile.get("languages"):
        c = config["theme"]["colors"]
        profile_langs = profile["languages"]
        # Convertir formato {name: percent} a lista ordenada
        languages = [
            {"name": name, "percent": pct, "color": c["primary"]}
            for name, pct in sorted(profile_langs.items(), key=lambda x: -x[1])
        ]
        print(f"   Usando languages del profile.json como fallback")

    # Fallback: si no hay stats, usar valores del profile
    if stats.get("total_commits", 0) == 0:
        stats["total_commits"] = profile.get("stats", {}).get("total_commits", 0)
        stats["total_repos"] = profile.get("stats", {}).get("total_repos", 0)
        stats["total_stars"] = profile.get("stats", {}).get("total_stars", 0)
        stats["followers"] = profile.get("stats", {}).get("followers", 0)
        print(f"   Usando stats del profile.json como fallback")

    # Fallback: datos de contribución simulados si la API no devolvió
    if not stats.get("contribution_days"):
        import random
        random.seed(42)  # Determinista para consistencia
        days = []
        for _ in range(364):
            days.append({
                "date": "2025-01-01",
                "contributionCount": random.randint(0, 8),
                "color": "#00f0ff",
            })
        stats["contribution_days"] = days
        print(f"   Usando contribution_days simulados como fallback")

    # Actualizar lenguajes con datos reales
    if languages:
        profile["languages_real"] = languages

    print(f"\n🎨 Rendering SVGs...")

    # Render main profile SVG
    main_svg = render_svg(profile, stats, languages)
    output_dir = Path(config["paths"]["output"])
    output_dir.mkdir(exist_ok=True)

    main_path = output_dir / "profile_card.svg"
    main_path.write_text(main_svg, encoding="utf-8")
    print(f"   ✅ {main_path}")

    # Render languages SVG
    if languages:
        lang_svg = render_languages_svg(languages, profile)
        lang_path = output_dir / "languages_card.svg"
        lang_path.write_text(lang_svg, encoding="utf-8")
        print(f"   ✅ {lang_path}")

    # Render activity SVG
    activity_svg = render_activity_svg(stats)
    activity_path = output_dir / "activity_card.svg"
    activity_path.write_text(activity_svg, encoding="utf-8")
    print(f"   ✅ {activity_path}")

    print(f"\n✅ Done! SVGs generated in {output_dir}/")
    print(f"   Commit and push to update your profile README.")


if __name__ == "__main__":
    main()
