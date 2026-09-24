# Local operations

Use the Python interpreter that has `psutil` installed. Keep one persistent work directory per project, including across provider switches. MiMo and DeepSeek must never have overlapping active tasks. Select only the provider that is configured and active in CC Switch; the other provider is optional.

## Windows PowerShell

```powershell
$skill = Join-Path $HOME '.codex\skills\mco-deepseek-mimo-team'
$py = Join-Path $skill '.venv\Scripts\python.exe'
$team = Join-Path $skill 'scripts\team.py'
mco --version
mco doctor --json
& $py $team routes
& $py $team start --repo . --work-dir work\mco-team --prompt-file work\mco-team\implementation.md --role pro --expected-provider DeepSeek --mode write --alias implementer --timeout 600 --task-id implement-1
& $py $team status --work-dir work\mco-team --task-id implement-1
& $py $team result --work-dir work\mco-team --task-id implement-1
& $py $team review-prompt --work-dir work\mco-team --task-id implement-1 --output work\mco-team\review-implement-1.md
```

On Windows with MCO 0.11.0, run `& $py (Join-Path $skill 'scripts\patch_mco_windows.py')` to check whether the tested adapter fixes are needed. Apply them only if reported. The checker exits without changes on macOS/Linux.

## macOS / Linux shell

```bash
skill="$HOME/.codex/skills/mco-deepseek-mimo-team"
py="$skill/.venv/bin/python"
team="$skill/scripts/team.py"
mco --version
mco doctor --json
"$py" "$team" routes
"$py" "$team" start --repo . --work-dir work/mco-team --prompt-file work/mco-team/implementation.md --role pro --expected-provider DeepSeek --mode write --alias implementer --timeout 600 --task-id implement-1
"$py" "$team" status --work-dir work/mco-team --task-id implement-1
"$py" "$team" result --work-dir work/mco-team --task-id implement-1
"$py" "$team" review-prompt --work-dir work/mco-team --task-id implement-1 --output work/mco-team/review-implement-1.md
```

For MiMo, switch CC Switch only after all DeepSeek workers have finished, run `routes` again, and use `--expected-provider 'Xiaomi MiMo'`. Use `--mode read_only` for review tasks. Omit `--task-id` for a generated ID. `result --include-answer` returns the full worker output, so use it only for short answers.

The helper stores metadata and JSONL events under `<work-dir>/tasks/<task-id>/` and MCO artifacts under `<work-dir>/artifacts/<task-id>/`. MCO's `run.json` determines invocation status. Check source files and actual test results when a worker reports completion. A live PID, raw stdout, or a worker's PASS is not proof of completion or correctness. For failures, inspect `diagnostics.log`, `events.jsonl`, and the MCO raw logs under `provider-runs/`.

If automatic MCO discovery fails, set `MCO_ENTRY` to the full path of the installed `@tt-a1i/mco/mco` Python file. This is a per-process setting and does not change MCO installation. The helper also accepts `CC_SWITCH_DB` and `CLAUDE_SETTINGS` paths when CC Switch or Claude Code uses nonstandard locations.

For a genuine worker error, use `review-prompt` to give a same-provider reviewer the original task, outputs, logs, and acceptance criteria. Ask for reproduction and a precise repair direction. For a timeout, compare elapsed time with the hard deadline and consider one bounded rerun. After a repair, independently check the affected acceptance criteria.
