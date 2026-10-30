"""Give the assistant its name and its home folder.

  python .claude/tools/rehome.py --name "Kai" --to "C:\\Users\\karen"   copies this folder to C:\\Users\\karen\\Kai
  python .claude/tools/rehome.py --name "Kai" --here                    names it, stays where it is (cloud)

Never overwrites a folder that already has files in it. Puts the name in CLAUDE.md, AGENTS.md,
README.md and Brain/Context/me.md, and points Claude's memory at the new folder's Brain/memory.
The original folder is left as it was; she can delete the download once the new one opens.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2]
NAME_LINE = re.compile(r"^Your name is .*$", re.M)


def folder_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
    return re.sub(r"\s+", "-", clean)[:40]


def set_title(path: Path, title: str, name_line: str) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[0].startswith("# "):
        lines[0] = title
    text = "\n".join(lines)
    if name_line:
        if NAME_LINE.search(text):
            text = NAME_LINE.sub(lambda m: name_line, text, count=1)
        else:
            first, _, rest = text.partition("\n")
            text = f"{first}\n\n{name_line}\n{rest}"
    path.write_text(text, encoding="utf-8", newline="\n")


def set_profile(root: Path, name: str) -> None:
    me = root / "Brain" / "Context" / "me.md"
    if not me.exists():
        return
    text = me.read_text(encoding="utf-8")
    block = f"## My assistant\n\n- Name: {name}\n- Lives in: {root}\n"
    if "## My assistant" in text:
        text = re.sub(r"## My assistant\n.*?(?=\n## |\Z)", lambda m: block, text, count=1, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n" + block
    me.write_text(text, encoding="utf-8", newline="\n")


def point_memory(root: Path) -> None:
    local = root / ".claude" / "settings.local.json"
    if not local.exists():
        return
    try:
        settings = json.loads(local.read_text(encoding="utf-8"))
    except ValueError:
        return
    if "autoMemoryDirectory" in settings:
        settings["autoMemoryDirectory"] = str((root / "Brain" / "memory").resolve())
        local.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--to", help="the folder to create her assistant's folder in")
    where.add_argument("--here", action="store_true")
    a = ap.parse_args()

    name = a.name.strip()
    folder = folder_name(name)
    if not folder:
        sys.exit("Pick a name with at least one letter or number.")
    if a.here:
        root = PACK_ROOT
    else:
        parent = Path(a.to).expanduser()
        if not parent.is_dir():
            sys.exit(f"That folder does not exist: {parent}")
        root = parent / folder
        if root.resolve() == PACK_ROOT:
            pass
        elif root.exists() and any(root.iterdir()):
            sys.exit(f"{root} already has files in it. Pick another name or place.")
        else:
            shutil.copytree(PACK_ROOT, root, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", ".tmp"))

    line = f"Your name is {name}. She chose it; use it when you introduce yourself."
    set_title(root / "CLAUDE.md", f"# {name}: how Claude works here", line)
    set_title(root / "AGENTS.md", f"# {name}: instructions for Codex", line)
    set_title(root / "README.md", f"# {name}", "")
    set_profile(root, name)
    point_memory(root)
    print(f"{name} lives in: {root}")


if __name__ == "__main__":
    main()
