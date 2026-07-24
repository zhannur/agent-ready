"""Render run results into the scoreboard site + shields.io badge endpoints."""
from __future__ import annotations

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


def render_index(results: list[dict]) -> None:
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
             · <a href="{REPO}/blob/main/runs/{r['name']}/transcript.jsonl">full transcript</a>
             · <a href="{REPO}/blob/main/runs/{r['name']}/result.json">result.json</a></p>
          <div class="badgebar">
            <a href="{PAGES}/badge-{r['name']}.json"><img src="{shield}" alt="agent-ready badge for {r['name']}"></a>
            <button class="copybtn" data-md="{md}">copy badge markdown</button>
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
    write_badges(results)
    render_index(results)
    print(f"{SITE}/index.html built with {len(results)} run(s)")
