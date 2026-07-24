"""Render run results into the scoreboard site + shields.io badge endpoints."""
from __future__ import annotations

import html
import json
import statistics
import urllib.parse
from pathlib import Path

from .checkpoints import CHECKPOINTS, WEIGHTS

SITE = Path("docs")
RUNS = Path("runs")
HISTORY = Path("runs/history.jsonl")
REPO = "https://github.com/zhannur/agent-ready"
PAGES = "https://zhannur.github.io/agent-ready"

FONT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">"""

# design tokens — "laboratory terminal": carbon surfaces, phosphor accents, mono-led type
BASE_CSS = """
:root {
  color-scheme: dark;
  --bg: #0a0c10; --card: #12151b; --inset: #0d1014; --line: #232833; --line2: #2e3542;
  --ink: #e8edf2; --ink2: #9aa5b1; --ink3: #5f6a76;
  --good: #46d17a; --lime: #b3d13b; --amber: #d9a13b; --orange: #e07b39; --bad: #e5544b;
  --link: #4cc2d9;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0 auto; max-width: 920px; padding: 3.2rem 1.2rem 4rem;
  background:
    radial-gradient(1100px 420px at 50% -160px, rgba(70, 209, 122, .07), transparent 65%),
    radial-gradient(rgba(255,255,255,.045) 1px, transparent 1px) 0 0 / 26px 26px,
    var(--bg);
  color: var(--ink); font: 15px/1.6 var(--sans);
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
code { font-family: var(--mono); font-size: .86em; background: var(--inset);
       border: 1px solid var(--line); padding: .08rem .38rem; border-radius: 5px; }
.wordmark { font-family: var(--mono); font-weight: 600; font-size: 2rem;
            letter-spacing: -.03em; margin: 0; }
.wordmark .cursor { display: inline-block; width: .55em; height: 1.05em; margin-left: .12em;
                    background: var(--good); vertical-align: text-bottom;
                    animation: blink 1.15s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.tagline { color: var(--ink2); margin: .5rem 0 0; max-width: 640px; }
.statstrip { display: flex; flex-wrap: wrap; gap: 1.6rem; margin: 1.6rem 0 0;
             font-family: var(--mono); font-size: .74rem; color: var(--ink3);
             text-transform: uppercase; letter-spacing: .08em; }
.statstrip b { display: block; color: var(--ink); font-size: 1.15rem; letter-spacing: 0; }
.cta { margin: 1.5rem 0 0; }
.cta a { display: inline-block; font-family: var(--mono); font-size: .8rem;
         color: var(--good); border: 1px solid rgba(70,209,122,.45); border-radius: 7px;
         padding: .45rem 1rem; background: rgba(70,209,122,.07); }
.cta a:hover { background: rgba(70,209,122,.16); text-decoration: none; }
.card { position: relative; overflow: hidden; background: var(--card);
        border: 1px solid var(--line); border-radius: 14px;
        padding: 1.4rem 1.5rem 1.25rem; margin: 1.4rem 0;
        display: grid; grid-template-columns: 96px 1fr; gap: 1.3rem;
        animation: rise .55s cubic-bezier(.2,.7,.2,1) both; }
@keyframes rise { from { opacity: 0; transform: translateY(14px); } }
.ghostrank { position: absolute; top: -.55rem; right: .4rem; font-family: var(--mono);
             font-weight: 600; font-size: 3.6rem; color: rgba(255,255,255,.05);
             user-select: none; }
.gaugewrap { display: flex; flex-direction: column; align-items: center; gap: .45rem; }
.gaugelabel { font-family: var(--mono); font-size: .62rem; letter-spacing: .12em;
              color: var(--ink3); text-transform: uppercase; }
.gauge text { font-family: var(--mono); font-weight: 600; }
.arc { animation: arc 1s .25s cubic-bezier(.3,.8,.3,1) both; }
@keyframes arc { from { stroke-dashoffset: var(--c); } to { stroke-dashoffset: var(--o); } }
.sdk { margin: 0; font-family: var(--mono); font-weight: 600; font-size: 1.3rem;
       letter-spacing: -.02em; }
.url { margin: .15rem 0 .7rem; font-size: .8rem; font-family: var(--mono); }
.cps { display: flex; flex-wrap: wrap; align-items: center; margin: 0 0 .8rem; }
.cpseg { font-family: var(--mono); font-size: .72rem; padding: .16rem .55rem;
         border-radius: 6px; border: 1px solid; white-space: nowrap; }
.cpseg.ok { color: var(--good); border-color: rgba(70,209,122,.4); background: rgba(70,209,122,.07); }
.cpseg.no { color: var(--bad); border-color: rgba(229,84,75,.45); background: rgba(229,84,75,.08); }
.cx { width: 12px; height: 1px; background: var(--line2); }
.summary { margin: 0 0 .75rem; color: var(--ink); }
.summary b { font-family: var(--mono); font-size: .82em; text-transform: uppercase;
             letter-spacing: .06em; }
.frictionhead { font-family: var(--mono); font-size: .68rem; letter-spacing: .12em;
                text-transform: uppercase; color: var(--amber); margin: 0 0 .3rem; }
.friction { margin: 0 0 .8rem; padding: 0; list-style: none; }
.friction li { position: relative; padding: .18rem 0 .18rem 1.15rem; font-size: .86rem;
               color: var(--ink2); }
.friction li::before { content: "▸"; position: absolute; left: 0; color: var(--amber); }
.friction b { color: var(--ink); font-weight: 500; }
.meta { color: var(--ink3); font-size: .76rem; font-family: var(--mono); margin: 0; }
.badgebar { display: flex; flex-wrap: wrap; align-items: center; gap: .7rem; margin-top: .65rem; }
.badgebar img { height: 20px; display: block; }
.copybtn { font-family: var(--mono); background: var(--inset); color: var(--ink2);
           border: 1px solid var(--line); border-radius: 6px; font-size: .72rem;
           padding: .18rem .6rem; cursor: pointer; }
.copybtn:hover { color: var(--ink); border-color: var(--ink3); }
.hist { margin-left: auto; display: flex; align-items: center; gap: .5rem;
        color: var(--ink3); font-size: .72rem; font-family: var(--mono); }
footer { margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--line);
         font-family: var(--mono); font-size: .72rem; color: var(--ink3); line-height: 2; }
.note { color: var(--amber); font-style: italic; margin: .6rem 0; padding: .5rem .8rem;
        border-left: 2px solid var(--amber); background: rgba(217,161,59,.05); }
.step { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
        padding: .55rem .85rem; margin: .6rem 0; }
.step summary { cursor: pointer; font-family: var(--mono); font-size: .84rem; }
pre { background: var(--inset); border: 1px solid var(--line); border-radius: 8px;
      padding: .7rem; overflow-x: auto; font: .78rem/1.5 var(--mono); white-space: pre-wrap; }
@media (max-width: 640px) {
  .card { grid-template-columns: 1fr; }
  .gaugewrap { flex-direction: row; }
  .hist { margin-left: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .card, .arc, .cursor { animation: none !important; }
}
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def score_color(total: int) -> str:
    if total >= 85:
        return "#46d17a"
    if total >= 70:
        return "#b3d13b"
    if total >= 50:
        return "#d9a13b"
    if total >= 30:
        return "#e07b39"
    return "#e5544b"


def badge_color(total: int) -> str:
    if total >= 85:
        return "brightgreen"
    if total >= 70:
        return "green"
    if total >= 50:
        return "yellow"
    if total >= 30:
        return "orange"
    return "red"


def gauge(total: int) -> str:
    """Calibration-dial score ring; arc draws in on load."""
    r, size = 40, 96
    c = 2 * 3.14159 * r
    off = c * (1 - total / 100)
    color = score_color(total)
    return f"""<svg class="gauge" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <circle cx="48" cy="48" r="{r}" fill="none" stroke="#1b202a" stroke-width="6"/>
  <circle class="arc" cx="48" cy="48" r="{r}" fill="none" stroke="{color}" stroke-width="6"
    stroke-linecap="round" stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}"
    style="--c:{c:.1f};--o:{off:.1f}" transform="rotate(-90 48 48)"/>
  <text x="48" y="46" text-anchor="middle" font-size="24" fill="{color}">{total}</text>
  <text x="48" y="63" text-anchor="middle" font-size="10" fill="#5f6a76">/100</text>
