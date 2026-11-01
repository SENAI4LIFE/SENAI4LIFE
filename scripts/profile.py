import argparse
from collections import deque
import datetime as dt
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OWNER = "SENAI4LIFE"
ASSETS = ROOT / "assets"
THEMES = {
    "dark": {"bg": "#211b26", "panel": "#2d2434", "line": "#55405a", "text": "#f6e7cc", "muted": "#c0a9bc", "accent": "#ff9b50", "empty": "#3a2d42"},
    "light": {"bg": "#fff7eb", "panel": "#f5eadc", "line": "#cfb9c8", "text": "#38263f", "muted": "#6e506b", "accent": "#a4420b", "empty": "#eadce7"},
}
COLORS = ["#ff9b50", "#bb8cb9", "#e6c595", "#e17643", "#8f8bbd", "#b7b37b"]
MOTION_CSS = (
    '@keyframes appear{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}'
    '@keyframes fill{from{transform:scaleX(.02)}to{transform:scaleX(1)}}'
    '@keyframes grow{from{transform:scaleY(.05)}to{transform:scaleY(1)}}'
    '.value,.enter{animation:appear .8s ease-out both}'
    '.language{transform-box:fill-box;transform-origin:left center;animation:fill 1s ease-out both}'
    '.bar{transform-box:fill-box;transform-origin:center bottom;animation:grow .6s ease-out both}'
)


def get_json(path):
    result = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)


def public_repositories(fetch=get_json):
    repos = []
    page = 1
    while True:
        batch = fetch(f"/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        repos.extend(r for r in batch if not r["private"] and not r["fork"] and r["name"] != OWNER)
        if len(batch) < 100:
            return repos
        page += 1


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.target = None
        self.tooltip = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.cells[attrs["id"]] = (attrs["data-date"], int(attrs["data-level"]))
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day"):
            self.target = attrs["for"]
            self.tooltip = []

    def handle_data(self, data):
        if self.target:
            self.tooltip.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.target:
            match = re.match(r"\s*(No|[\d,]+) contributions?\b", "".join(self.tooltip))
            if not match:
                raise ValueError("Unrecognized contribution tooltip")
            self.counts[self.target] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
            self.target = None

    def days(self):
        if len(self.cells) < 350 or self.cells.keys() - self.counts.keys():
            raise ValueError("Contribution calendar is incomplete")
        days = sorted((date, self.counts[key], level) for key, (date, level) in self.cells.items())
        dates = [dt.date.fromisoformat(day[0]) for day in days]
        if any(b - a != dt.timedelta(days=1) for a, b in zip(dates, dates[1:])):
            raise ValueError("Contribution calendar has duplicate or missing dates")
        if any(count < 0 or not 0 <= level <= 4 for _, count, level in days):
            raise ValueError("Contribution calendar has invalid values")
        return days


def streaks(days):
    run = longest = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    end = len(days) - 1
    if end >= 0 and days[end][1] == 0:
        end -= 1
    current = 0
    while end >= 0 and days[end][1]:
        current += 1
        end -= 1
    return current, longest


def text(x, y, value, size=16, fill="text", weight=400, extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" class="{fill}" {extra}>{html.escape(str(value))}</text>'


def svg(width, height, title, body, theme, bottom_gap=0):
    p = THEMES[theme]
    styles = "".join(f".{key}{{fill:{color}}}" for key, color in p.items())
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">'
        f'<title id="title">{html.escape(title)}</title><style>text{{font-family:Arial,Helvetica,sans-serif}}{styles}{MOTION_CSS}'
        '@media(prefers-reduced-motion:reduce){.motion{animation:none!important}.reveal{clip-path:none!important}}'
        '</style>'
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1-bottom_gap}" rx="18" class="bg" stroke="{p["line"]}"/>{body}</svg>\n'
    )


