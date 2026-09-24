"""Launch and inspect local MCO Claude workers without loading raw answers into Codex."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psutil


HOME = Path.home()
DB = Path(os.environ.get("CC_SWITCH_DB", HOME / ".cc-switch" / "cc-switch.db")).expanduser()
CLAUDE_SETTINGS = Path(os.environ.get("CLAUDE_SETTINGS", HOME / ".claude" / "settings.json")).expanduser()
SUPPORTED_PROVIDERS = {"DeepSeek", "Xiaomi MiMo"}
MODEL_KEYS = (
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
)


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def mco_command() -> list[str]:
    """Find the installed MCO CLI without assuming one OS or npm prefix."""
    explicit = os.environ.get("MCO_ENTRY")
    if explicit:
        entry = Path(explicit).expanduser().resolve()
        if not entry.is_file():
            raise FileNotFoundError(f"MCO_ENTRY does not exist: {entry}")
        return [sys.executable, str(entry)]

    binary = shutil.which("mco")
    roots = []
    if binary:
        roots.append(Path(binary).resolve().parent / "node_modules")
        roots.append(Path(binary).parent / "node_modules")
    if os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "npm" / "node_modules")
    npm = shutil.which("npm")
    if npm:
        try:
            result = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=5, check=True)
            roots.append(Path(result.stdout.strip()))
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    roots.append(HOME / ".local" / "share" / "mco" / "node_modules")
    for root in roots:
        entry = root / "@tt-a1i" / "mco" / "mco"
        if entry.is_file():
            return [sys.executable, str(entry.resolve())]
    if binary and os.name != "nt":
        return [binary]
    raise FileNotFoundError("MCO CLI not found; install @tt-a1i/mco or set MCO_ENTRY to its Python entrypoint")


def active_route() -> dict:
    if not DB.is_file():
        raise FileNotFoundError(f"CC Switch database not found: {DB}")
    with sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT name, settings_config FROM providers WHERE app_type='claude' AND is_current=1"
        ).fetchall()
    if len(rows) != 1:
        raise RuntimeError(f"Expected one active Claude provider, found {len(rows)}")
    provider, raw = rows[0]
    if provider not in SUPPORTED_PROVIDERS:
        raise RuntimeError(f"Active provider {provider!r} is outside this skill's supported routes")
    provider_env = json.loads(raw or "{}").get("env", {})
    live_env = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8")).get("env", {})
    candidates = []
    for key in MODEL_KEYS:
        target = provider_env.get(key)
        alias = live_env.get(key)
        if not isinstance(target, str) or not isinstance(alias, str):
            continue
        lower = target.lower()
        if "flash" in lower:
            role = "flash"
        elif "pro" in lower:
            role = "ultraspeed" if "ultraspeed" in lower else "pro"
        else:
            role = "other"
        candidates.append({
            "role": role,
            "alias": alias,
            "target": target,
            "one_m": "[1m]" in lower or "[1m]" in alias.lower(),
            "mapping_key": key,
        })
    return {"provider": provider, "candidates": candidates}


def pick_model(route: dict, role: str) -> dict:
    options = [item for item in route["candidates"] if item["role"] == role]
    if not options:
        raise RuntimeError(f"No {role!r} model is configured for {route['provider']}")
    options.sort(key=lambda item: (not item["one_m"], MODEL_KEYS.index(item["mapping_key"])))
    return options[0]


def task_dir(base: Path, task_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", task_id):
        raise ValueError("Invalid task ID")
    return base / "tasks" / task_id


def process_running(meta: dict) -> bool:
    try:
        process = psutil.Process(int(meta["pid"]))
        return abs(process.create_time() - float(meta["pid_created"])) < 2 and process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, ValueError):
        return False


def read_meta(directory: Path) -> dict:
    return json.loads((directory / "meta.json").read_text(encoding="utf-8"))


def task_status(directory: Path) -> dict:
    meta = read_meta(directory)
    events = []
    event_file = directory / "events.jsonl"
    if event_file.exists():
        for line in event_file.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and "type" in item:
                events.append(item)
    final = next((item for item in reversed(events) if item.get("type") == "task_finished"), None)
    finish = next((item for item in reversed(events) if item.get("type") == "invocation_finished"), None)
    raw_files = list((Path(meta["artifact_base"]) / meta["task_id"] / "provider-runs").glob("**/raw/claude.stdout.log"))
    raw_bytes = sum(path.stat().st_size for path in raw_files if path.is_file())
    raw_latest = max((path.stat().st_mtime for path in raw_files if path.is_file() and path.stat().st_size), default=None)
    last_event = events[-1] if events else None
    running = process_running(meta)
    end_time = datetime.now(timezone.utc)
    if final and final.get("timestamp"):
        try:
            end_time = datetime.fromisoformat(final["timestamp"])
        except ValueError:
            pass
    worker_process_count = 0
    if running:
        try:
            worker_process_count = len(psutil.Process(int(meta["pid"])).children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    current_provider = None
    try:
        current_provider = active_route()["provider"]
    except Exception:
        pass
    return {
        "task_id": meta["task_id"],
        "provider": meta["provider"],
        "model_alias": meta["model_alias"],
        "target_model": meta["target_model"],
        "running": running,
        "status": final.get("status") if final else ("running" if running else "stopped_without_final_event"),
        "invocation_status": finish.get("status") if finish else None,
        "last_event": last_event.get("type") if last_event else None,
        "last_event_at": last_event.get("timestamp") if last_event else None,
        "answer_characters_seen": sum(len(item.get("delta", "")) for item in events if item.get("type") == "output_delta"),
        "raw_stdout_bytes": raw_bytes,
        "seconds_since_last_raw_output": round(datetime.now(timezone.utc).timestamp() - raw_latest, 1) if raw_latest else None,
        "elapsed_seconds": round(end_time.timestamp() - datetime.fromisoformat(meta["started_at"]).timestamp(), 1),
        "worker_process_count": worker_process_count,
        "provider_changed_during_task": current_provider is not None and current_provider != meta["provider"],
        "result_dir": str(Path(meta["artifact_base"]) / meta["task_id"]),
    }


def start_task(args: argparse.Namespace) -> dict:
    route = active_route()
    if route["provider"] != args.expected_provider:
        raise RuntimeError(f"Expected {args.expected_provider!r}, but CC Switch currently selects {route['provider']!r}")
    selected = pick_model(route, args.role)
    base = Path(args.work_dir).resolve()
    repo = Path(args.repo).resolve()
    prompt = Path(args.prompt_file).resolve()
    if not repo.is_dir() or not prompt.is_file():
        raise FileNotFoundError("Repository or prompt file does not exist")
    command = mco_command()
    for meta_file in (base / "tasks").glob("*/meta.json"):
        other = read_meta(meta_file.parent)
        if process_running(other) and other.get("provider") != route["provider"]:
            raise RuntimeError("Another provider still has an active worker; finish it before switching")
    task_id = args.task_id or ("team-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    directory = task_dir(base, task_id)
    directory.mkdir(parents=True, exist_ok=False)
    artifact_base = base / "artifacts"
    command += [
        "review" if args.mode == "read_only" else "run",
        "--repo", str(repo), "--file", str(prompt),
        "--agent", f"{args.alias}=claude:{selected['alias']}",
        "--task-id", task_id, "--artifact-base", str(artifact_base),
        "--result-mode", "both", "--stream", "jsonl",
        "--invocation-hard-timeout", str(args.timeout),
    ]
    if args.mode == "write":
        command += ["--execution-mode", "write"]
    process_options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt" else {"start_new_session": True}
    )
    with (directory / "events.jsonl").open("w", encoding="utf-8") as stdout, (directory / "diagnostics.log").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command, cwd=repo, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            **process_options,
        )
    pid_created = psutil.Process(process.pid).create_time()
    meta = {
        "task_id": task_id, "pid": process.pid, "pid_created": pid_created,
        "provider": route["provider"], "model_alias": selected["alias"],
        "target_model": selected["target"], "role": args.role,
        "repo": str(repo), "prompt_file": str(prompt), "mode": args.mode,
        "alias": args.alias, "timeout_seconds": args.timeout,
        "artifact_base": str(artifact_base),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (directory / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"task_id": task_id, "provider": route["provider"], "model_alias": selected["alias"], "target_model": selected["target"], "pid": process.pid, "task_dir": str(directory)}


def show_result(directory: Path, include_answer: bool) -> dict:
    status = task_status(directory)
    result_file = Path(status["result_dir"]) / "run.json"
    if not result_file.exists():
        return {**status, "result_ready": False, "diagnostics_path": str(directory / "diagnostics.log")}
    record = json.loads(result_file.read_text(encoding="utf-8"))
    outputs = []
    for item in record.get("outputs", []):
        output_path = item.get("output_path")
        output = {
            "invocation_id": item.get("invocation_id"), "stage": item.get("stage"),
            "status": item.get("status"), "error": item.get("error"),
            "output_path": output_path,
        }
        if include_answer:
            output["answer"] = Path(output_path).read_text(encoding="utf-8") if output_path and Path(output_path).is_file() else None
        outputs.append(output)
    return {**status, "result_ready": True, "outputs": outputs, "run_json": str(result_file), "diagnostics_path": str(directory / "diagnostics.log")}


def create_review_prompt(directory: Path, output_file: Path) -> dict:
    meta = read_meta(directory)
    status = task_status(directory)
    result_dir = Path(status["result_dir"])
    run_file = result_dir / "run.json"
    output_paths = []
    if run_file.is_file():
        record = json.loads(run_file.read_text(encoding="utf-8"))
        output_paths = [item["output_path"] for item in record.get("outputs", []) if item.get("output_path")]
    prompt_text = Path(meta["prompt_file"]).read_text(encoding="utf-8")
    paths = "\n".join(f"- {path}" for path in output_paths) or "- No completed output artifact; inspect partial raw logs."
    review = f"""Act as an independent read-only reviewer of a worker task. Inspect the actual source files and artifacts; do not accept a worker's PASS without checking evidence. Do not edit files.

