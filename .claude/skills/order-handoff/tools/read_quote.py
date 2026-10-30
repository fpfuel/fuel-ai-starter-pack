"""Print the fields of a quote sheet as JSON. Standard library only.

  python .claude/skills/order-handoff/tools/read_quote.py "External/Quotes/<customer>/<file>.xlsx"
"""
import json
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CELLS = {
    "customer": "B6", "company": "B7", "address1": "B8", "address2": "B9", "phone": "B10",
    "inquiry": "A13", "terms": "D13", "date_serial": "J13",
    "qty": "A17", "item": "C17", "unit_price": "H17", "goods": "J17",
    "charge1_label": "C18", "charge1": "J18", "charge2_label": "C19", "charge2": "J19",
    "shipping_label": "C20", "shipping": "J20", "charge3_label": "C21", "charge3": "J21",
    "subtotal": "J22", "ge_tax": "J23", "total": "J24", "per_each": "H24",
    "product_link": "C29", "note1": "A31", "note2": "A32", "note3": "A33", "turnaround": "C32",
}


def text(node):
    return "".join(t.text or "" for t in node.iter(NS + "t"))


def read(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = [text(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si")]
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    values = {}
    for c in sheet.iter(NS + "c"):
        ref, kind, v = c.get("r"), c.get("t"), c.find(NS + "v")
        if kind == "s" and v is not None:
            values[ref] = shared[int(v.text)]
        elif kind == "inlineStr":
            values[ref] = text(c.find(NS + "is"))
        elif v is not None and v.text is not None:
            try:
                values[ref] = float(v.text) if re.search(r"[.eE]", v.text) else int(v.text)
            except ValueError:
                values[ref] = v.text
    out = {}
    for name, ref in CELLS.items():
        val = values.get(ref)
        if isinstance(val, str):
            val = val.strip() or None
        if val is not None:
            out[name] = round(val, 2) if isinstance(val, float) else val
    if "phone" in out:
        out["phone"] = re.sub(r"^ph:\s*", "", str(out["phone"]))
    if "turnaround" in out:
        out["turnaround"] = re.sub(r"^Turnaround time:\s*", "", str(out["turnaround"]))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(json.dumps(read(sys.argv[1]), indent=2, ensure_ascii=False))