</svg>"""


def load_history() -> dict[str, list[dict]]:
    hist: dict[str, list[dict]] = {}
    if HISTORY.exists():
        for line in HISTORY.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                hist.setdefault(e["name"], []).append(e)
    for entries in hist.values():
        entries.sort(key=lambda e: e.get("started", ""))
    return hist


def sparkline(entries: list[dict]) -> str:
    """Score-history sparkline: one series, one hue, dots ringed with the surface color."""
    if not entries:
        return ""
    points = [e["score"] for e in entries]
    w, h = 120, 28
    xs = [w // 2] if len(points) == 1 else \
        [4 + round(i * (w - 8) / (len(points) - 1)) for i in range(len(points))]
    ys = [h - 4 - round(p / 100 * (h - 8)) for p in points]
    line = ""
    if len(points) > 1:
        pts = " ".join(f"{x},{y}" for x, y in zip(xs, ys))
        line = f'<polyline points="{pts}" fill="none" stroke="#46d17a" stroke-width="2"/>'
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="3" fill="#46d17a" stroke="#12151b" stroke-width="2">'
        f'<title>{e["started"][:16].replace("T", " ")}Z — {e["score"]}/100</title></circle>'
        for x, y, e in zip(xs, ys, entries))
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="score history for this SDK">{line}{dots}</svg>')


def load_results() -> list[dict]:
    results = []
    for path in sorted(RUNS.glob("*/result.json")):
        results.append(json.loads(path.read_text()))
    return sorted(results, key=lambda r: -r["score"])


def write_badges(results: list[dict]) -> None:
    for r in results:
        badge = {"schemaVersion": 1, "label": "agent-ready",
                 "message": f"{r['score']}/100", "color": badge_color(r["score"])}
        (SITE / f"badge-{r['name']}.json").write_text(json.dumps(badge))


def render_log_pages(results: list[dict]) -> None:
    """A human-readable step timeline per run, next to the raw JSONL."""
    for r in results:
        tpath = RUNS / r["name"] / "transcript.jsonl"
        if not tpath.exists():
            continue
        events = [json.loads(l) for l in tpath.read_text().splitlines() if l.strip()]
        blocks = []
        for e in events:
            if e["kind"] == "assistant":
                blocks.append(f'<div class="note">{esc(e.get("text", ""))}</div>')
                continue
            try:
                a = json.loads(e.get("args") or "{}")
                shown = a.get("command") or a.get("path") or a.get("url") or ""
            except Exception:
                shown = e.get("args", "")
            blocks.append(
                f'<details class="step" open><summary>#{e.get("step", "·")} '
                f'<b>{esc(e.get("tool", ""))}</b> <code>{esc(str(shown)[:140])}</code></summary>'
                f'<pre>{esc(e.get("output", ""))}</pre></details>')

        page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-ready — {r['name']} run log</title>
{FONT_LINKS}
<style>{BASE_CSS}</style></head><body>
<h1 class="wordmark"><a href="index.html" style="color:inherit">agent-ready</a> · {r['name']}
<span style="color:{score_color(r['score'])}">{r['score']}/100</span></h1>
<p class="meta" style="margin:.6rem 0 1.4rem">{r.get('steps', '?')} steps ·
{r.get('wall_seconds', '?')}s · agent <code>{esc((r.get('agent_model') or 'unknown').split('/')[-1])}</code> ·
<a href="{REPO}/blob/main/runs/{r['name']}/transcript.jsonl">raw JSONL</a></p>
{''.join(blocks)}
</body></html>"""
        (SITE / f"log-{r['name']}.html").write_text(page)