Original task ({meta['task_id']}, {meta['provider']}, {meta['target_model']}):
{prompt_text}

Observed state: task={status['status']}; invocation={status['invocation_status']}; raw stdout bytes={status['raw_stdout_bytes']}; provider changed={status['provider_changed_during_task']}.
The MCO task status, not raw stdout text, determines whether the invocation completed. Partial raw output after a timeout is unverified evidence.

Worker output artifacts:
{paths}

Diagnostics and raw evidence:
- {directory / 'events.jsonl'}
- {directory / 'diagnostics.log'}
- {run_file}
- {result_dir / 'provider-runs'}

Reproduce material claims against primary files, identify any errors with precise locations, give the most likely cause and concrete investigation or repair direction in the context of this task. End with PASS, FAIL, or INDETERMINATE and a concise evidence summary.
"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(review, encoding="utf-8")
    return {"review_prompt": str(output_file), "source_task": meta["task_id"], "source_status": status["status"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("routes")
    start = sub.add_parser("start")
    start.add_argument("--repo", required=True)
    start.add_argument("--work-dir", required=True)
    start.add_argument("--prompt-file", required=True)
    start.add_argument("--role", choices=("pro", "flash", "ultraspeed"), required=True)
    start.add_argument("--expected-provider", choices=sorted(SUPPORTED_PROVIDERS), required=True)
    start.add_argument("--mode", choices=("read_only", "write"), default="read_only")
    start.add_argument("--alias", default="worker")
    start.add_argument("--timeout", type=int, default=600)
    start.add_argument("--task-id")
    for name in ("status", "result"):
        command = sub.add_parser(name)
        command.add_argument("--work-dir", required=True)
        command.add_argument("--task-id", required=True)
        if name == "result":
            command.add_argument("--include-answer", action="store_true")
    review = sub.add_parser("review-prompt")
    review.add_argument("--work-dir", required=True)
    review.add_argument("--task-id", required=True)
    review.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "routes":
            emit(active_route())
        elif args.command == "start":
            if args.timeout <= 0:
                raise ValueError("timeout must be positive")
            emit(start_task(args))
        elif args.command == "review-prompt":
            directory = task_dir(Path(args.work_dir).resolve(), args.task_id)
            emit(create_review_prompt(directory, Path(args.output).resolve()))
        else:
            directory = task_dir(Path(args.work_dir).resolve(), args.task_id)
            emit(task_status(directory) if args.command == "status" else show_result(directory, args.include_answer))
    except Exception as exc:
        emit({"error": str(exc), "type": type(exc).__name__})
        raise SystemExit(2)


if __name__ == "__main__":
    main()
