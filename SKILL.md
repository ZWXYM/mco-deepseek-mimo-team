---
name: mco-deepseek-mimo-team
description: Lead local Claude Code workers through MCO and CC Switch with an active DeepSeek or Xiaomi MiMo route on Windows, macOS, or Linux.
---

# Codex-led MCO workers

Use this skill when the user asks Codex to delegate work to the local DeepSeek or Xiaomi MiMo route. Codex owns the task, acceptance criteria, stage gates, and final verification. Workers can plan, implement, test, review, and repair. Keep routine worker analysis in their artifacts; bring only compact results and decisive evidence into Codex's context. If the `mco-cli` skill is installed, read it for native MCO modes beyond this helper.

## Routing and concurrency

- Only **one provider** may work at a time: DeepSeek or Xiaomi MiMo. Multiple workers and model variants of that selected provider may run concurrently. Never switch CC Switch while a worker is active. Use one persistent `--work-dir` for all workers so the helper can detect active tasks from the other provider.
- Run `team.py routes` with the Python interpreter that has `psutil` installed before dispatch. It reads the active CC Switch Claude provider and live Claude model aliases, reporting model names only. MiMo is optional: a DeepSeek-only installation works when DeepSeek is active. Do not print or copy credentials. Pass the selected name as `--expected-provider` to `start`; the command rejects provider drift.
- Prefer a configured `[1M]` variant when the same model name has both ordinary and `[1M]` choices. The helper sorts `[1M]` first within a role. Choose Pro, Flash, or Ultraspeed by the job rather than fixed roles. The model string and a successful short call do not prove usable context capacity; verify long-context behavior separately when it matters.
- Mappings can change. Re-read `routes` each session. Validate each configured route with a small task before relying on it for substantive work.

## Dispatch and control loop

1. Define each worker's distinct objective, input paths, expected artifact, and acceptance checks in its own UTF-8 prompt file. Workers do not inherit this chat. Briefly tell the user which jobs are being dispatched. Prefer separate MCO invocations when prompts differ; one ordinary MCO call with several `--agent` entries gives them the same prompt.
2. Start each worker with `scripts/team.py start`. Use `--mode read_only` for analysis or review and `--mode write` only for requested implementation. Parallel writers need separate worktrees or non-overlapping files. The helper launches MCO in the background, saves JSONL events, diagnostics, metadata, and MCO artifacts, and returns a task ID. Commands and examples are in [references/operations.md](references/operations.md).
3. Call `status` during execution. Check task state, invocation state, elapsed time, process/child count, provider drift, and raw output size. A running process with zero output can be normal because Claude/MCO may buffer text until the invocation finishes. Status shows observable progress, not the worker's internal reasoning. Investigate a stale task against its deadline, diagnostics, and raw logs; do not call it successful based on a live PID.
4. On completion, call `result`; read `run.json` and the output artifact, or use `--include-answer` only when the response is short. Require `task_finished=complete` and each required invocation `success`. A timed-out invocation can leave persuasive raw stdout, sometimes after the deadline; treat it as partial, unverified evidence and rerun or independently check it.
5. Give an independent same-provider worker the original task, the first worker's output, source files, and acceptance criteria. `review-prompt` creates a contextual review prompt from an existing task. The reviewer must reproduce material claims and give a likely cause plus concrete investigation or repair direction for errors. Send actionable findings to a writer for correction; recheck affected criteria. Codex spot-checks decisive evidence and resolves disagreements. A worker's PASS alone is not proof.

## Local MiMo Pro behavior and failure handling

- On MCO 0.11.0, a MiMo Pro `[1M]` review timed out at the default 180-second hard deadline although raw output appeared just after it. The same style of task completed successfully with a 420-second deadline; use an explicit larger `--timeout` for substantive Pro work (the helper defaults to 600 seconds). Tune to task size, inspect status, and do not extend indefinitely without evidence.
- The tested Windows MCO 0.11.0 installation needed compatibility fixes: native `claude.exe` launch, explicit `--model` forwarding, `os.getuid` fallback, and process-tree cancellation with `taskkill`. The Windows patch script is not needed on macOS or Linux. npm updates may overwrite local patches. If startup, model selection, or cancellation fails, inspect the installed MCO adapter before retrying; see [references/operations.md](references/operations.md).
- If the route rejects Claude Code's advisor tool with `advisor_20260301` or HTTP 422, try `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` for a test process. Do not set it globally without evidence.
- In local MCO 0.11.0 testing, `--chain --synthesize` together produced chain artifacts but no synthesis artifact. When both are needed, run them as separate stages and check saved stage files.

Keep worker count proportional to the task. Continue review and repair until acceptance criteria are met or a concrete blocker is identified, then report actual outcomes and limits.
