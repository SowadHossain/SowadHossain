"""
GitHub Stats SVG Generator
Fetches GitHub stats via GraphQL API and generates beautiful SVG cards.
Run by GitHub Actions daily or manually.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# --- Configuration ---
USERNAME = os.environ.get("GITHUB_USERNAME", "SowadHossain")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# Theme colors
BG = "#0D1117"
BG_CARD = "#161B22"
BORDER = "rgba(139,92,246,0.3)"
PRIMARY = "#7C3AED"   # Purple
SECONDARY = "#22D3EE"  # Cyan
TEXT = "#C9D1D9"
TEXT_DIM = "#8B949E"
WHITE = "#FFFFFF"
ACCENT_GRADIENT = f"url(#accentGrad)"

# Contribution heatmap colors (purple scale)
HEAT_COLORS = ["#161B22", "#2D1B69", "#5B21B6", "#7C3AED", "#A78BFA"]


def graphql_query(query, variables=None):
    """Execute a GitHub GraphQL query."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "GitHubStatsGenerator/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"GraphQL Error: {e.code} - {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def fetch_all_stats():
    """Fetch all GitHub stats in a single GraphQL query."""
    now = datetime.now(timezone.utc)
    year_ago = (now - timedelta(days=365)).isoformat()

    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $username) {
        name
        repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: STARGAZERS, direction: DESC}) {
          totalCount
          nodes {
            stargazerCount
            forkCount
            primaryLanguage { name color }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
        followers { totalCount }
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                weekday
              }
            }
          }
        }
      }
    }
    """
    result = graphql_query(query, {
        "username": USERNAME,
        "from": year_ago,
        "to": now.isoformat(),
    })

    if "errors" in result:
        print(f"API Errors: {result['errors']}", file=sys.stderr)
        sys.exit(1)

    return result["data"]["user"]


def compute_stats(data):
    """Process raw API data into structured stats."""
    repos = data["repositories"]["nodes"]
    contrib = data["contributionsCollection"]
    calendar = contrib["contributionCalendar"]

    # Basic stats
    total_stars = sum(r["stargazerCount"] for r in repos)
    total_forks = sum(r["forkCount"] for r in repos)

    # Language stats
    lang_sizes = defaultdict(lambda: {"size": 0, "color": "#8B949E"})
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_sizes[name]["size"] += edge["size"]
            lang_sizes[name]["color"] = edge["node"]["color"] or "#8B949E"

    sorted_langs = sorted(lang_sizes.items(), key=lambda x: x[1]["size"], reverse=True)[:8]
    total_size = sum(v["size"] for _, v in sorted_langs) or 1
    languages = [
        {"name": name, "color": info["color"], "percent": round(info["size"] / total_size * 100, 1)}
        for name, info in sorted_langs
    ]

    # Streak calculation
    all_days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            all_days.append(day)

    all_days.sort(key=lambda d: d["date"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    current_streak = 0
    longest_streak = 0
    streak = 0
    streak_start = None
    current_start = None
    longest_start = None
    longest_end = None

    for day in all_days:
        if day["contributionCount"] > 0:
            streak += 1
            if streak == 1:
                streak_start = day["date"]
            if streak > longest_streak:
                longest_streak = streak
                longest_start = streak_start
                longest_end = day["date"]
        else:
            streak = 0
            streak_start = None

    # Compute current streak from end
    current_streak = 0
    current_start = None
    for day in reversed(all_days):
        if day["date"] > today:
            continue
        if day["contributionCount"] > 0:
            current_streak += 1
            current_start = day["date"]
        else:
            break

    return {
        "name": data["name"] or USERNAME,
        "total_repos": data["repositories"]["totalCount"],
        "total_stars": total_stars,
        "total_forks": total_forks,
        "followers": data["followers"]["totalCount"],
        "total_commits": contrib["totalCommitContributions"],
        "total_prs": contrib["totalPullRequestContributions"],
        "total_issues": contrib["totalIssueContributions"],
        "total_reviews": contrib["totalPullRequestReviewContributions"],
        "total_contributions": calendar["totalContributions"],
        "languages": languages,
        "weeks": calendar["weeks"],
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "current_start": current_start,
        "longest_start": longest_start,
        "longest_end": longest_end,
    }


# ─── SVG Generators ─────────────────────────────────────────────

def _gradient_defs():
    return f"""
    <defs>
      <linearGradient id="accentGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="{PRIMARY}"/>
        <stop offset="100%" stop-color="{SECONDARY}"/>
      </linearGradient>
      <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="{BG}"/>
        <stop offset="100%" stop-color="{BG_CARD}"/>
      </linearGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="3" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>"""


def _card_bg(width, height):
    return f"""
    <rect width="{width}" height="{height}" rx="12" fill="url(#bgGrad)" stroke="{BORDER}" stroke-width="1"/>
    <rect width="{width}" height="{height}" rx="12" fill="none" stroke="url(#accentGrad)" stroke-width="0.5" opacity="0.4"/>"""


def _animate_fade(delay=0):
    return f'opacity="0" style="animation: fadeIn 0.6s ease {delay}s forwards"'


def generate_stats_card(stats):
    """Generate the main GitHub stats card SVG."""
    items = [
        ("⭐", "Total Stars", f"{stats['total_stars']:,}"),
        ("🔥", "Total Commits", f"{stats['total_commits']:,}"),
        ("🔀", "Pull Requests", f"{stats['total_prs']:,}"),
        ("📋", "Issues", f"{stats['total_issues']:,}"),
        ("📦", "Repositories", f"{stats['total_repos']:,}"),
        ("👥", "Followers", f"{stats['followers']:,}"),
    ]

    rows = ""
    for i, (icon, label, value) in enumerate(items):
        y = 70 + i * 38
        delay = 0.1 + i * 0.1
        rows += f"""
        <g {_animate_fade(delay)}>
          <text x="30" y="{y}" font-size="15" fill="{TEXT}">{icon} {label}</text>
          <text x="420" y="{y}" font-size="16" font-weight="600" fill="{SECONDARY}" text-anchor="end">{value}</text>
          <line x1="30" y1="{y + 12}" x2="420" y2="{y + 12}" stroke="{TEXT_DIM}" stroke-width="0.3" opacity="0.3"/>
        </g>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="450" height="315" viewBox="0 0 450 315">
    <style>
      @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif; }}
    </style>
    {_gradient_defs()}
    {_card_bg(450, 315)}
    <g {_animate_fade(0)}>
      <text x="30" y="38" font-size="18" font-weight="700" fill="{WHITE}">{stats['name']}'s GitHub Stats</text>
      <rect x="30" y="48" width="60" height="3" rx="1.5" fill="url(#accentGrad)"/>
    </g>
    {rows}
    </svg>"""
    return svg


def generate_streak_card(stats):
    """Generate the streak stats card SVG."""
    current = stats["current_streak"]
    longest = stats["longest_streak"]
    total = stats["total_contributions"]

    def _format_date(d):
        if not d:
            return ""
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            return dt.strftime("%b %d")
        except (ValueError, TypeError):
            return str(d)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="450" height="200" viewBox="0 0 450 200">
    <style>
      @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      @keyframes pulse {{ 0%, 100% {{ transform: scale(1); }} 50% {{ transform: scale(1.05); }} }}
      @keyframes ringDraw {{ from {{ stroke-dashoffset: 251; }} to {{ stroke-dashoffset: 0; }} }}
      text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif; }}
    </style>
    {_gradient_defs()}
    {_card_bg(450, 200)}

    <!-- Total Contributions -->
    <g {_animate_fade(0.1)}>
      <text x="83" y="75" font-size="28" font-weight="700" fill="{SECONDARY}" text-anchor="middle">{total:,}</text>
      <text x="83" y="100" font-size="11" font-weight="500" fill="{TEXT_DIM}" text-anchor="middle">Total Contributions</text>
      <text x="83" y="118" font-size="10" fill="{TEXT_DIM}" text-anchor="middle">Past Year</text>
    </g>

    <!-- Divider -->
    <line x1="165" y1="40" x2="165" y2="165" stroke="{TEXT_DIM}" stroke-width="0.5" opacity="0.3"/>

    <!-- Current Streak -->
    <g {_animate_fade(0.3)}>
      <circle cx="262" cy="80" r="40" fill="none" stroke="{PRIMARY}" stroke-width="3" opacity="0.2"/>
      <circle cx="262" cy="80" r="40" fill="none" stroke="{SECONDARY}" stroke-width="3"
        stroke-dasharray="251" stroke-dashoffset="251" stroke-linecap="round"
        style="animation: ringDraw 1.5s ease 0.5s forwards"/>
      <text x="262" y="76" font-size="28" font-weight="700" fill="{WHITE}" text-anchor="middle"
        dominant-baseline="middle" style="animation: pulse 2s ease-in-out infinite">{current}</text>
      <text x="262" y="135" font-size="12" font-weight="600" fill="{PRIMARY}" text-anchor="middle">Current Streak</text>
      <text x="262" y="152" font-size="10" fill="{TEXT_DIM}" text-anchor="middle">{_format_date(stats['current_start'])} - Present</text>
    </g>

    <!-- Divider -->
    <line x1="345" y1="40" x2="345" y2="165" stroke="{TEXT_DIM}" stroke-width="0.5" opacity="0.3"/>

    <!-- Longest Streak -->
    <g {_animate_fade(0.5)}>
      <text x="397" y="75" font-size="28" font-weight="700" fill="{PRIMARY}" text-anchor="middle">{longest}</text>
      <text x="397" y="100" font-size="11" font-weight="500" fill="{TEXT_DIM}" text-anchor="middle">Longest Streak</text>
      <text x="397" y="118" font-size="10" fill="{TEXT_DIM}" text-anchor="middle">{_format_date(stats['longest_start'])} - {_format_date(stats['longest_end'])}</text>
    </g>

    <!-- Fire icon -->
    <text x="262" y="25" font-size="18" text-anchor="middle" filter="url(#glow)">🔥</text>
    </svg>"""
    return svg


