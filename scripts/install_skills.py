#!/usr/bin/env python3
"""Install the versioned skill bundle; preserve unrelated or modified skills."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ".wechat-ai-skills-receipt.json"
LOCK = ".wechat-ai-skills-install.lock"


def hashes(directory: Path) -> dict[str, str]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"Expected an ordinary skill directory: {directory}")
    result = {}
    for p in sorted(directory.rglob("*")):
        if p.is_symlink():
            raise ValueError(f"Symbolic link requires manual review: {p}")
        if p.is_file():
            result[p.relative_to(directory).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif not p.is_dir():
            raise ValueError(f"Unsupported file type: {p}")
    return result


def package(root: Path) -> tuple[str, dict[str, Path]]:
    spec = json.loads((root / "manifest.json").read_text())
    entries = {}
    for row in spec["skills"]:
        name = row["name"]
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
            raise ValueError(f"Invalid skill name: {name}")
        path = root / row["path"]
        if name in entries or path.is_symlink() or path.resolve().parent != (root / ".agents/skills").resolve():
            raise ValueError(f"Invalid or duplicate skill path: {name}")
        if path.name != name or not (path / "SKILL.md").is_file():
            raise ValueError(f"Missing skill: {name}")
        entries[name] = path
    if not entries:
        raise ValueError("Empty skill package")
    return spec["version"], entries


def install(root: Path, target: Path, update: bool = False, dry_run: bool = False) -> dict:
    version, sources = package(root)
    target = target.expanduser().absolute()
    if target.is_symlink():
        raise ValueError("Target is a symbolic link; choose an ordinary directory")
    if target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Use repository-scoped skills directly; installation target must be outside this checkout")
    if dry_run:
        return preflight(target, version, sources, update)
    target.mkdir(parents=True, exist_ok=True)
    lock = target / LOCK
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f"Installation lock exists; inspect any interrupted installation first: {lock}")
    try:
        result = preflight(target, version, sources, update)
        if result["unchanged"]:
            return result
        transaction = Path(tempfile.mkdtemp(prefix=".wechat-ai-skills-stage-", dir=target))
        moved, placed = [], []
        try:
            stage = transaction / "new"
            backup = transaction / "previous"
            stage.mkdir()
            backup.mkdir()
            for name, source in sources.items():
                shutil.copytree(source, stage / name)
                if hashes(stage / name) != result["skills"][name]:
                    raise ValueError(f"Copy verification failed: {name}")
            receipt_tmp = transaction / "receipt.json"
            receipt_tmp.write_text(json.dumps({"package": "wechat-ai-skills", "version": version,
                                               "skills": result["skills"]}, indent=2) + "\n")
            # Staging may take time. Recheck all destinations before the first mutation.
            if preflight(target, version, sources, update) != result:
                raise ValueError("Installation changed during staging; no skills were replaced")
            for name in sources:
                destination = target / name
                if destination.is_symlink():
                    raise ValueError(f"Destination changed to a symlink: {destination}")
                if destination.exists():
                    if name not in result["previous"] or hashes(destination) != result["previous"][name]:
                        raise ValueError(f"Destination changed during installation: {destination}")
                    destination.rename(backup / name)
                    moved.append(name)
                (stage / name).rename(destination)
                placed.append(name)
            for name in moved:
                if hashes(backup / name) != result["previous"][name]:
                    raise ValueError(f"Previous skill changed during replacement: {name}")
            os.replace(receipt_tmp, target / RECEIPT)
        except BaseException:
            # Roll back only paths this transaction placed or moved.
            for name in reversed(placed):
                shutil.rmtree(target / name)
            for name in moved:
                (backup / name).rename(target / name)
            raise
        finally:
            # If restoring a backup failed, keep recovery files for the operator.
            if not (transaction / "previous").exists() or not any((transaction / "previous").iterdir()):
                shutil.rmtree(transaction)
            elif len(placed) == len(sources) and (target / RECEIPT).is_file():
                # Successful transaction; previous files were checked before replacement.
                current = json.loads((target / RECEIPT).read_text())
                if current.get("version") == version and current.get("skills") == result["skills"]:
                    shutil.rmtree(transaction)
        return result
    finally:
        lock.rmdir()


def preflight(target: Path, version: str, sources: dict[str, Path], update: bool) -> dict:
    receipt_path = target / RECEIPT
    if receipt_path.is_symlink():
        raise ValueError("Receipt is a symbolic link; manual review required")
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    if previous and previous.get("package") != "wechat-ai-skills":
        raise ValueError("Unrecognized installation receipt")
    old = previous.get("skills", {})
    removed = set(old) - set(sources)
    if removed:
        raise ValueError(f"This version omits installed skills; review migration before replacing: {sorted(removed)}")
    new = {name: hashes(source) for name, source in sources.items()}
    for name in sources:
        dest = target / name
        if dest.is_symlink():
            raise ValueError(f"Existing symlink was preserved; review manually: {dest}")
        if dest.exists():
            if name not in old:
                raise ValueError(f"Existing unmanaged skill was preserved: {dest}")
            if hashes(dest) != old[name]:
                raise ValueError(f"Local modifications were preserved: {dest}")
        elif name in old:
            raise ValueError(f"Managed skill is missing; inspect the installation: {dest}")
    unchanged = bool(previous) and previous.get("version") == version and old == new
    if previous and not unchanged and not update:
        raise ValueError("Installed version differs; review the changelog, then use --update")
    return {"version": version, "target": str(target), "skills": new, "previous": old,
            "unchanged": unchanged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path.home() / ".agents" / "skills"
    parser.add_argument("--target", type=Path, default=default, help="Host skill directory (default: Codex skills)")
    parser.add_argument("--update", action="store_true", help="Replace a previously managed, unmodified installation")
    parser.add_argument("--dry-run", action="store_true", help="Check installation and conflicts without writing")
    parser.add_argument("--list", action="store_true", help="List all skill names")
    parser.add_argument("--copy", action="store_true", help="Compatibility option; installation always uses copies")
    args = parser.parse_args()
    try:
        if args.list:
            print("\n".join(package(ROOT)[1]))
            return 0
        result = install(ROOT, args.target, args.update, args.dry_run)
        verb = "Checked" if args.dry_run else ("Already installed" if result["unchanged"] else "Installed")
        print(f"{verb}: {len(result['skills'])} skills, v{result['version']}, {result['target']}")
        if not args.dry_run:
            print("Use the next turn or reload the host to discover skills; verify $private-domain-ops and $wechat-scrm-onboarding.")
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
