"""Copy every skill to .agents/skills/ so Codex sees the same skills. Never deletes.

  python .claude/tools/sync_codex_skills.py           all skills
  python .claude/tools/sync_codex_skills.py quote     one or more by name
"""
import shutil
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parents[2]
SRC = PACK / ".claude" / "skills"
DST = PACK / ".agents" / "skills"
SKIP = shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc")


def sync(name):
    src, dst = SRC / name, DST / name
    if not src.is_dir():
        sys.exit(f"no skill named {name} under .claude/skills/")
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=SKIP)
    for md in dst.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        new = text.replace(".claude/skills/", ".agents/skills/")
        if new != text:
            md.write_text(new, encoding="utf-8", newline="\n")


def main():
    names = sys.argv[1:] or sorted(p.name for p in SRC.iterdir() if p.is_dir())
    DST.mkdir(parents=True, exist_ok=True)
    for n in names:
        sync(n)
    print(f"Synced {len(names)} skills to .agents/skills/")
    if not sys.argv[1:]:
        orphans = sorted(p.name for p in DST.iterdir() if p.is_dir() and not (SRC / p.name).is_dir())
        for o in orphans:
            print(f"  {o} is in .agents/skills/ but not .claude/skills/; move it to internal/Trash/ by hand if it was retired")


if __name__ == "__main__":
    main()