def generate_languages_card(stats):
    """Generate the top languages card SVG."""
    langs = stats["languages"]
    if not langs:
        langs = [{"name": "No data", "color": TEXT_DIM, "percent": 100}]

    # Progress bar
    bar_width = 390
    bar_y = 55
    bar_segments = ""
    x_offset = 30
    for lang in langs:
        w = max(bar_width * lang["percent"] / 100, 2)
        bar_segments += f'<rect x="{x_offset}" y="{bar_y}" width="{w}" height="8" rx="4" fill="{lang["color"]}"/>'
        x_offset += w

    # Legend items
    legend = ""
    cols = 2
    for i, lang in enumerate(langs):
        col = i % cols
        row = i // cols
        x = 30 + col * 200
        y = 85 + row * 28
        legend += f"""
        <g {_animate_fade(0.2 + i * 0.08)}>
          <circle cx="{x + 6}" cy="{y - 4}" r="5" fill="{lang['color']}"/>
          <text x="{x + 18}" y="{y}" font-size="12" fill="{TEXT}">{lang['name']}</text>
          <text x="{x + 170}" y="{y}" font-size="12" fill="{TEXT_DIM}" text-anchor="end">{lang['percent']}%</text>
        </g>"""

    height = 95 + ((len(langs) + 1) // 2) * 28

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="450" height="{height}" viewBox="0 0 450 {height}">
    <style>
      @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      @keyframes barGrow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
      text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif; }}
    </style>
    {_gradient_defs()}
    {_card_bg(450, height)}

    <g {_animate_fade(0)}>
      <text x="30" y="38" font-size="18" font-weight="700" fill="{WHITE}">Most Used Languages</text>
      <rect x="30" y="48" width="60" height="3" rx="1.5" fill="url(#accentGrad)"/>
    </g>

    <!-- Progress Bar -->
    <g {_animate_fade(0.15)}>
      <rect x="30" y="{bar_y}" width="{bar_width}" height="8" rx="4" fill="{BG}"/>
      <clipPath id="barClip"><rect x="30" y="{bar_y}" width="{bar_width}" height="8" rx="4"/></clipPath>
      <g clip-path="url(#barClip)" style="transform-origin: 30px center; animation: barGrow 1s ease 0.3s both">
        {bar_segments}
      </g>
    </g>

    <!-- Legend -->
    {legend}
    </svg>"""
    return svg


def generate_contribution_graph(stats):
    """Generate the contribution heatmap SVG."""
    weeks = stats["weeks"]
    cell_size = 12
    gap = 3
    margin_left = 40
    margin_top = 45
    total_weeks = len(weeks)

    width = margin_left + total_weeks * (cell_size + gap) + 20
    height = margin_top + 7 * (cell_size + gap) + 40

    # Day labels
    day_labels = ""
    for i, label in enumerate(["Mon", "", "Wed", "", "Fri", "", ""]):
        if label:
            y = margin_top + i * (cell_size + gap) + cell_size - 2
            day_labels += f'<text x="{margin_left - 8}" y="{y}" font-size="10" fill="{TEXT_DIM}" text-anchor="end">{label}</text>'

    # Month labels
    month_labels = ""
    last_month = -1
    for wi, week in enumerate(weeks):
        if week["contributionDays"]:
            d = datetime.strptime(week["contributionDays"][0]["date"], "%Y-%m-%d")
            if d.month != last_month:
                last_month = d.month
                x = margin_left + wi * (cell_size + gap)
                month_labels += f'<text x="{x}" y="{margin_top - 10}" font-size="10" fill="{TEXT_DIM}">{d.strftime("%b")}</text>'

    # Heatmap cells
    cells = ""
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            wd = day["weekday"]
            count = day["contributionCount"]
            if count == 0:
                color_idx = 0
            elif count <= 3:
                color_idx = 1
            elif count <= 6:
                color_idx = 2
            elif count <= 9:
                color_idx = 3
            else:
                color_idx = 4

            x = margin_left + wi * (cell_size + gap)
            y = margin_top + wd * (cell_size + gap)
            delay = 0.005 * wi
            cells += f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" fill="{HEAT_COLORS[color_idx]}" opacity="0" style="animation: fadeIn 0.3s ease {delay:.2f}s forwards"><title>{day["date"]}: {count} contributions</title></rect>'

    # Legend
    legend_x = width - 160
    legend_y = height - 22
    legend = f'<text x="{legend_x - 5}" y="{legend_y + 9}" font-size="10" fill="{TEXT_DIM}">Less</text>'
    for i, color in enumerate(HEAT_COLORS):
        legend += f'<rect x="{legend_x + 28 + i * 18}" y="{legend_y}" width="{cell_size}" height="{cell_size}" rx="2" fill="{color}"/>'
    legend += f'<text x="{legend_x + 28 + 5 * 18 + 4}" y="{legend_y + 9}" font-size="10" fill="{TEXT_DIM}">More</text>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    <style>
      @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
      text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif; }}
    </style>
    {_gradient_defs()}
    {_card_bg(width, height)}

    <g opacity="0" style="animation: fadeIn 0.4s ease 0s forwards">
      <text x="{margin_left}" y="28" font-size="16" font-weight="700" fill="{WHITE}">Contribution Graph</text>
      <rect x="{margin_left}" y="35" width="50" height="3" rx="1.5" fill="url(#accentGrad)"/>
    </g>

    {month_labels}
    {day_labels}
    {cells}
    {legend}
    </svg>"""
    return svg