def render_index(results: list[dict], hist: dict[str, list[dict]]) -> None:
    rows = []
    for rank, r in enumerate(results, 1):
        cps = []
        for i, (name, desc) in enumerate(CHECKPOINTS):
            if i:
                cps.append('<i class="cx"></i>')
            ok = r["checkpoints"][name]["passed"]
            cps.append(f'<span class="cpseg {"ok" if ok else "no"}" title="{esc(desc)} '
                       f'(weight {WEIGHTS[name]})">{"✓" if ok else "✕"} {name}</span>')
        friction = "".join(f"<li><b>{esc(f.get('where', ''))}</b>: {esc(f.get('detail', ''))}</li>"
                           for f in r.get("friction", []))
        endpoint = urllib.parse.quote(f"{PAGES}/badge-{r['name']}.json", safe="")
        shield = f"https://img.shields.io/endpoint?url={endpoint}&label={r['name']}"
        md = f"[![agent-ready: {r['name']}]({shield})]({PAGES}/)"
        entries = hist.get(r["name"], [])
        rows.append(f"""
        <section class="card" style="animation-delay:{rank * 80}ms">
          <span class="ghostrank">{rank:02d}</span>
          <div class="gaugewrap">{gauge(r['score'])}<span class="gaugelabel">agent-ready</span></div>
          <div>
            <h2 class="sdk">{r['name']}</h2>
            <p class="url"><a href="{r['url']}">{r['url']}</a></p>
            <div class="cps">{''.join(cps)}</div>
            <p class="summary"><b>{r['outcome']}</b> — {esc(r['summary'])}</p>
            <p class="frictionhead">friction report</p>
            <ul class="friction">{friction}</ul>
            <p class="meta">agent <code>{esc((r.get('agent_model') or 'unknown').split('/')[-1])}</code>
               · {r.get('steps', '?')} steps · {r.get('wall_seconds', '?')}s · {r.get('started', '')[:10]}
               · <a href="log-{r['name']}.html">readable log</a>
               · <a href="{REPO}/blob/main/runs/{r['name']}/transcript.jsonl">raw transcript</a>
               · <a href="{REPO}/blob/main/runs/{r['name']}/result.json">result.json</a></p>
            <div class="badgebar">
              <a href="{PAGES}/badge-{r['name']}.json"><img src="{shield}" alt="agent-ready badge for {r['name']}"></a>
              <button class="copybtn" data-md="{md}">copy badge markdown</button>
              <span class="hist">{sparkline(entries)}{len(entries)} run(s)</span>
            </div>
          </div>
        </section>""")

    n_runs = sum(len(v) for v in hist.values())
    median = int(statistics.median([r["score"] for r in results])) if results else 0
    updated = max((r.get("started", "") for r in results), default="")[:10]

    html_page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-ready — can a clean agent finish your quickstart?</title>
{FONT_LINKS}
<style>{BASE_CSS}</style></head><body>
<h1 class="wordmark">agent-ready<span class="cursor"></span></h1>
<p class="tagline">Can a clean agent finish your quickstart? A pristine Daytona sandbox, an
autonomous agent, and Braintrust-scored checkpoints. No pretending — every pass is backed
by command output.</p>
<div class="statstrip">
  <span>SDKs tested<b>{len(results):02d}</b></span>
  <span>runs logged<b>{n_runs:02d}</b></span>
  <span>median score<b>{median}</b></span>
  <span>updated<b>{updated}</b></span>
