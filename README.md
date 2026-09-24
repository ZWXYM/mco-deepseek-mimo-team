# MCO DeepSeek / MiMo Team

让 Codex 通过 MCO 和 CC Switch 调度 DeepSeek 或 Xiaomi MiMo 的 Claude Code worker，支持 Windows、macOS 和 Linux。可以分配不同任务、查看运行状态、读取结果，并生成独立复核任务。只需配置当前要用的提供商；**没有 MiMo 的 DeepSeek 安装也可以使用**。同一时间不要切换 CC Switch 提供商，当前提供商的多个 worker 可以并行运行。

This repository contains a Codex skill and a small Python helper. It contains no API keys or CC Switch configuration.

## Requirements

- Python 3.10+ and `psutil` from [requirements.txt](requirements.txt)
- Claude Code, CC Switch, and an active Claude provider named `DeepSeek` or `Xiaomi MiMo` with model mappings
- MCO 0.11.0 (`@tt-a1i/mco`) available as `mco` or via its Python entrypoint

CC Switch and Claude Code must run under the same user account as the helper. The helper reads `~/.cc-switch/cc-switch.db` and `~/.claude/settings.json`; it prints model names, not credentials. If either file lives elsewhere, set `CC_SWITCH_DB` or `CLAUDE_SETTINGS` to its full path. Set `MCO_ENTRY` to the installed MCO Python entrypoint only when automatic discovery fails. `CODEX_HOME` can change the Skill installation location.

## Install

Install MCO and its general `mco-cli` skill if they are not already present:

```text
npx @tt-a1i/mco@0.11.0 install --agent codex --yes
mco --version
mco doctor --json
```

Clone this repository to your personal Codex skills directory. The skill name is `mco-deepseek-mimo-team`, so it can coexist with an older `mco-deepseek-team` skill.

### Windows PowerShell

```powershell
$skill = Join-Path $HOME '.codex\skills\mco-deepseek-mimo-team'
git clone https://github.com/ZWXYM/mco-deepseek-mimo-team $skill
Set-Location $skill
py -3 -m venv .venv
$py = Join-Path $skill '.venv\Scripts\python.exe'
& $py -m pip install -r requirements.txt
& $py scripts\patch_mco_windows.py
& $py -m unittest discover -s tests -v
```

The Windows patch checker reports whether the tested MCO 0.11.0 adapter needs fixes. Only if needed, run `& $py scripts\patch_mco_windows.py --apply`. It backs up the installed files first and refuses other MCO versions. An MCO update can replace these patches; check again after updating. The helper can locate a normal global npm installation; for a custom installation, set `MCO_ENTRY` to its `mco` Python file.

### macOS / Linux shell

```bash
skill="$HOME/.codex/skills/mco-deepseek-mimo-team"
git clone https://github.com/ZWXYM/mco-deepseek-mimo-team "$skill"
cd "$skill"
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m unittest discover -s tests -v
```

Do not run the Windows adapter patch on macOS or Linux. The helper first looks for the MCO Python entrypoint in common npm locations and then uses the `mco` command on POSIX systems. For example, a custom installation can be selected with `export MCO_ENTRY=/path/to/@tt-a1i/mco/mco`.

## Quick use

Use the Python interpreter in `.venv` for the following commands. On Windows it is `.venv\Scripts\python.exe`; on macOS/Linux it is `.venv/bin/python`.

```text
<python> <skill>/scripts/team.py routes
<python> <skill>/scripts/team.py start --repo . --work-dir work/mco-team --prompt-file work/mco-team/task.md --role pro --expected-provider DeepSeek --mode read_only --timeout 600 --task-id task-1
<python> <skill>/scripts/team.py status --work-dir work/mco-team --task-id task-1
<python> <skill>/scripts/team.py result --work-dir work/mco-team --task-id task-1
<python> <skill>/scripts/team.py review-prompt --work-dir work/mco-team --task-id task-1 --output work/mco-team/review-task-1.md
```

Run `routes` first and use the provider name it reports. The helper prefers a configured `[1M]` variant within the chosen role; a model label alone does not prove usable long-context capacity. See [SKILL.md](SKILL.md) and [operations.md](references/operations.md) for the control loop and platform-specific examples. A completed `run.json` and output artifact are the authoritative result; a live process or partial raw output is not.

## Security and scope

Keep prompts, task artifacts, provider logs, and `.cc-switch` data outside this repository. Read-only workers may read paths supplied in their prompts. Parallel writers need isolated worktrees or non-overlapping file ownership. The helper has been exercised with DeepSeek on macOS and with DeepSeek/MiMo on one Windows setup; the automated suite runs on all three operating systems. A local Linux provider route still needs an end-to-end check on the target machine.

Licensed under the MIT License. This project is independent of MCO, Claude Code, CC Switch, DeepSeek, and Xiaomi MiMo.
