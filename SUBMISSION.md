# agent-ready — Devpost submission

**Team name:** agent-ready
**Team:** Zhannur (solo)
**Repo:** https://github.com/zhannur/agent-ready
**Live scoreboard:** https://zhannur.github.io/agent-ready/

## Summary (2–3 sentences)

agent-ready answers one question every SDK team assumes but never tests: *can a clean
agent actually finish your public quickstart?* It boots a pristine Daytona sandbox, drops
in an autonomous agent (Fireworks-hosted Kimi K2.6) with only your quickstart URL, and
grades the attempt against five evidence-backed checkpoints logged as Braintrust evals —
producing a 0–100 Agent-Ready score, a friction report, and a README badge.

## The problem & impact

Developer onboarding is where SDK adoption dies quietly — and in 2026 the "developer"
hitting your quickstart is increasingly an AI agent in a sandbox. Today, in one
afternoon, agent-ready found real onboarding walls in three of the four sponsor
quickstarts it tested **at this hackathon**: a documented model ID that 404s, SDK code
samples calling methods that no longer exist, and a quickstart that can't complete
inside a common agent sandbox. Every finding is a fixable docs/DX bug, discovered autonomously in minutes for
cents, with transcript evidence attached. DX teams currently learn these things from
churned signups; agent-ready makes them a CI metric.

## Results (10 runs today, single model, identical rules)

| SDK | Latest | All runs | Headline finding |
|---|---|---|---|
| elevenlabs | **100/100** | 100, 100 | Perfect twice — docs ship copy-paste-true samples and an `/llms.txt` agent index; agent-ready by design |
| fireworks | 75/100 | 75, 75 | Docs' example model (`deepseek-v3p1`) is no longer deployed → first call 404s; the agent recovered via a self-written model-discovery script — both times |
| daytona | 70/100 | 70, 45, 70 | Quickstart samples call renamed SDK methods (`Process.execute`→`exec`, `CodeInterpreter.run`→`run_code`); nested sandbox creation itself worked |
| braintrust | 30/100 | 75, 0, 30 | `api.braintrust.dev` is unreachable from inside agent sandboxes and the offline workaround (`--no-send-logs`) is undocumented — the score depends on the agent rediscovering it, and that instability is itself the finding |

**We catch our own bad measurements — demonstrated live:** when two scores dipped between rounds, the
append-only history caught it, the transcripts attributed it — our account's disk quota
had been saturated by nested sandboxes the runs themselves created, not a docs change —
`lab cleanup` remediated it, and re-measurement reproduced daytona's baseline exactly
(70 → 45 → 70). Single runs lie; tracked history doesn't. That's why every run is a
scored Braintrust eval and every card ships a score-history sparkline.

## How it works

target.yaml (quickstart URL + promised outcome) → pristine **Daytona** sandbox →
autonomous agent (**Fireworks** Kimi K2.6; tools: bash / write_file / fetch_url / finish)
→ full transcript → strict evidence-based judge → five weighted checkpoints
(env_ready 10, installed 20, configured 15, first_call 25, verified 30) logged as scored
**Braintrust** evals → static scoreboard + shields.io badge endpoints on GitHub Pages.

Honesty is enforced structurally: a checkpoint passes only on real command output; the
agent must follow the vendor's own instructions and declare deviations; secrets are
redacted before anything is persisted; each run gets a fresh sandbox destroyed afterward.

## Sponsor tools used (all load-bearing)

- **Daytona** — one pristine, disposable sandbox per run; the clean-room guarantee IS the
  measurement. (Also the funniest run: an agent inside a Daytona sandbox creating another
  Daytona sandbox via their SDK.)
- **Fireworks AI** — hosts both the agent's brain (kimi-k2p6) and the checkpoint judge;
  every run is ~50–100 tool-calling completions.
- **Braintrust** — every run is a scored eval with per-checkpoint scores and evidence,
  making scores comparable across SDKs and across doc revisions over time.

## Key technical components

- Resilient tool loop: tool failures return to the agent as information (like a real
  developer session), never crash the run
- Evidence-strict LLM judge with friction-point extraction (the sellable report)
- Weighted checkpoint scoring → shields.io badge endpoint per SDK, with one-click
  embed-markdown copy on every card
- Honest budget handling: capped runs end with a model-written truthful account
- Append-only run history → per-SDK sparklines; human-readable log page per run
- GitHub Actions runner: nightly docs-regression sweep over all targets + on-demand
  `workflow_dispatch` runs (name + quickstart URL in, scored card out), with sandbox
  cleanup baked into every batch

## What's next

Model-matrix runs (is your quickstart agent-ready for K2-class, GPT-class, small
models?), environment matrices (which sandboxes can your users' agents actually reach
you from?), and signed vendor-neutral reports. Scheduled re-runs already ship — the
nightly sweep re-grades every target and the board updates itself.