</div>
<p class="cta"><a href="{REPO}/issues/new?title=Run%20request%3A%20%3Cyour%20SDK%3E&body=Quickstart%20URL%3A%20%0APromised%20outcome%3A%20%0AAnything%20we%20should%20know%3A%20">
Want your SDK on this board? Request a run →</a></p>
{''.join(rows) if rows else '<p>No runs yet.</p>'}
<footer>
  checkpoints: env_ready 10 · installed 20 · configured 15 · first_call 25 · verified 30
  <br>every run = one fresh sandbox + one scored Braintrust eval · history is append-only
  <br><a href="{REPO}">github.com/zhannur/agent-ready</a> · built solo at Daytona HackSprint w/ Braintrust · SF · July 2026
</footer>
<script>
document.querySelectorAll('.copybtn').forEach(b => b.addEventListener('click', async () => {{
  try {{ await navigator.clipboard.writeText(b.dataset.md); }} catch (e) {{}}
  const t = b.textContent; b.textContent = 'copied!';
  setTimeout(() => b.textContent = t, 1200);
}}));
</script>
</body></html>"""
    (SITE / "index.html").write_text(html_page)


def build_site() -> None:
    SITE.mkdir(exist_ok=True)
    results = load_results()
    hist = load_history()
    write_badges(results)
    render_log_pages(results)
    render_index(results, hist)
    print(f"{SITE}/index.html built with {len(results)} run(s), "
          f"{sum(len(v) for v in hist.values())} history point(s)")
