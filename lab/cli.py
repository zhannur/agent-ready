"""agent-ready CLI: run acceptance runs and build the scoreboard site."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_env(spec: dict[str, str] | None) -> dict[str, str]:
    """Target sandbox_env values starting with $ pull from the host environment."""
    resolved = {}
    for key, value in (spec or {}).items():
        actual = os.environ.get(value[1:], "") if str(value).startswith("$") else str(value)
        if not actual:
            print(f"  ! {key} is empty on host — injecting nothing for it")
            continue
        resolved[key] = actual
    return resolved


def cmd_run(target_path: str, keep_sandbox: bool) -> None:
    from .agent import run_agent
    from .checkpoints import judge_run, log_to_braintrust, score
    from .sandbox import LabSandbox

    target = yaml.safe_load(Path(target_path).read_text())
    name, url = target["name"], target["quickstart_url"]
    promised = target["promised_output"]
    inject = resolve_env(target.get("sandbox_env"))

    run_dir = Path("runs") / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "transcript.jsonl").write_text("")

    sandbox = LabSandbox(inject_env=inject)
    try:
        print(f"== {name}: creating pristine sandbox")
        sandbox.create()
        print(f"== {name}: agent attempting {url}")
        outcome = run_agent(name, url, promised, sandbox, inject, run_dir)
    finally:
        if keep_sandbox:
            print("== keeping sandbox alive (--keep-sandbox)")
        else:
            sandbox.destroy()

    print(f"== {name}: judging transcript ({outcome['steps']} steps)")
    verdict = judge_run(promised, outcome["events"])
    total = score(verdict["checkpoints"])
    span_id = log_to_braintrust(name, url, outcome, verdict["checkpoints"],
                                verdict["friction_points"], total)

    from .agent import model_name
    result = {"name": name, "url": url, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "agent_model": model_name(), "judge_model": model_name(),
              "outcome": outcome["outcome"], "summary": outcome["summary"],
              "deviations": outcome.get("deviations", ""), "steps": outcome["steps"],
              "wall_seconds": outcome["wall_seconds"], "checkpoints": verdict["checkpoints"],
              "friction": verdict["friction_points"], "score": total,
              "braintrust_span": span_id}
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    with (Path("runs") / "history.jsonl").open("a") as f:
        f.write(json.dumps({"name": name, "started": result["started"], "score": total,
                            "outcome": result["outcome"], "steps": result["steps"],
                            "wall_seconds": result["wall_seconds"],
                            "agent_model": result["agent_model"],
                            "braintrust_span": span_id}) + "\n")
    print(f"== {name}: agent-ready score {total}/100 → {run_dir}/result.json")


def cmd_site() -> None:
    from .report import build_site
    build_site()


def cmd_all(keep_sandbox: bool) -> None:
    for target in sorted(Path("targets").glob("*.yaml")):
        try:
            cmd_run(str(target), keep_sandbox)
        except Exception as e:
            print(f"!! {target.name} failed: {e}")
    cmd_site()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="agent-ready")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run one acceptance target")
    p_run.add_argument("target")
    p_run.add_argument("--keep-sandbox", action="store_true")

    sub.add_parser("site", help="build the scoreboard site from runs/")

    p_all = sub.add_parser("all", help="run every target then build the site")
    p_all.add_argument("--keep-sandbox", action="store_true")

    args = parser.parse_args()
    if args.cmd == "run":
        cmd_run(args.target, args.keep_sandbox)
    elif args.cmd == "site":
        cmd_site()
    elif args.cmd == "all":
        cmd_all(args.keep_sandbox)


if __name__ == "__main__":
    main()
