"""
Stats card builder
------------------
Reads live numbers from the GitHub API and draws dist/stats.svg in the same
fonts and colours as the rest of the profile ("By the numbers" section).

Run daily by .github/workflows/profile.yml. Uses only the Python standard library.
"""
import base64, datetime as dt, json, os, re, sys, urllib.request

# Settings come from the workflow environment.
LOGIN = os.environ.get("GH_LOGIN") or sys.argv[1]
TOKEN = os.environ.get("GH_TOKEN", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist")
ACC = "#ff5c5c"


# Send one GraphQL query to the GitHub API and return its "data" part.
def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]


# Collect every number shown on the card: stars, commits, PRs, followers,
# repos, total contributions and current / longest streak.
def fetch():
    base = gql("""query($login:String!){user(login:$login){
      createdAt followers{totalCount}
      repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100){totalCount nodes{stargazerCount}}
      pullRequests{totalCount}
      repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount}
      contributionsCollection{totalCommitContributions
        contributionCalendar{weeks{contributionDays{date contributionCount contributionLevel}}}}}}""", login=LOGIN)["user"]
    # Last 12 months, week by week, for the contributions grid
    weeks = [[d["contributionLevel"] for d in w["contributionDays"]]
             for w in base["contributionsCollection"]["contributionCalendar"]["weeks"]]
    days = []
    start = int(base["createdAt"][:4])
    now = dt.datetime.now(dt.timezone.utc)
    for year in range(start, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = now.strftime("%Y-%m-%dT%H:%M:%SZ") if year == now.year else f"{year}-12-31T23:59:59Z"
        cal = gql("""query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
          contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}""",
                  login=LOGIN, **{"from": frm, "to": to})["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            days += [(d["date"], d["contributionCount"]) for d in w["contributionDays"]]
    days = sorted({d: c for d, c in days}.items())
    today = now.date().isoformat()
    days = [x for x in days if x[0] <= today]
    total = sum(c for _, c in days)
    # longest streak
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # current streak (today may still be empty)
    cur = 0
    seq = days[::-1]
    if seq and seq[0][1] == 0:
        seq = seq[1:]
    for _, c in seq:
        if not c:
            break
        cur += 1
    return {
        "stars": sum(n["stargazerCount"] for n in base["repositories"]["nodes"]),
        "commits": base["contributionsCollection"]["totalCommitContributions"],
        "prs": base["pullRequests"]["totalCount"],
        "contrib": base["repositoriesContributedTo"]["totalCount"],
        "followers": base["followers"]["totalCount"],
        "repos": base["repositories"]["totalCount"],
        "total": total, "current": cur, "longest": longest,
        "views": profile_views(), "weeks": weeks,
    }


# Profile views come from the komarev counter that README.md loads (hidden 1px image).
# Reading it here adds one view per day, which is negligible.
def profile_views():
    try:
        req = urllib.request.Request(f"https://komarev.com/ghpvc/?username={LOGIN}", headers={"User-Agent": "profile-stats"})
        with urllib.request.urlopen(req, timeout=20) as r:
            svg = r.read().decode("utf-8", "ignore")
        nums = re.findall(r">\s*([\d,\.]+[kKmM]?)\s*<", svg)
        return nums[-1] if nums else "—"
    except Exception:
        return "—"


# Read a font file from assets/fonts and return it base64-encoded (fonts are embedded in the SVG).
def font(name):
    with open(os.path.join(ROOT, "assets", "fonts", name), "rb") as f:
        return base64.b64encode(f.read()).decode()


# @font-face rules for Space Grotesk and JetBrains Mono, embedded so the card renders the same everywhere.
def style():
    return (f"@font-face{{font-family:'SG';font-weight:400;src:url(data:font/woff2;base64,{font('SpaceGrotesk-400.woff2')}) format('woff2')}}"
            f"@font-face{{font-family:'SG';font-weight:700;src:url(data:font/woff2;base64,{font('SpaceGrotesk-700.woff2')}) format('woff2')}}"
            f"@font-face{{font-family:'JBM';font-weight:400;src:url(data:font/woff2;base64,{font('JetBrainsMono-400.woff2')}) format('woff2')}}"
            f"@font-face{{font-family:'JBM';font-weight:600;src:url(data:font/woff2;base64,{font('JetBrainsMono-600.woff2')}) format('woff2')}}")


# Line icons for each tile: (colour, SVG path)
ICONS = {
    "star": ("#ffd166", '<path d="M12 2l3 6.5 7 .8-5.2 4.8 1.4 7L12 17.6 5.8 21l1.4-7L2 9.3l7-.8z"/>'),
    "commit": (ACC, '<circle cx="12" cy="12" r="3.5"/><path d="M2 12h6.5M15.5 12H22"/>'),
    "pr": ("#7ee0c3", '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M6 8.5v7M18 15.5V9a3 3 0 0 0-3-3h-4M13 3.5 10.5 6 13 8.5"/>'),
    "repo": ("#8ab4f8", '<path d="M4 19.5V5a2 2 0 0 1 2-2h14v15H6.5A2.5 2.5 0 0 0 4 20.5 2.5 2.5 0 0 0 6.5 23H20v-5"/>'),
    "people": ("#b8a4ff", '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>'),
}


# Short number format: 12,345 -> 12.3k
def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


# Draw the card: four number tiles on top, streak + community cards underneath.
def stats_svg(s):
    W, gap = 940, 14
    tw = (W - 3 * gap) / 4
    parts = []
    tiles = [("star", s["stars"], "Stars earned"), ("commit", s["commits"], "Commits this year"),
             ("pr", s["prs"], "Pull requests"), ("repo", s["contrib"], "Repos contributed to")]
    for i, (ic, val, lab) in enumerate(tiles):
        x = i * (tw + gap)
        col, path = ICONS[ic]
        parts.append(f'<rect x="{x+.5:.1f}" y=".5" width="{tw-1:.1f}" height="135" rx="14" fill="#161b22" stroke="#30363d"/>'
                     f'<rect x="{x+18:.1f}" y="18" width="36" height="36" rx="10" fill="{col}" fill-opacity=".13"/>'
                     f'<g transform="translate({x+27:.1f} 27) scale(.75)" fill="none" stroke="{col}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">{path}</g>'
                     f'<text x="{x+18:.1f}" y="92" font-family="SG" font-weight="700" font-size="30" fill="#f0f6fc">{fmt(val)}</text>'
                     f'<text x="{x+18:.1f}" y="118" font-family="SG" font-size="13" fill="#8b949e">{lab}</text>')
    y = 150
    sw = (W - gap) * 2 / 3
    parts.append(f'<rect x=".5" y="{y+.5}" width="{sw-1:.1f}" height="189" rx="14" fill="#161b22" stroke="#30363d"/>'
                 f'<text x="22" y="{y+32}" font-family="JBM" font-size="12" letter-spacing="1.5" fill="#8b949e">STREAK</text>')
    cw = sw / 3
    for i, (val, lab, color) in enumerate([(s["total"], "Total contributions", "#8b949e"), (s["current"], "Current streak", ACC), (s["longest"], "Longest streak", "#8b949e")]):
        cx = cw * (i + .5)
        if i == 1:
            parts.append(f'<circle cx="{cx:.1f}" cy="{y+100}" r="45" fill="none" stroke="{ACC}" stroke-width="6"/>'
                         f'<circle cx="{cx:.1f}" cy="{y+55}" r="13" fill="#161b22"/>'
                         f'<g class="fl"><path transform="translate({cx-9:.1f} {y+46}) scale(.75)" fill="{ACC}" d="M12 2c1 3.5 5 5.5 5 10.5a5 5 0 0 1-10 0c0-2.4 1.2-4 2.5-5.3.3 1.8 1.2 2.8 2.3 3.3C11.4 8 11 5 12 2z"/></g>'
                         f'<text x="{cx:.1f}" y="{y+110}" text-anchor="middle" font-family="SG" font-weight="700" font-size="28" fill="#f0f6fc">{fmt(val)}</text>'
                         f'<text x="{cx:.1f}" y="{y+170}" text-anchor="middle" font-family="SG" font-weight="700" font-size="13" fill="{ACC}">{lab}</text>')
        else:
            parts.append(f'<text x="{cx:.1f}" y="{y+108}" text-anchor="middle" font-family="SG" font-weight="700" font-size="28" fill="#f0f6fc">{fmt(val)}</text>'
                         f'<text x="{cx:.1f}" y="{y+132}" text-anchor="middle" font-family="SG" font-size="13" fill="{color}">{lab}</text>')
    x2 = sw + gap
    w2 = W - x2
    parts.append(f'<rect x="{x2+.5:.1f}" y="{y+.5}" width="{w2-1:.1f}" height="189" rx="14" fill="#161b22" stroke="#30363d"/>'
                 f'<text x="{x2+22:.1f}" y="{y+32}" font-family="JBM" font-size="12" letter-spacing="1.5" fill="#8b949e">COMMUNITY</text>')
    for i, (ic, val, lab) in enumerate([("people", s["followers"], "Followers"), ("repo", s["repos"], "Public repos")]):
        yy = y + 58 + i * 62
        col, path = ICONS[ic]
        parts.append(f'<rect x="{x2+22:.1f}" y="{yy}" width="40" height="40" rx="11" fill="{col}" fill-opacity=".13"/>'
                     f'<g transform="translate({x2+32:.1f} {yy+10}) scale(.8333)" fill="none" stroke="{col}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{path}</g>'
                     f'<text x="{x2+76:.1f}" y="{yy+19}" font-family="SG" font-weight="700" font-size="20" fill="#f0f6fc">{fmt(val)}</text>'
                     f'<text x="{x2+76:.1f}" y="{yy+37}" font-family="SG" font-size="13" fill="#8b949e">{lab}</text>')
    H = y + 190
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{s["stars"]} stars, {s["commits"]} commits this year, {s["prs"]} pull requests, {s["contrib"]} repos contributed to, '
            f'{s["total"]} total contributions, {s["current"]} day current streak, {s["longest"]} day longest streak">'
            f'<style>{style()}@keyframes fl{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-3px)}}}}.fl{{animation:fl 1.6s ease-in-out infinite}}</style>'
            + "".join(parts) + "</svg>")


# Badge row under the status strip: profile views · followers · stars (same pills as the design).
def badges_svg(s):
    items = [
        ("profile views", s.get("views", "—"), '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
        ("followers", fmt(s["followers"]), '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.8c1.7.7 2.7 2.4 3 5.2"/>'),
        ("stars", fmt(s["stars"]), '<path d="M12 2.8l2.8 5.8 6.4.9-4.6 4.5 1.1 6.3L12 17.3l-5.7 3 1.1-6.3-4.6-4.5 6.4-.9z"/>'),
    ]
    CH, H, gap = 7.22, 34, 10                     # JetBrains Mono 12px char width, pill height, gap
    pills, widths = [], []
    for label, value, icon in items:
        lw = 12 + 14 + 8 + len(label) * CH + 12   # padding + icon + gap + text + padding
        vw = 12 + len(str(value)) * CH + 12
        widths.append((lw, vw))
    total = sum(l + v for l, v in widths) + gap * (len(items) - 1)
    W = 940
    x = (W - total) / 2
    for (label, value, icon), (lw, vw) in zip(items, widths):
        w = lw + vw
        pills.append(
            f'<clipPath id="c{len(pills)}"><rect x="{x+.5:.1f}" y=".5" width="{w-1:.1f}" height="{H-1}" rx="8"/></clipPath>'
            f'<g clip-path="url(#c{len(pills)})"><rect x="{x:.1f}" y="0" width="{w:.1f}" height="{H}" fill="#161b22"/>'
            f'<rect x="{x+lw:.1f}" y="0" width="{vw:.1f}" height="{H}" fill="#21262d"/></g>'
            f'<line x1="{x+lw:.1f}" y1="0" x2="{x+lw:.1f}" y2="{H}" stroke="#30363d"/>'
            f'<rect x="{x+.5:.1f}" y=".5" width="{w-1:.1f}" height="{H-1}" rx="8" fill="none" stroke="#30363d"/>'
            f'<g transform="translate({x+12:.1f} 10) scale(.5833)" fill="none" stroke="{ACC}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">{icon}</g>'
            f'<text x="{x+34:.1f}" y="21.5" font-family="JBM" font-size="12" fill="#a5b0c2">{label}</text>'
            f'<text x="{x+lw+12:.1f}" y="21.5" font-family="JBM" font-weight="600" font-size="12" fill="#f0f6fc">{value}</text>')
        x += w + gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{s.get("views","—")} profile views, {s["followers"]} followers, {s["stars"]} stars">'
            f'<style>{style()}</style>' + "".join(pills) + "</svg>")


# Contributions card with a Pac-Man game: Pac-Man snakes through every row of the
# last 12 months, eating each contribution square (and the small pellets on empty days),
# with three ghosts chasing him. Eaten squares grow back after a while, so it loops forever.
def serpentine_svg(s):
    LEVEL = {"FIRST_QUARTILE": "#4a1f24", "SECOND_QUARTILE": "#8f3a42",
             "THIRD_QUARTILE": "#c84a52", "FOURTH_QUARTILE": ACC}
    weeks = s["weeks"][-53:]
    n = len(weeks)
    W, PAD, CELL, STEP = 940, 22, 13, 16
    gx, gy = PAD + 1, 70                          # grid origin
    gw = (n - 1) * STEP                           # distance from first to last column centre
    H = gy + 7 * STEP + 22
    SPEED = 230                                   # px per second
    lap = 7 * gw + 6 * STEP                       # serpentine path length
    D = round(lap / SPEED + 1.5, 2)               # seconds per loop (+ short pause)
    cx = lambda w: gx + w * STEP + CELL / 2
    cy = lambda d: gy + d * STEP + CELL / 2

    # Serpentine route: row 0 left→right, row 1 right→left, …
    pts = [f"M{cx(0)},{cy(0)}"]
    for d in range(7):
        pts.append(f"H{cx(n-1) if d % 2 == 0 else cx(0)}")
        if d < 6:
            pts.append(f"V{cy(d+1)}")
    route = " ".join(pts)

    def eaten_at(w, d):                           # when Pac-Man reaches this cell
        along = (w if d % 2 == 0 else n - 1 - w) * STEP
        return (d * (gw + STEP) + along) / SPEED

    cells = []
    for w, week in enumerate(weeks):
        for d, lvl in enumerate(week):
            delay = eaten_at(w, d) - D
            col = LEVEL.get(lvl)
            if col:                               # contribution square
                cells.append(f'<rect class="e" style="animation-delay:{delay:.2f}s" x="{gx + w*STEP}" y="{gy + d*STEP}" '
                             f'width="{CELL}" height="{CELL}" rx="3" fill="{col}"/>')
            else:                                 # empty day = small pellet
                cells.append(f'<circle class="e" style="animation-delay:{delay:.2f}s" cx="{cx(w)}" cy="{cy(d)}" r="1.6" fill="#6e7681"/>')

    legend_x = W - PAD - 52 - 4 * 15
    legend = (f'<text x="{legend_x - 10}" y="40" text-anchor="end" font-family="SG" font-size="13" fill="#8b949e">Less</text>'
              + "".join(f'<rect x="{legend_x + i*15}" y="29" width="11" height="11" rx="3" fill="{c}"/>'
                        for i, c in enumerate(["#4a1f24", "#8f3a42", "#c84a52", ACC]))
              + f'<text x="{legend_x + 4*15 + 2}" y="40" font-family="SG" font-size="13" fill="#8b949e">More</text>')
    score = (f'<text x="{PAD + 170}" y="40" font-family="JBM" font-size="12" letter-spacing="1.5" fill="#8b949e">SCORE '
             f'<tspan fill="#ffd166" font-weight="600">{s["total"] * 10:,}</tspan></text>')

    def ghost(color, lag):                        # classic ghost with wavy hem and eyes
        body = (f'<path d="M-8 8V-1a8 8 0 0 1 16 0V8l-2.7-2.4L10.6 8 8 5.6 5.3 8 2.7 5.6 0 8l-2.7-2.4L-5.3 8-8 5.6z" fill="{color}"/>'
                '<circle cx="-3" cy="-1" r="2.4" fill="#fff"/><circle cx="3" cy="-1" r="2.4" fill="#fff"/>'
                '<circle cx="-2.4" cy="-1" r="1.1" fill="#1f2a5a"/><circle cx="3.6" cy="-1" r="1.1" fill="#1f2a5a"/>')
        return (f'<g transform="scale(.95)">{body}</g>'
                f'<animateMotion dur="{D}s" begin="-{D - lag:.2f}s" repeatCount="indefinite" path="{route}" {motion}/>')

    lag = 26 / SPEED                              # spacing between characters
    run = (D - 1.5) / D                           # share of the loop spent moving
    motion = f'calcMode="linear" keyTimes="0;{run:.4f};1" keyPoints="0;1;1"'
    actors = (
        f'<g>{ghost("#ffb8de", 3*lag)}</g>'
        f'<g>{ghost("#7ee0f0", 2*lag)}</g>'
        f'<g>{ghost(ACC, lag)}</g>'
        f'<g><path fill="#ffd166"><animate attributeName="d" dur=".28s" repeatCount="indefinite" '
        f'values="M0 0L9.2 -4A10 10 0 1 0 9.2 4Z;M0 0L10 -0.4A10 10 0 1 0 10 0.4Z;M0 0L9.2 -4A10 10 0 1 0 9.2 4Z"/></path>'
        f'<animateMotion dur="{D}s" begin="0s" repeatCount="indefinite" rotate="auto" path="{route}" {motion}/></g>'
    )
    css = ("@keyframes eat{0%{opacity:0}26%{opacity:0}33%,100%{opacity:1}}"
           f".e{{animation:eat {D}s linear infinite}}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Pac-Man eating my contribution graph for the last 12 months">'
            f'<style>{style()}{css}</style>'
            f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="14" fill="#161b22" stroke="#30363d"/>'
            f'<text x="{PAD}" y="40" font-family="JBM" font-size="12" letter-spacing="1.5" fill="#8b949e">CONTRIBUTIONS</text>'
            + legend + "".join(cells) + actors + "</svg>")


# Contributions card. If the Pac-Man maze game (pacman-contribution-graph, run earlier in the
# workflow) produced dist/pacman-contribution-graph-dark.svg, it is recoloured to the red theme
# and placed inside the card, so Pac-Man runs through a real maze and the ghosts chase him.
# Otherwise the simpler built-in serpentine version is drawn instead.
MAZE_COLOURS = {   # GitHub dark greens -> profile reds, white walls -> deep red (with a red glow), empty tiles -> soft light highlight
    "#0e4429": "#4a1f24", "#006d32": "#8f3a42", "#26a641": "#c84a52", "#39d353": "#ff5c5c",
    "#ffffff": "#6e1520", "#161b22": "#262d37", "#0d1117": "#161b22",
}

def contrib_svg(s):
    src = os.path.join(OUT, "pacman-contribution-graph-dark.svg")
    if not os.path.exists(src):
        return serpentine_svg(s)
    game = open(src, encoding="utf-8").read()
    for old, new in MAZE_COLOURS.items():
        game = re.sub(re.escape(old), new, game, flags=re.IGNORECASE)
    m = re.search(r'<svg[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', game)
    gw, gh = float(m.group(1)), float(m.group(2))
    W, PAD, TOP = 940, 22, 58
    inner_w = W - 2 * PAD
    inner_h = inner_w * gh / gw
    H = round(TOP + inner_h + 16)
    # open the game's own <svg> tag with a position, size and viewBox inside the card
    game = re.sub(r"<\?xml[^>]*\?>", "", game)
    game = re.sub(r"<svg\b[^>]*>", f'<svg x="{PAD}" y="{TOP}" width="{inner_w}" height="{inner_h:.1f}" viewBox="0 0 {gw:g} {gh:g}">', game, count=1)
    # Red neon glow around the maze walls (wall pieces have ids starting "wh-" / "wv-")
    glow = ('<defs><filter id="wallglow" x="-60%" y="-60%" width="220%" height="220%">'
            '<feGaussianBlur in="SourceAlpha" stdDeviation="2.2" result="b"/>'
            '<feFlood flood-color="#ff2e40" flood-opacity="1"/><feComposite in2="b" operator="in" result="g"/>'
            '<feMerge><feMergeNode in="g"/><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
    game = re.sub(r"(<svg\b[^>]*>)", r"\1" + glow, game, count=1)
    legend_x = W - PAD - 52 - 4 * 15
    legend = (f'<text x="{legend_x - 10}" y="40" text-anchor="end" font-family="SG" font-size="13" fill="#8b949e">Less</text>'
              + "".join(f'<rect x="{legend_x + i*15}" y="29" width="11" height="11" rx="3" fill="{c}"/>'
                        for i, c in enumerate(["#4a1f24", "#8f3a42", "#c84a52", ACC]))
              + f'<text x="{legend_x + 4*15 + 2}" y="40" font-family="SG" font-size="13" fill="#8b949e">More</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Pac-Man eating my contribution graph for the last 12 months">'
            f'<style>{style()}svg svg text{{font-family:\'JBM\',monospace;fill:#8b949e}}[id^="wh-"],[id^="wv-"]{{filter:url(#wallglow)}}</style>'
            f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="14" fill="#161b22" stroke="#30363d"/>'
            f'<text x="{PAD}" y="40" font-family="JBM" font-size="12" letter-spacing="1.5" fill="#8b949e">CONTRIBUTIONS</text>'
            + legend + game + "</svg>")


# Entry point. FAKE_STATS (JSON) can be set to preview the card without calling the API.
def main():
    s = json.loads(os.environ["FAKE_STATS"]) if os.environ.get("FAKE_STATS") else fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, draw in (("stats.svg", stats_svg), ("badges.svg", badges_svg), ("contributions.svg", contrib_svg)):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(draw(s))
    print(json.dumps({k: v for k, v in s.items() if k != "weeks"}))


if __name__ == "__main__":
    main()