def write(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8", newline="\n")


def header(mobile=False):
    width, height = (480, 160) if mobile else (880, 170)
    body = '<style>@keyframes glow{50%{opacity:.25}}.spark{animation:glow 4s ease-in-out infinite}</style>'
    body += f'<path d="M{width-300} 0h300v{height}h-110z" fill="#302337"/><path d="M0 {height-7}h{width}" stroke="#fa7921" stroke-width="6"/>'
    body += '<path d="M32 28h18v4H36v18h-4zm52 0h18v22h-4V32H84z" fill="#fa7921"/>'
    body += text(width/2, 100 if mobile else 104, OWNER, 44 if mobile else 62, "text", 700, 'text-anchor="middle" letter-spacing="-2"')
    trace = "M32 124h95l10-9 14 18 12-9h285" if mobile else "M33 132h200l12-10 16 20 14-10h572"
    body += f'<path d="{trace}" fill="none" stroke="#79536e" stroke-width="2"/>'
    body += f'<path class="spark motion" d="M{width-39} 35h10m-5-5v10" stroke="#e6c595" stroke-width="2"/>'
    return svg(width, height, OWNER, body, "dark")


def overview(repos, days, theme):
    current, longest = streaks(days)
    body = text(24, 34, "OVERVIEW", 13, "accent", 700, 'letter-spacing="2"')
    metrics = [(len(repos), "public projects"), (sum(d[1] for d in days), "contributions / year"), (sum(bool(d[1]) for d in days), "active days / year"), (current, "current streak / days")]
    for i, (value, label) in enumerate(metrics):
        x, y = 24 + i % 2 * 200, 83 + i // 2 * 80
        body += text(x, y, f"{value:,}", 33, "text value motion", 700) + text(x, y+24, label, 14, "muted")
    body += f'<path d="M24 202h392" stroke="{THEMES[theme]["line"]}"/>'
    body += text(24, 229, f"Best streak: {longest} {'day' if longest == 1 else 'days'}", 15, "muted")
    return svg(440, 290, "Public project totals and contribution streaks over the displayed year", body, theme, 8)


def languages(totals, theme):
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    top = ranked[:5]
    if len(ranked) > 5:
        top.append(("Other", sum(v for _, v in ranked[5:])))
    total = sum(totals.values())
    body = text(24, 34, "LANGUAGE MIX", 13, "accent", 700, 'letter-spacing="2"')
    body += text(24, 60, "Public repositories", 14, "muted")
    x = 24
    for i, (_, value) in enumerate(top):
        width = value / total * 392
        body += f'<rect x="{x:.2f}" y="80" width="{width:.2f}" height="12" class="language motion" fill="{COLORS[i]}"/>'
        x += width
    for i, (name, value) in enumerate(top):
        x, y = 24 + i % 2 * 205, 126 + i // 2 * 39
        body += f'<circle cx="{x+4}" cy="{y-5}" r="4" fill="{COLORS[i]}"/>'
        body += text(x+16, y, name, 14) + text(x+174, y, f"{value/total:.1%}", 13, "muted", extra='text-anchor="end"')
    if not total:
        body += text(24, 126, "No language data available", 16, "muted")
    body += text(24, 262, "Source bytes · forks excluded", 12, "muted")
    return svg(440, 290, "Language usage by source bytes in public original repositories", body, theme, 8)


def activity(days, theme):
    recent = days[-30:]
    maximum = max(1, max(d[1] for d in recent))
    body = text(24, 34, "30-DAY PULSE", 13, "accent", 700, 'letter-spacing="2"')
    body += text(24, 61, "Daily contributions", 15, "muted")
    body += text(416, 61, f"{sum(d[1] for d in recent):,} total", 17, "text", 700, 'text-anchor="end"')
    for i, (date, count, _) in enumerate(recent):
        h = max(2, count / maximum * 115)
        body += f'<rect x="{24+i*13.2:.1f}" y="{206-h:.1f}" width="9" height="{h:.1f}" rx="2" class="accent bar motion" style="animation-delay:{i*.025:.3f}s"><title>{date}: {count} contributions</title></rect>'
    body += text(24, 233, recent[0][0][5:], 13, "muted") + text(416, 233, recent[-1][0][5:], 13, "muted", extra='text-anchor="end"')
    return svg(440, 290, "Daily contribution chart for the most recent 30 days", body, theme, 8)


def recent_projects(repos, theme):
    recent = sorted(repos, key=lambda r: r["pushed_at"] or "", reverse=True)[:4]
    body = text(24, 34, "RECENT PROJECTS", 13, "accent", 700, 'letter-spacing="2"')
    body += text(24, 61, "Latest updates", 14, "muted")
    for i, repo in enumerate(recent):
        y = 101 + i * 42
        name = repo["name"]
        if len(name) > 29:
            name = name[:26] + "…"
        body += text(24, y, name, 16, "text enter motion", 700)
        body += text(416, y, repo["pushed_at"][:10], 13, "muted", extra='text-anchor="end"')
        body += f'<path d="M24 {y+13}h392" stroke="{THEMES[theme]["line"]}"/>'
    return svg(440, 290, "The four most recently updated public original repositories", body, theme, 8)


def contribution_route(cells):
    remaining = {position for position, count in cells.items() if count > 0}
    if not remaining:
        return [], {}
    current = min(remaining)
    route = [current]
    eaten = {current: 0}
    remaining.remove(current)
    while remaining:
        queue = deque([current])
        parents = {current: None}
        target = None
        while queue:
            position = queue.popleft()
            if position in remaining:
                target = position
                break
            column, row = position
            for neighbor in [(column, row+1), (column+1, row), (column, row-1), (column-1, row)]:
                if neighbor in cells and neighbor not in parents:
                    parents[neighbor] = position
                    queue.append(neighbor)
        if target is None:
            raise ValueError("Contribution cells are disconnected")
        path = []
        position = target
        while position != current:
            path.append(position)
            position = parents[position]
        for position in reversed(path):
            route.append(position)
            if position in remaining:
                eaten[position] = len(route)-1
                remaining.remove(position)
        current = target
    return route, eaten


def trail(days, theme):
    start = dt.date.fromisoformat(days[0][0])
    start -= dt.timedelta(days=(start.weekday()+1) % 7)
    palette = [THEMES[theme]["empty"], "#79506a", "#ae6660", "#d8793b", "#fa9b50"]
    body = text(26, 35, "CONTRIBUTION TRAIL", 14, "accent", 700, 'letter-spacing="2"')
    body += text(26, 61, "One year of contributions.", 16, "muted")
    cells = {}
    month = None
    for date, count, level in days:
        day = dt.date.fromisoformat(date)
        week = (day-start).days // 7
        row = (day.weekday()+1) % 7
        x, y = 27+week*16, 98+row*16
        cells[(week, row)] = (date, count, level, x, y)
        if day.month != month and (day.day < 8 or month is None) and week < 52:
            month = day.month
            body += text(x, 87, day.strftime("%b"), 11, "muted")
    route, eaten = contribution_route({position: cell[1] for position, cell in cells.items()})
    steps = max(1, len(route)-1)
    duration = max(18, min(42, len(route)*.1))
    styles = []
    for index, (position, (date, count, level, x, y)) in enumerate(cells.items()):
        animation = ""
        if position in eaten:
            hit = max(.1, eaten[position]/steps*94)
            styles.append(f'@keyframes eat-{index}{{0%,{hit-.01:.3f}%{{fill:{palette[level]}}}{hit:.3f}%,100%{{fill:{palette[0]}}}}}.food-{index}{{animation:eat-{index} {duration:g}s linear infinite}}')
            animation = f' class="food-{index} motion"'
        body += f'<rect x="{x}" y="{y}" width="11" height="11" rx="2" fill="{palette[level]}"{animation}><title>{date}: {count} contributions</title></rect>'
    if route:
        positions = [(cells[position][3]+5.5, cells[position][4]+5.5) for position in route]
        keyframes = "".join(f'{i/steps*94:.3f}%{{transform:translate({x:.1f}px,{y:.1f}px)}}' for i, (x, y) in enumerate(positions))
        keyframes += f'100%{{transform:translate({positions[-1][0]:.1f}px,{positions[-1][1]:.1f}px)}}'
        body += '<style>' + ''.join(styles) + '@keyframes walk{' + keyframes + f'}}.walker{{animation:walk {duration:g}s linear infinite}}</style>'
        for i in range(5, -1, -1):
            body += f'<g class="walker motion" style="transform:translate({positions[0][0]}px,{positions[0][1]}px);animation-delay:{i*duration*.94/steps:.3f}s"><rect x="-5" y="-5" width="10" height="10" rx="3" fill="{COLORS[0]}" opacity="{1-i*.1:.1f}"/>'
            if i == 0:
                body += '<path d="M-5-2v-7l4 4m2 0 4-4v7" fill="#fa7921"/><circle cx="-2" cy="-1" r="1" fill="#38263f"/><circle cx="2" cy="-1" r="1" fill="#38263f"/>'
            body += '</g>'
    body += text(26, 235, f"{days[0][0]} → {days[-1][0]}", 12, "muted")
    body += text(702, 235, "Less", 12, "muted")
    for i, color in enumerate(palette):
        body += f'<rect x="{738+i*16}" y="225" width="11" height="11" rx="2" fill="{color}"/>'
    body += text(828, 235, "More", 12, "muted")
    return svg(896, 256, "Yearly contribution calendar with an animated fox trail; each square represents a day", body, theme)


def build_static():
    ASSETS.mkdir(exist_ok=True)
    write("header.svg", header())
    write("header-mobile.svg", header(True))


def refresh():
    repos = public_repositories()
    totals = {}
    for repo in repos:
        for language, count in get_json(f'/repos/{OWNER}/{repo["name"]}/languages').items():
            totals[language] = totals.get(language, 0) + count
    request = urllib.request.Request(f"https://github.com/users/{OWNER}/contributions", headers={"User-Agent": "profile-readme", "Accept-Language": "en-US"})
    with urllib.request.urlopen(request, timeout=45) as response:
        calendar = CalendarParser()
        calendar.feed(response.read().decode("utf-8"))
    days = calendar.days()
    stamp = dt.datetime.now(dt.timezone.utc).date().isoformat()
    if days[-1][0] != stamp:
        raise ValueError("Contribution calendar is stale")
    rendered = {}
    for theme in THEMES:
        rendered.update({
            f"overview-{theme}.svg": overview(repos, days, theme),
            f"languages-{theme}.svg": languages(totals, theme),
            f"activity-{theme}.svg": activity(days, theme),
            f"recent-{theme}.svg": recent_projects(repos, theme),
            f"trail-{theme}.svg": trail(days, theme),
        })
    for name, content in rendered.items():
        ET.fromstring(content)
    for name, content in rendered.items():
        write(name, content)
    print(f"Refreshed {len(rendered)} assets from {len(repos)} public projects and {len(days)} calendar days")


def check():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for path in re.findall(r'(?:src|srcset)="(assets/[^" ]+)"', readme):
        if not (ROOT / path).is_file():
            raise ValueError(f"Missing README asset: {path}")
    for path in ASSETS.rglob("*.svg"):
        tree = ET.fromstring(path.read_text(encoding="utf-8"))
        for item in tree.iter():
            if item.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}:
                raise ValueError(f"Unsupported SVG element: {path.name}")
            for key, value in item.attrib.items():
                if key.lower().startswith("on") or (key.endswith("href") and not value.startswith(("#", "data:image/png;base64,"))):
                    raise ValueError(f"External or executable SVG content: {path.name}")
    if re.search(r'https?://[^" )]+\.(?:app|com)/api\?', readme):
        raise ValueError("README contains a remotely rendered widget")
    for theme in THEMES:
        for name in ["overview", "languages", "activity", "recent", "trail"]:
            if not (ASSETS / f"{name}-{theme}.svg").is_file():
                raise ValueError(f"Missing {theme} asset: {name}")
    print("Profile assets and README references passed validation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.build or args.refresh:
        build_static()
    if args.refresh:
        refresh()
    if args.check:
        check()
    if not args.refresh and not args.check and not args.build:
        parser.error("Choose --build, --refresh, or --check")
