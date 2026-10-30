"""Read a key or password for the tools, without ever printing it.

Order: an environment variable with the same name, then secrets/keys.xlsx (two columns,
"name" and "value", first sheet). Standard library only, so it works before anything is
installed. Names the tools use:

  SAGE_ACCT_ID, SAGE_LOGIN_ID, SAGE_API_KEY      SAGE Connect (product search)
  PIPEDRIVE_API_TOKEN, PIPEDRIVE_DOMAIN           Pipedrive (contacts and activities)

  python .claude/tools/keys.py     lists which names are filled in. Never shows a value.
"""

import os
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

PACK_ROOT = Path(__file__).resolve().parents[2]
KEYS_FILE = PACK_ROOT / "secrets" / "keys.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
KNOWN = ("SAGE_ACCT_ID", "SAGE_LOGIN_ID", "SAGE_API_KEY", "PIPEDRIVE_API_TOKEN", "PIPEDRIVE_DOMAIN")

_cache = None


def _text(node):
    return "".join(t.text or "" for t in node.iter("{%s}t" % NS["m"]))


def _read_sheet(path):
    """Return {name: value} from the first sheet, columns A and B."""
    out = {}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root.findall("m:si", NS)]
        names = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        if not names:
            return out
        root = ET.fromstring(z.read(names[0]))
        for row in root.iter("{%s}row" % NS["m"]):
            cells = {}
            for c in row.findall("m:c", NS):
                col = re.match(r"[A-Z]+", c.get("r", "")).group(0) if c.get("r") else ""
                kind = c.get("t")
                v = c.find("m:v", NS)
                if kind == "s" and v is not None:
                    val = shared[int(v.text)]
                elif kind == "inlineStr":
                    is_ = c.find("m:is", NS)
                    val = _text(is_) if is_ is not None else ""
                else:
                    val = v.text if v is not None else ""
                cells[col] = (val or "").strip()
            name = cells.get("A", "")
            if name and name.lower() != "name":
                out[name] = cells.get("B", "")
    return out


def _sheet():
    global _cache
    if _cache is None:
        _cache = {}
        if KEYS_FILE.exists():
            try:
                _cache = _read_sheet(KEYS_FILE)
            except (zipfile.BadZipFile, ET.ParseError, KeyError, OSError):
                print("Could not read secrets/keys.xlsx. Save it again from Excel as a normal "
                      "workbook (.xlsx).", file=sys.stderr)
    return _cache


def get(name):
    """The value for name, or None. Never printed."""
    value = os.environ.get(name)
    if value:
        return value.strip()
    value = _sheet().get(name)
    return value or None


def filled():
    """Names that have a value, from either source."""
    names = set(KNOWN) | set(_sheet())
    return sorted(n for n in names if get(n))


if __name__ == "__main__":
    print("keys file:", "found" if KEYS_FILE.exists() else "not created yet (copy secrets/keys.example.xlsx)")
    for n in sorted(set(KNOWN) | set(_sheet())):
        print(f"  {n}: {'filled in' if get(n) else 'empty'}")
