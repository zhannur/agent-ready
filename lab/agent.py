"""The clean-room developer agent: a tool loop over Fireworks chat completions."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx
from openai import OpenAI

from .sandbox import LabSandbox

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_MODEL = "accounts/fireworks/models/kimi-k2-instruct"
MAX_STEPS = 40
WALL_LIMIT_S = 1500
TOOL_OUTPUT_CAP = 6000

SYSTEM_PROMPT = """\
You are a developer who has just been handed a link to a vendor's public quickstart.
You are working in a brand-new Linux sandbox: assume nothing is installed or configured.
Your mission is to complete the quickstart end-to-end, exactly as written, until the
promised outcome demonstrably works: {promised_output}

Ground rules:
- fetch_url the quickstart page first and follow the vendor's own instructions. Note in
  finish() anywhere you had to deviate from the docs to make things work.
- Everything happens inside the sandbox via bash/write_file. No pretending: a step only
  counts when real command output proves it ran.
- Credentials already exported in the sandbox environment: {env_names}. Use them where
  the quickstart asks for keys. Never print their values.
- When the promised outcome is verified — or you are honestly stuck — call finish() with
  an accurate account of how far you got and what broke.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "bash",
        "description": "Run a shell command in the sandbox. Returns exit code and output.",
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write a file into the sandbox.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                      "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "fetch_url",
        "description": "Fetch a web page (e.g. the quickstart docs) and return its readable text.",
        "parameters": {"type": "object",
                       "properties": {"url": {"type": "string"}},
                       "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "End the run with an honest outcome report.",
        "parameters": {"type": "object",
                       "properties": {"outcome": {"type": "string",
                                                  "enum": ["verified", "partial", "stuck"]},
                                      "summary": {"type": "string"},
                                      "deviations": {"type": "string"}},
                       "required": ["outcome", "summary"]}}},
]

_TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)


def fireworks_client() -> OpenAI:
    return OpenAI(base_url=FIREWORKS_BASE_URL, api_key=os.environ["FIREWORKS_API_KEY"])


def model_name() -> str:
    return os.environ.get("FIREWORKS_MODEL", DEFAULT_MODEL)


def fetch_readable(url: str) -> str:
    html = httpx.get(url, follow_redirects=True, timeout=30).text
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text[:60_000]


class Redactor:
    """Scrub injected secret values from anything that gets persisted."""

    def __init__(self, secrets: list[str]):
        self._secrets = [s for s in secrets if s and len(s) > 5]

    def __call__(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "***REDACTED***")
        return text


def run_agent(name: str, quickstart_url: str, promised_output: str,
              sandbox: LabSandbox, inject_env: dict[str, str],
              run_dir: Path) -> dict:
    """Drive the agent until finish(), step cap, or wall clock. Returns the outcome dict."""
    client = fireworks_client()
    redact = Redactor(list(inject_env.values()))
    transcript_path = run_dir / "transcript.jsonl"
    events: list[dict] = []

    def record(kind: str, **fields):
        event = {"t": round(time.time(), 2), "kind": kind, **fields}
        events.append(event)
        with transcript_path.open("a") as f:
            f.write(json.dumps(event) + "\n")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            promised_output=promised_output,
            env_names=", ".join(inject_env) or "(none needed)")},
        {"role": "user", "content": f"Quickstart URL: {quickstart_url}\n"
                                    f"Promised outcome to verify: {promised_output}\nBegin."},
    ]

    started = time.time()
    outcome = {"outcome": "stuck", "summary": "run ended without finish()", "deviations": ""}

    for step in range(1, MAX_STEPS + 1):
        if time.time() - started > WALL_LIMIT_S:
            outcome["summary"] = f"wall-clock budget exhausted at step {step}"
            break

        resp = client.chat.completions.create(
            model=model_name(), messages=messages, tools=TOOLS, temperature=0.2)
        msg = resp.choices[0].message

        if msg.content:
            record("assistant", text=redact(msg.content))
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({"role": "user",
                             "content": "Continue using tools; call finish() when done."})
            continue

        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})

        finished = False
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool = tc.function.name

            if tool == "bash":
                code, out = sandbox.run(args.get("command", ""), timeout=240)
                result = f"exit={code}\n{out}"
            elif tool == "write_file":
                sandbox.write_file(args.get("path", "/tmp/unnamed"), args.get("content", ""))
                result = f"wrote {args.get('path')} ({len(args.get('content', ''))} bytes)"
            elif tool == "fetch_url":
                try:
                    result = fetch_readable(args.get("url", ""))
                except Exception as e:
                    result = f"fetch failed: {e}"
            elif tool == "finish":
                outcome = {"outcome": args.get("outcome", "stuck"),
                           "summary": args.get("summary", ""),
                           "deviations": args.get("deviations", "")}
                result = "run finished"
                finished = True
            else:
                result = f"unknown tool {tool}"

            result = redact(str(result))
            record("tool", step=step, tool=tool,
                   args=redact(json.dumps(args))[:2000], output=result[:TOOL_OUTPUT_CAP])
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": result[:TOOL_OUTPUT_CAP]})
        if finished:
            break

    outcome["steps"] = len([e for e in events if e["kind"] == "tool"])
    outcome["wall_seconds"] = round(time.time() - started, 1)
    outcome["events"] = events
    return outcome
