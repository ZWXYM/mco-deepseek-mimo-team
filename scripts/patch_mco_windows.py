"""Check or patch the Windows adapter issues observed in MCO 0.11.0."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected one upstream insertion point, found {source.count(old)}")
    return source.replace(old, new, 1)


def proposed(root: Path) -> dict[Path, str]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    if package.get("version") != "0.11.0":
        raise RuntimeError("This patch is only verified for MCO 0.11.0; inspect the newer package manually")
    runtime = root / "runtime"
    claude = runtime / "adapters" / "claude.py"
    shim = runtime / "adapters" / "shim.py"
    acp = runtime / "acp" / "adapter.py"
    files = {path: path.read_text(encoding="utf-8") for path in (claude, shim, acp)}

    native = '''        binary = "claude"
        if os.name == "nt":
            candidate = os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
            if os.path.isfile(candidate):
                binary = candidate
        cmd = [
            binary,'''
    files[claude] = replace_once(files[claude], '        cmd = [\n            "claude",', native, "native Claude executable")
    files[claude] = replace_once(
        files[claude],
        '            "--output-format",\n            "text",\n        ]\n',
        '            "--output-format",\n            "text",\n        ]\n        model = input_task.metadata.get("model")\n        if isinstance(model, str) and model.strip():\n            cmd.extend(["--model", model.strip()])\n',
        "explicit model forwarding",
    )
    if "import os" not in files[claude]:
        files[claude] = replace_once(files[claude], "from __future__ import annotations\n", "from __future__ import annotations\n\nimport os\n", "os import")
    for path in (shim, acp):
        files[path] = files[path].replace('os.getuid()', 'getattr(os, "getuid", lambda: 0)()')

    cancellation = '''        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(handle.process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                try:
                    handle.process.terminate()
                except OSError:
                    pass
            self._close_io(handle)
            self._runs.pop(ref.run_id, None)
            return
        try:
            os.killpg(os.getpgid(handle.process.pid), signal.SIGTERM)'''
    files[shim] = replace_once(
        files[shim],
        '        try:\n            os.killpg(os.getpgid(handle.process.pid), signal.SIGTERM)',
        cancellation,
        "Windows process-tree cancellation",
    )
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mco-root", type=Path, default=Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@tt-a1i" / "mco")
    parser.add_argument("--apply", action="store_true", help="Back up and modify the installed MCO package")
    args = parser.parse_args()
    if os.name != "nt":
        print("Windows MCO adapter patches are not needed on this platform")
        return
    root = args.mco_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"MCO package not found: {root}")
    changes = proposed(root)
    pending = [path for path, content in changes.items() if path.read_text(encoding="utf-8") != content]
    if not args.apply:
        print(json.dumps({"mco_root": str(root), "needs_patch": [str(path.relative_to(root)) for path in pending]}, indent=2))
        return
    if not pending:
        print("MCO 0.11.0 Windows adapter patches are already present")
        return
    backup = root / ("mco-team-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup.mkdir()
    for path in pending:
        target = backup / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for path in pending:
        path.write_text(changes[path], encoding="utf-8", newline="\n")
    print(json.dumps({"patched": [str(path.relative_to(root)) for path in pending], "backup": str(backup)}, indent=2))


if __name__ == "__main__":
    main()
