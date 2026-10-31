#!/usr/bin/env python3
"""Gate 5 — osaudit.toml verified by osaudit.

The open science repository must contain `osaudit.toml` at its root, and
`osaudit` (https://github.com/ASSERT-KTH/osaudit, static checks only: nothing
from the repository is executed) must exit 0 on it.

Usage:
  ./scripts/check_osaudit.py <repo-dir> [--json]

The binary is taken from $OSAUDIT_BIN, then PATH, then the local checkout's venv.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_NAME = "osaudit.toml"
OSAUDIT_URL = "https://github.com/ASSERT-KTH/osaudit"
TIMEOUT = 600
MAX_FINDINGS = 30
LOCAL_BIN = Path.home() / "workspace" / "prototypes" / "osaudit" / ".venv" / "bin" / "osaudit"


def find_osaudit() -> str:
    for cand in (os.environ.get("OSAUDIT_BIN"), shutil.which("osaudit"), str(LOCAL_BIN)):
        if cand and Path(cand).exists():
            return cand
    raise RuntimeError(f"osaudit is not installed (see {OSAUDIT_URL}); set OSAUDIT_BIN")


def check_osaudit(root: Path, binary: str | None = None) -> dict:
    """Return {verdict, present, feedback, findings}. Raises if osaudit itself is unavailable."""
    result: dict = {"verdict": False, "present": False, "feedback": "", "findings": []}
    if not (root / CONFIG_NAME).is_file():
        result["feedback"] = f"The repository has no `{CONFIG_NAME}` at its root (see {OSAUDIT_URL})."
        return result
    result["present"] = True
    proc = subprocess.run(
        [binary or find_osaudit(), "--root", str(root), "--json"],
        capture_output=True, text=True, timeout=TIMEOUT, cwd=root,
    )
    if proc.returncode == 0:
        result["verdict"] = True
    elif proc.returncode == 1:
        try:
            result["findings"] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result["findings"] = [proc.stdout.strip()]
        result["feedback"] = f"osaudit reports {len(result['findings'])} finding(s)."
    else:
        msg = (proc.stderr or proc.stdout).strip().splitlines()
        result["feedback"] = f"osaudit could not run on `{CONFIG_NAME}`: {msg[-1] if msg else 'unknown error'}"
    return result


def render_gate5(result: dict) -> str:
    lines = []
    if result.get("feedback"):
        lines += [f"> **Feedback:** {result['feedback']}", ""]
    for f in result.get("findings", [])[:MAX_FINDINGS]:
        if isinstance(f, dict):
            f = f"{f.get('file', '')}:{f.get('line', '')}: {f.get('rule', '')}: {f.get('message', '')}"
        lines.append(f"- `{f}`")
    if len(result.get("findings", [])) > MAX_FINDINGS:
        lines.append("- …")
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo_dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check_osaudit(Path(args.repo_dir))
    if args.json:
        print(json.dumps(result, indent=2))
    elif not result["verdict"]:
        print(f"✗ FAIL {GATE5_LABEL}\n" + render_gate5(result))
    return 0 if result["verdict"] else 1


GATE5_LABEL = "Gate 5 — osaudit.toml verified by osaudit"

if __name__ == "__main__":
    sys.exit(main())