def generate_typing_svg(stats):
    """Generate the animated typing SVG header."""
    lines = [
        "Full-Stack Developer",
        "SaaS & Dashboard Builder",
        "Automation Enthusiast",
        "Minimalist UX | Max Impact",
    ]

    # We cycle through lines with CSS animations
    total_duration = len(lines) * 4  # 4s per line
    line_elements = ""
    for i, line in enumerate(lines):
        start_pct = (i * 100) // len(lines)
        show_start = start_pct
        show_end = ((i + 1) * 100) // len(lines)

        line_elements += f"""
        <text x="325" y="32" text-anchor="middle" font-size="22" font-weight="500"
          fill="{PRIMARY}" font-family="'Fira Code', 'Cascadia Code', monospace"
          opacity="0">
          {line}
          <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;{show_start/100:.2f};{(show_start+2)/100:.2f};{(show_end-2)/100:.2f};{show_end/100:.2f};1" dur="{total_duration}s" repeatCount="indefinite"/>
        </text>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="650" height="50" viewBox="0 0 650 50">
    <style>
      @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
    </style>
    {line_elements}
    <!-- Cursor -->
    <rect x="520" y="12" width="2" height="26" rx="1" fill="{PRIMARY}" style="animation: blink 0.8s step-end infinite"/>
    </svg>"""
    return svg


# ─── Main ────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("Error: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"🔍 Fetching GitHub stats for {USERNAME}...")
    data = fetch_all_stats()
    stats = compute_stats(data)

    print(f"   ⭐ Stars: {stats['total_stars']} | 🔥 Commits: {stats['total_commits']} | 📦 Repos: {stats['total_repos']}")
    print(f"   🔥 Current Streak: {stats['current_streak']} | 🏆 Longest: {stats['longest_streak']}")
    print(f"   📊 Languages: {', '.join(l['name'] for l in stats['languages'][:5])}")

    generators = [
        ("stats.svg", generate_stats_card),
        ("streak.svg", generate_streak_card),
        ("languages.svg", generate_languages_card),
        ("contribution-graph.svg", generate_contribution_graph),
        ("typing.svg", generate_typing_svg),
    ]

    for filename, generator in generators:
        path = os.path.join(OUTPUT_DIR, filename)
        svg = generator(stats)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"   ✅ Generated {filename}")

    print(f"\n🎉 All SVGs generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
