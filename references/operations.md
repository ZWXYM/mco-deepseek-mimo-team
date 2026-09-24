# Local operations

Set `$team = Join-Path $HOME '.codex\skills\mco-deepseek-team\scripts\team.py'` (adjust for a custom `CODEX_HOME`). Use one persistent work directory for the project, including across provider switches. MiMo and DeepSeek must never have overlapping active tasks.

```powershell
mco --version
mco doctor --json
python $team routes
python $team start --repo . --work-dir work\mco-team --prompt-file work\mco-team\implementation.md --role pro --expected-provider 'Xiaomi MiMo' --mode write --alias implementer --timeout 600 --task-id implement-1
python $team status --work-dir work\mco-team --task-id implement-1
python $team result --work-dir work\mco-team --task-id implement-1
python $team review-prompt --work-dir work\mco-team --task-id implement-1 --output work\mco-team\review-implement-1.md
python $team start --repo . --work-dir work\mco-team --prompt-file work\mco-team\review-implement-1.md --role flash --expected-provider 'Xiaomi MiMo' --mode read_only --alias reviewer --timeout 300 --task-id review-1
```

For DeepSeek, set `--expected-provider DeepSeek` after confirming `routes` and choose an available role. Omit `--task-id` for generated IDs. `result --include-answer` loads the full output into the tool response, so use it sparingly. The compact result contains each `output_path` and `run_json`; inspect those files as needed. `status` provides an immediate snapshot and can be called repeatedly at sensible intervals while work continues.

The helper stores task metadata and JSONL events under `<work-dir>/tasks/<task-id>/` and MCO artifacts under `<work-dir>/artifacts/<task-id>/`. MCO's `run.json` is authoritative for invocation status and output paths. Check source files and actual test results when a worker reports completion. For failures, inspect `diagnostics.log`, `events.jsonl`, and `provider-runs/.../raw/claude.stdout.log` and `.stderr.log`; a nonempty raw log is not a completed invocation.

After an npm update, check the installed package at `%APPDATA%\npm\node_modules\@tt-a1i\mco\runtime\`. The tested MCO 0.11.0 setup needed `adapters/claude.py` to launch the native Windows Claude executable and pass `--model`, `adapters/shim.py` and `acp/adapter.py` to tolerate missing `os.getuid`, and `adapters/shim.py` to cancel the Windows process tree. Inspect the installed version and adapt patches before a minimal read-only route test. Do not print or modify CC Switch secrets during diagnosis.

For a genuine provider or invocation error, pass the failed task through `review-prompt`, then have a same-provider reviewer inspect source, logs, and context. Ask for precise reproduction and a repair direction. If a task timed out, compare its elapsed time to the hard deadline and consider a bounded rerun with a longer timeout. If the worker's answer is wrong, direct a separate correction task to the exact files and failed acceptance checks, then request independent recheck.
