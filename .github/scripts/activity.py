"""Draws the README activity graph (light and dark SVG) from the GitHub GraphQL API."""
import datetime as dt
import json
import os
import urllib.request

USER = os.environ["USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = "activity"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
      commitContributionsByRepository(maxRepositories: 10) {
        repository { name isPrivate }
        contributions { totalCount }
      }
    }
  }
}
"""

THEMES = {
    "light": {
        "text": "#0a0a0b", "muted": "#6e6e6c",
        "cells": ["#ebebe8", "#c4c4c0", "#8f8f8c", "#50504f", "#0a0a0b"],
    },
    "dark": {
        "text": "#eeeeec", "muted": "#8b8b8f",
        "cells": ["#1f2126", "#43464d", "#72757c", "#aeb0b5", "#f0f0ee"],
    },
}
LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"

WIDTH = 880
LEFT, TOP = 34, 92
GAP = 3


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", body,
        {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["user"]["contributionsCollection"]


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current, i = 0, len(counts) - 1
    if counts[i] == 0:  # today not started yet
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return current, longest


def fmt(n):
    return f"{n:,}"


def svg(data, theme):
    t = THEMES[theme]
    cal = data["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    current, longest = streaks(days)
    best = max(days, key=lambda d: d["contributionCount"])
    best_date = dt.date.fromisoformat(best["date"]).strftime("%b %-d")

    # cells stretch so the grid fills the width exactly
    global STEP, CELL
    STEP = (WIDTH - LEFT + GAP) / len(weeks)
    CELL = STEP - GAP
    grid_w = WIDTH - LEFT
    x0 = LEFT
    grid_bottom = round(TOP + 7 * STEP - GAP)
    height = grid_bottom + 58

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Contribution activity">',
        f'<style>text{{font-family:{SANS};fill:{t["text"]}}}.m{{font-family:{MONO};'
        f'fill:{t["muted"]};font-size:10px;letter-spacing:.08em}}.n{{font-size:22px;font-weight:600}}'
        f'rect{{animation:f .5s ease-out both}}@keyframes f{{from{{opacity:0}}}}</style>',
    ]

    stats = [
        (fmt(cal["totalContributions"]), "CONTRIBUTIONS · LAST YEAR"),
        (f"{current} days", "CURRENT STREAK"),
        (f"{longest} days", "LONGEST STREAK"),
        (f"{best['contributionCount']}", f"BUSIEST DAY · {best_date.upper()}"),
    ]
    col = (WIDTH - x0) / len(stats)
    for i, (num, label) in enumerate(stats):
        x = x0 + i * col
        out.append(f'<text x="{x:.0f}" y="28" class="n">{num}</text>')
        out.append(f'<text x="{x:.0f}" y="46" class="m">{label}</text>')

    last_month = None
    for wi, w in enumerate(weeks):
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != last_month and first.day <= 7 and wi < len(weeks) - 1:
            out.append(f'<text x="{x0 + wi * STEP:.0f}" y="{TOP - 8}" class="m">{first.strftime("%b").upper()}</text>')
            last_month = first.month
        elif last_month is None:
            last_month = first.month
        for d in w["contributionDays"]:
            wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday first
            color = t["cells"][LEVELS.index(d["contributionLevel"])]
            delay = wi * 12
            out.append(
                f'<rect x="{x0 + wi * STEP:.1f}" y="{TOP + wd * STEP:.1f}" width="{CELL:.1f}" height="{CELL:.1f}" rx="2.5" '
                f'fill="{color}" style="animation-delay:{delay}ms"><title>{d["date"]}: '
                f'{d["contributionCount"]} contributions</title></rect>'
            )
    for wd, name in ((1, "MON"), (3, "WED"), (5, "FRI")):
        out.append(f'<text x="0" y="{TOP + wd * STEP + CELL - 3:.0f}" class="m">{name}</text>')

    repos = [
        r for r in data["commitContributionsByRepository"] if not r["repository"]["isPrivate"]
    ][:4]
    if repos:
        line = "   ".join(f'{r["repository"]["name"]} {r["contributions"]["totalCount"]}' for r in repos)
        out.append(f'<text x="{x0}" y="{grid_bottom + 36}" class="m">MOST COMMITS   {line.upper()}</text>')

    more_x = WIDTH - 32
    lx = more_x - 8 - 5 * STEP + GAP
    out.append(f'<text x="{lx - 8}" y="{grid_bottom + 36}" class="m" text-anchor="end">LESS</text>')
    for i, c in enumerate(t["cells"]):
        out.append(f'<rect x="{lx + i * STEP:.1f}" y="{grid_bottom + 26}" width="{CELL:.1f}" height="{CELL:.1f}" rx="2.5" fill="{c}"/>')
    out.append(f'<text x="{more_x}" y="{grid_bottom + 36}" class="m">MORE</text>')

    out.append("</svg>")
    return "\n".join(out)


def main():
    data = fetch()
    os.makedirs(OUT, exist_ok=True)
    for theme in THEMES:
        with open(f"{OUT}/{theme}.svg", "w") as f:
            f.write(svg(data, theme))


if __name__ == "__main__":
    main()
