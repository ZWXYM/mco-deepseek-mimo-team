# MCO DeepSeek / MiMo Team

在 Windows 上让 Codex 通过 MCO 和 CC Switch 调度 DeepSeek 或 Xiaomi MiMo Claude Code worker。支持分配不同任务、查看运行状态、读取结果、生成交叉复核任务，以及将错误反馈给修复 worker。同一时间只运行一个提供商；该提供商的多个模型可以并行工作。

This is a Codex skill and a small command-line helper. It does not contain API keys or CC Switch configuration.

## Requirements

- Windows, Python 3.10+, `pip install -r requirements.txt`
- Claude Code and CC Switch with an active Claude provider configured for DeepSeek or Xiaomi MiMo
- MCO 0.11.0 (`@tt-a1i/mco`) in the default global npm location

## Install

```powershell
git clone https://github.com/ZWXYM/mco-deepseek-mimo-team "$HOME\.codex\skills\mco-deepseek-team"
cd "$HOME\.codex\skills\mco-deepseek-team"
python -m pip install -r requirements.txt
python scripts\patch_mco_windows.py
```

The last command checks whether the tested MCO 0.11.0 Windows fixes are needed. If it lists files, run `python scripts\patch_mco_windows.py --apply`; the script makes a timestamped backup inside the installed MCO package first. It refuses other MCO versions. These compatibility changes affect the local MCO installation, so inspect its backup and rerun a small read-only invocation after an MCO update.

## Quick use

```powershell
$team = Join-Path $HOME '.codex\skills\mco-deepseek-team\scripts\team.py'
python $team routes
python $team start --repo . --work-dir work\mco-team --prompt-file work\mco-team\task.md --role pro --expected-provider 'Xiaomi MiMo' --mode read_only --timeout 600 --task-id task-1
python $team status --work-dir work\mco-team --task-id task-1
python $team result --work-dir work\mco-team --task-id task-1
python $team review-prompt --work-dir work\mco-team --task-id task-1 --output work\mco-team\review-task-1.md
```

For DeepSeek, select that provider in CC Switch and use `--expected-provider DeepSeek`. Check `routes` before dispatch. The helper prefers a configured `[1M]` variant within the selected role; a model label alone does not verify actual long-context capacity.

See [SKILL.md](SKILL.md) for the coordination rules and [operations.md](references/operations.md) for the full workflow. Status exposes MCO events and process activity, but Claude Code may buffer its answer until the invocation finishes. Treat `run.json` plus the output artifact as the completion record.

## Security and scope

The helper reads CC Switch model mapping and Claude settings locally. It prints model names, not credentials. Keep prompts, task artifacts, provider logs, and `.cc-switch` data outside this repository. Review work may read local source files given in its prompt. This skill was tested on one Windows setup with MCO 0.11.0; other versions and CC Switch schemas may need adaptation.

Licensed under the MIT License. This project is independent of MCO, Claude Code, CC Switch, DeepSeek, and Xiaomi MiMo.
