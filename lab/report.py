"""Render run results into the scoreboard site + shields.io badge endpoints."""
from __future__ import annotations

import html
import json
import urllib.parse
from pathlib import Path

from .checkpoints import CHECKPOINTS, WEIGHTS

SITE = Path("docs")
RUNS = Path("runs")
REPO = "https://github.com/zhannur/agent-ready"
PAGES = "https://zhannur.github.io/agent-ready"


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


HISTORY = Path("runs/history.jsonl")


def esc(s) -> str:
    return html.escape(str(s), quote=True)


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
        line = f'<polyline points="{pts}" fill="none" stroke="#3fb950" stroke-width="2"/>'
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="3" fill="#3fb950" stroke="#161b22" stroke-width="2">'
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
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0 auto; max-width: 880px; padding: 2rem 1rem 4rem;
         background: #0d1117; color: #e6edf3;
         font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif; }}
  h1 {{ font-size: 1.4rem; }} h1 a {{ color: #58a6ff; text-decoration: none; }}
  .sub {{ color: #8b949e; }}
  .step {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px;
          padding: .5rem .8rem; margin: .6rem 0; }}
  .step summary {{ cursor: pointer; }}
  .note {{ color: #d29922; font-style: italic; margin: .6rem 0; padding: .5rem .8rem;
          border-left: 3px solid #d29922; }}
  pre {{ background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
        padding: .7rem; overflow-x: auto; font-size: .8rem; white-space: pre-wrap; }}
  code {{ background: #21262d; padding: .1rem .35rem; border-radius: 6px; font-size: .85em; }}
</style></head><body>
<h1><a href="index.html">agent-ready</a> · {r['name']} — {r['score']}/100</h1>
<p class="sub">{r.get('steps', '?')} steps · {r.get('wall_seconds', '?')}s ·
agent <code>{esc((r.get('agent_model') or 'unknown').split('/')[-1])}</code> ·
<a href="{REPO}/blob/main/runs/{r['name']}/transcript.jsonl" style="color:#58a6ff">raw JSONL</a></p>
{''.join(blocks)}
</body></html>"""
        (SITE / f"log-{r['name']}.html").write_text(page)


def render_index(results: list[dict], hist: dict[str, list[dict]]) -> None:
    rows = []
    for rank, r in enumerate(results, 1):
        pills = "".join(
            f'<span class="pill {"ok" if r["checkpoints"][name]["passed"] else "no"}" '
            f'title="{desc}">{name}</span>'
            for name, desc in CHECKPOINTS)
        friction = "".join(f"<li><b>{f.get('where', '')}</b>: {f.get('detail', '')}</li>"
                           for f in r.get("friction", []))
        endpoint = urllib.parse.quote(f"{PAGES}/badge-{r['name']}.json", safe="")
        shield = f"https://img.shields.io/endpoint?url={endpoint}&label={r['name']}"
        md = f"[![agent-ready: {r['name']}]({shield})]({PAGES}/)"
        rows.append(f"""
        <section class="card">
          <div class="head">
            <span class="rank">#{rank}</span>
            <h2>{r['name']}</h2>
            <span class="score s-{badge_color(r['score'])}">{r['score']}<small>/100</small></span>
          </div>
          <p class="url"><a href="{r['url']}">{r['url']}</a></p>
          <div class="pills">{pills}</div>
          <p class="summary"><b>{r['outcome']}</b> — {r['summary']}</p>
          <ul class="friction">{friction}</ul>
          <p class="meta">agent: <code>{(r.get('agent_model') or 'unknown').split('/')[-1]}</code>
             · {r.get('steps', '?')} steps · {r.get('wall_seconds', '?')}s · {r.get('started', '')[:10]}
             · <a href="log-{r['name']}.html">readable log</a>
             · <a href="{REPO}/blob/main/runs/{r['name']}/transcript.jsonl">raw transcript</a>
             · <a href="{REPO}/blob/main/runs/{r['name']}/result.json">result.json</a></p>
          <div class="badgebar">
            <a href="{PAGES}/badge-{r['name']}.json"><img src="{shield}" alt="agent-ready badge for {r['name']}"></a>
            <button class="copybtn" data-md="{md}">copy badge markdown</button>
            <span class="hist">{sparkline(hist.get(r['name'], []))}{len(hist.get(r['name'], []))} run(s)</span>
          </div>
        </section>""")

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-ready — can a clean agent finish your quickstart?</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0 auto; max-width: 880px; padding: 2rem 1rem 4rem;
         background: #0d1117; color: #e6edf3;
         font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, sans-serif; }}
  h1 {{ font-size: 1.9rem; margin-bottom: .2rem; }}
  .sub {{ color: #8b949e; margin-top: 0; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px;
          padding: 1.1rem 1.3rem; margin: 1.1rem 0; }}
  .head {{ display: flex; align-items: baseline; gap: .8rem; }}
  .head h2 {{ margin: 0; font-size: 1.25rem; flex: 1; }}
  .rank {{ color: #8b949e; }}
  .score {{ font-size: 1.5rem; font-weight: 700; }}
  .score small {{ color: #8b949e; font-size: .9rem; }}
  .s-brightgreen, .s-green {{ color: #3fb950; }}
  .s-yellow {{ color: #d29922; }} .s-orange {{ color: #f0883e; }} .s-red {{ color: #f85149; }}
  .pills {{ margin: .5rem 0; }}
  .pill {{ display: inline-block; margin: 0 .35rem .35rem 0; padding: .12rem .6rem;
          border-radius: 999px; font-size: .78rem; border: 1px solid #30363d; }}
  .pill.ok {{ background: #12261e; color: #3fb950; border-color: #238636; }}
  .pill.no {{ background: #2b1214; color: #f85149; border-color: #da3633; }}
  .url a {{ color: #58a6ff; text-decoration: none; font-size: .85rem; }}
  .summary {{ margin: .4rem 0; }}
  .friction {{ color: #d29922; font-size: .9rem; margin: .3rem 0 .4rem; padding-left: 1.2rem; }}
  .meta {{ color: #8b949e; font-size: .8rem; margin: 0; }}
  .meta a {{ color: #58a6ff; text-decoration: none; }}
  .badgebar {{ display: flex; align-items: center; gap: .7rem; margin-top: .55rem; }}
  .badgebar img {{ height: 20px; display: block; }}
  .copybtn {{ background: #21262d; color: #8b949e; border: 1px solid #30363d;
             border-radius: 6px; font-size: .75rem; padding: .15rem .6rem; cursor: pointer; }}
  .copybtn:hover {{ color: #e6edf3; border-color: #8b949e; }}
  .hist {{ margin-left: auto; display: flex; align-items: center; gap: .45rem;
          color: #8b949e; font-size: .75rem; }}
  code {{ background: #21262d; padding: .1rem .35rem; border-radius: 6px; }}
</style></head><body>
<h1>agent-ready</h1>
<p class="sub">Can a clean agent finish your quickstart? Fresh Daytona sandbox + autonomous
agent + Braintrust-scored checkpoints. No pretending — every pass is backed by command output.</p>
{''.join(rows) if rows else '<p>No runs yet.</p>'}
<script>
document.querySelectorAll('.copybtn').forEach(b => b.addEventListener('click', async () => {{
  try {{ await navigator.clipboard.writeText(b.dataset.md); }} catch (e) {{}}
  const t = b.textContent; b.textContent = 'copied!';
  setTimeout(() => b.textContent = t, 1200);
}}));
</script>
</body></html>"""
    (SITE / "index.html").write_text(html)


def build_site() -> None:
    SITE.mkdir(exist_ok=True)
    results = load_results()
    hist = load_history()
    write_badges(results)
    render_log_pages(results)
    render_index(results, hist)
    print(f"{SITE}/index.html built with {len(results)} run(s), "
          f"{sum(len(v) for v in hist.values())} history point(s)")
