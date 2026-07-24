"""Score a run transcript into acceptance checkpoints; log the run to Braintrust."""
from __future__ import annotations

import json
import re

from .agent import fireworks_client, model_name

CHECKPOINTS = [
    ("env_ready", "The toolchain the quickstart needs was installed/ready (runtime, package manager)"),
    ("installed", "The vendor's SDK or CLI was installed successfully"),
    ("configured", "Credentials/config were wired the way the quickstart instructs"),
    ("first_call", "The first API call or core action succeeded"),
    ("verified", "The quickstart's promised output was produced and verified"),
]
WEIGHTS = {"env_ready": 10, "installed": 20, "configured": 15, "first_call": 25, "verified": 30}

JUDGE_PROMPT = """\
You are grading whether an autonomous agent completed a vendor quickstart inside a clean sandbox.
Below is the run transcript (commands, outputs, agent notes). Judge STRICTLY from evidence in
the transcript — claimed success without command output proving it is a fail.

Promised outcome for this quickstart: {promised_output}

For each checkpoint, decide passed true/false and cite one line of evidence.
Also list up to 5 friction_points: concrete places a first-time developer would bleed time
(missing prerequisite, wrong command in docs, unclear auth step, version drift...), each with
a short quote from the transcript.

Checkpoints: {checkpoint_defs}

Reply with ONLY a JSON object:
{{"checkpoints": {{"<name>": {{"passed": bool, "evidence": "..."}}}},
  "friction_points": [{{"where": "...", "detail": "..."}}]}}

Transcript:
{transcript}
"""


def transcript_text(events: list[dict], cap: int = 40_000) -> str:
    lines = []
    for e in events:
        if e["kind"] == "assistant":
            lines.append(f"[agent] {e['text'][:1500]}")
        else:
            lines.append(f"[{e.get('tool')}] args={e.get('args', '')[:500]}\n{e.get('output', '')[:2000]}")
    text = "\n".join(lines)
    return text[-cap:]


def judge_run(promised_output: str, events: list[dict]) -> dict:
    client = fireworks_client()
    prompt = JUDGE_PROMPT.format(
        promised_output=promised_output,
        checkpoint_defs=json.dumps(dict(CHECKPOINTS)),
        transcript=transcript_text(events))
    resp = client.chat.completions.create(
        model=model_name(), temperature=0,
        messages=[{"role": "user", "content": prompt}])
    raw = resp.choices[0].message.content or "{}"
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        parsed = json.loads(match.group(0) if match else raw)
    except json.JSONDecodeError:
        parsed = {"checkpoints": {}, "friction_points": [{"where": "judge", "detail": "unparseable judge output"}]}

    checks = {}
    for cp_name, _ in CHECKPOINTS:
        entry = parsed.get("checkpoints", {}).get(cp_name, {})
        checks[cp_name] = {"passed": bool(entry.get("passed")), "evidence": str(entry.get("evidence", ""))[:500]}
    return {"checkpoints": checks, "friction_points": parsed.get("friction_points", [])[:5]}


def score(checks: dict) -> int:
    return sum(WEIGHTS[name] for name, c in checks.items() if c["passed"])


def log_to_braintrust(target_name: str, quickstart_url: str, outcome: dict,
                      checks: dict, friction: list, total: int) -> str | None:
    """Log the run as a scored eval; returns a permalink-ish id or None if logging failed."""
    try:
        import braintrust
        logger = braintrust.init_logger(project="agent-ready")
        with logger.start_span(name=target_name, type="eval") as span:
            span.log(
                input={"quickstart_url": quickstart_url},
                output={"outcome": outcome["outcome"], "summary": outcome["summary"],
                        "deviations": outcome.get("deviations", ""), "friction": friction},
                scores={**{f"cp_{k}": (1.0 if v["passed"] else 0.0) for k, v in checks.items()},
                        "agent_ready": total / 100.0},
                metadata={"steps": outcome.get("steps"), "wall_seconds": outcome.get("wall_seconds")})
            return getattr(span, "id", None)
    except Exception as e:
        print(f"  ! braintrust logging failed: {e}")
        return None
