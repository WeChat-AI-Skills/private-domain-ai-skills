#!/usr/bin/env python3
"""Validate skill structure, frontmatter, relative links and examples.

No third-party dependencies. Run from anywhere:

    python3 scripts/validate_skills.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".agents" / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|\{\{[^}]+\}\}")
MAX_SKILL_LINES = 500
MAX_DESC = 1024
MIN_DESC = 30

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def parse_frontmatter(text: str, rel: Path) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        err(f"{rel}: missing YAML frontmatter")
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        err(f"{rel}: frontmatter not closed")
        return {}
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            err(f"{rel}: invalid frontmatter line: {line!r}")
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def check_links(md: Path) -> None:
    rel = md.relative_to(ROOT)
    text = md.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (md.parent / path_part).resolve()
        if not resolved.exists():
            err(f"{rel}: broken link -> {target}")


def check_skill(skill_dir: Path) -> None:
    entry = skill_dir / "SKILL.md"
    rel = entry.relative_to(ROOT)
    if not entry.is_file():
        err(f"{skill_dir.relative_to(ROOT)}: missing SKILL.md")
        return

    text = entry.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > MAX_SKILL_LINES:
        err(f"{rel}: too long ({len(lines)} lines > {MAX_SKILL_LINES})")

    fm = parse_frontmatter(text, rel)
    name = fm.get("name", "")
    desc = fm.get("description", "")

    if name != skill_dir.name:
        err(f"{rel}: name {name!r} != directory {skill_dir.name!r}")
    if not NAME_RE.match(name):
        err(f"{rel}: invalid name {name!r} (lowercase letters, digits, hyphens)")
    if len(name) > 64:
        err(f"{rel}: name longer than 64 characters")
    if not MIN_DESC <= len(desc) <= MAX_DESC:
        err(f"{rel}: description length {len(desc)} not in [{MIN_DESC}, {MAX_DESC}]")
    if "\n" in desc:
        err(f"{rel}: description must be a single line")

    if PLACEHOLDER_RE.search(text):
        err(f"{rel}: contains placeholder text")


    check_links(entry)

    for ref in (skill_dir / "references").glob("*.md"):
        check_links(ref)


def check_examples() -> None:
    examples = ROOT / "examples"
    if not examples.is_dir():
        err("examples/: missing")
        return
    for case in sorted(p for p in examples.iterdir() if p.is_dir()):
        for required in ("input.md", "expected.md"):
            if not (case / required).is_file():
                err(f"{case.relative_to(ROOT)}: missing {required}")
        for md in case.glob("*.md"):
            check_links(md)


def check_docs() -> None:
    for name in ("method.md", "boundaries.md", "tool-contract.md"):
        path = ROOT / "docs" / name
        if not path.is_file():
            err(f"docs/{name}: missing")
        else:
            check_links(path)


def check_readme() -> None:
    readme = ROOT / "README.md"
    if not readme.is_file():
        err("README.md: missing")
        return
    check_links(readme)
    text = readme.read_text(encoding="utf-8")
    for skill in sorted(p.name for p in SKILLS.iterdir() if p.is_dir()):
        if skill not in text:
            warn(f"README.md: skill {skill!r} not mentioned")
    for asset in ("cover-v2.jpg", "architecture.jpg", "scene-intake.jpg", "scene-moments.jpg", "scene-campaign.jpg"):
        if not (ROOT / "assets" / asset).is_file():
            err(f"assets/{asset}: missing")


def main() -> int:
    if not SKILLS.is_dir():
        print("skills/ not found", file=sys.stderr)
        return 1

    skill_dirs = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    if not skill_dirs:
        err("skills/: no skill directories")

    names = [p.name for p in skill_dirs]
    if len(names) != len(set(names)):
        err("duplicate skill names")

    for skill_dir in skill_dirs:
        check_skill(skill_dir)

    check_examples()
    check_docs()
    check_readme()
    import json
    manifest = json.loads((ROOT / "manifest.json").read_text())
    manifest_paths = {item["path"] for item in manifest["skills"]}
    actual_paths = {p.relative_to(ROOT).as_posix() for p in skill_dirs}
    if manifest_paths != actual_paths or len(manifest["skills"]) != len(skill_dirs):
        err("manifest.json: skill list differs from actual directories")
    for md in ROOT.rglob("*.md"):
        if ".git" not in md.parts:
            check_links(md)

    print(f"checked {len(skill_dirs)} skills, {len(errors)} error(s), {len(warnings)} warning(s)")
    for message in warnings:
        print(f"  warning: {message}")
    for message in errors:
        print(f"  error: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
