#!/usr/bin/env python3
"""Run the release checks with Python 3.10+ standard library only."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    commands = [
        [sys.executable, "scripts/validate_skills.py"],
        [sys.executable, "scripts/validate_architecture.py"],
        [sys.executable, "scripts/build_catalog_docs.py", "--check"],
        [sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py", "-v"],
        [sys.executable, ".agents/skills/task-reconcile/scripts/mock_scrm.py", "--demo"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, env=env)
        if result.returncode:
            return result.returncode
    print("Release checks passed. Live host delegation and customer systems require separate evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
