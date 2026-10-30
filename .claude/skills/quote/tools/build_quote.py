"""Build a quote in your own QUOTE sheet layout.

Standard library only. The sheet is made by filling your template workbook
(.claude/tools/quote_template.xlsx) cell by cell, so fonts, borders, column widths, merged
cells and the logo stay exactly as you designed them. The header (your name, company, phone,
email, website) comes from internal/Domains/Work/ASB/quote-header.json.

Example (the keyring test quote):

  python .claude/skills/quote/tools/build_quote.py --customer "Pat Sample" \
    --company "Sample Contracting" --address "100 Sample St." --address "Hilo, HI 96720" \
    --phone "(808) 555-0100" --item "Pull Apart Keyring" --qty 150 --unit-cost 3.95 \
    --setup "Setup, laser engrave=80" --shipping 143 --destination Hilo \
    --url https://us.stregisgrp.com/channel/home-office/detail/KC110 \
    --turnaround "10-12 business days" --date 2026-10-25

Or every input in one JSON file (what the review page sends):  --json inputs.json

Saves to External/Quotes/<Customer Company>/<YYYY-MM-DD>-<item>.xlsx unless --out is given.
Every number must come from a supplier page, the pricing file, or you. This script only lays
them out; it never estimates anything.
"""

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

PACK_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = PACK_ROOT / ".claude" / "tools" / "quote_template.xlsx"
HEADER = PACK_ROOT / "internal" / "Domains" / "Work" / "ASB" / "quote-header.json"
QUOTES = PACK_ROOT / "External" / "Quotes"

SHEET = "xl/worksheets/sheet1.xml"
WORKBOOK = "xl/workbook.xml"
GE_TAX_RATE = 0.04712

# Every cell the quote writes. All are cleared first, so a new quote never carries the last
# customer's text.
VARIABLE_CELLS = [
    "A4", "G6", "G7", "G9", "G10",
    "B6", "B7", "B8", "B9", "B10",
    "A13", "C13", "D13", "G13", "J13",
    "A17", "B17", "C17", "H17", "I17",
    "C18", "J18", "C19", "J19", "C20", "J20", "C21", "J21",
    "C29", "A31", "A32", "A33", "C32", "F37",
]
FORMULAS = {"J17": "H17*A17", "J22": "SUM(J17:J21)", "J23": "J22*4.712%",
            "H24": "J24/A17", "J24": "SUM(J22:J23)"}
CHARGE_ROWS = ["18", "19", "21"]  # row 20 is shipping


SHEET_RELS = "xl/worksheets/_rels/sheet1.xml.rels"


def set_link(sheet_xml, rels_xml, ref, url):
    """Point the hyperlink on `ref` at url, or remove it when url is empty."""
    m = re.search(r'<hyperlink ref="' + re.escape(ref) + r'" r:id="(rId\d+)"[^>]*/>', sheet_xml)
    if not m:
        return sheet_xml, rels_xml
    rid = m.group(1)
    if url:
        if not re.match(r"^[a-z]+://", url, re.I):
            url = "https://" + url
        rels_xml = re.sub(r'(<Relationship Id="' + rid + r'"[^>]*?Target=")[^"]*(")',
                          lambda r: r.group(1) + escape(url, {'"': "&quot;"}) + r.group(2), rels_xml)
    else:
        sheet_xml = sheet_xml.replace(m.group(0), "")
        rels_xml = re.sub(r'<Relationship Id="' + rid + r'"[^>]*/>', "", rels_xml)
        sheet_xml = re.sub(r"<hyperlinks>\s*</hyperlinks>", "", sheet_xml)
    return sheet_xml, rels_xml


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + (ord(ch) - 64)
    return n


class Sheet:
    """Edits cell values in sheet XML and leaves everything else alone."""

    def __init__(self, xml):
        self.xml = xml

    def _find(self, ref):
        return re.search(r'<c r="' + ref + r'"(?P<a>[^>]*?)(?:/>|>(?P<b>.*?)</c>)', self.xml, re.S)

    def set(self, ref, value, cached=None):
        m = self._find(ref)
        style = re.search(r'\bs="(\d+)"', m.group("a")).group(1) if m and 's="' in m.group("a") else None
        s = f' s="{style}"' if style else ""
        if value is None or value == "":
            new = f'<c r="{ref}"{s}/>'
        elif isinstance(value, tuple):
            v = "" if cached is None else f"<v>{cached!r}</v>"
            new = f'<c r="{ref}"{s}><f>{escape(value[1])}</f>{v}</c>'
        elif isinstance(value, dt.date):
            new = f'<c r="{ref}"{s}><v>{(value - dt.date(1899, 12, 30)).days}</v></c>'
        elif isinstance(value, (int, float)):
            new = f'<c r="{ref}"{s}><v>{value!r}</v></c>'
        else:
            new = (f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">'
                   f'{escape(str(value))}</t></is></c>')
        if m:
            self.xml = self.xml[:m.start()] + new + self.xml[m.end():]
            return
        row = re.search(r"\d+", ref).group(0)
        rm = re.search(r'<row r="' + row + r'"[^>]*>(.*?)</row>', self.xml, re.S)
        if not rm:
            sys.exit(f"Row {row} is missing from the quote template, so {ref} cannot be written.")
        body = rm.group(1)
        at = len(body)
        for c in re.finditer(r'<c r="([A-Z]+)' + row + r'"', body):
            if _col(c.group(1)) > _col(ref):
                at = c.start()
                break
        self.xml = self.xml[:rm.start(1)] + body[:at] + new + body[at:] + self.xml[rm.end(1):]


def parse_setup(items):
    out = []
    for item in items or []:
        label, _, amount = str(item).rpartition("=")
        if not label.strip() or not amount.strip():
            sys.exit(f'A setup charge needs "label=amount", got {item!r}.')
        out.append((label.strip(), float(amount)))
    if len(out) > len(CHARGE_ROWS):
        sys.exit("The sheet has room for three setup or extra charges. Combine some and try again.")
    return out


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:60] or "quote"


def folder_name(text):
    name = re.sub(r'[<>:"/\\|?*]+', "", str(text or "").strip()).rstrip(". ")
    return name or "Unsorted"


def default_out(company, customer, item, date):
    folder = QUOTES / folder_name(company or customer)
    out = folder / f"{date.isoformat()}-{slug(item)}.xlsx"
    n = 2
    while out.exists():
        out = folder / f"{date.isoformat()}-{slug(item)}-{n}.xlsx"
        n += 1
    return out


def load_header(path):
    if not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError:
        sys.exit(f"{path} is not valid JSON. Fix it or run setup again.")


def build(a):
    template = Path(a.template)
    if not template.exists():
        sys.exit(f"Quote template not found: {template}")
    header = load_header(a.header)
    zin = zipfile.ZipFile(template)
    sh = Sheet(zin.read(SHEET).decode("utf-8"))
    wb_xml = zin.read(WORKBOOK).decode("utf-8")

    for ref in VARIABLE_CELLS:
        sh.set(ref, None)

    sh.set("A4", header.get("header_line"))
    sh.set("G6", header.get("from_name"))
    sh.set("G7", header.get("from_company"))
    sh.set("G9", header.get("from_city"))
    sh.set("G10", header.get("from_web"))

    addr = [x for x in (a.address or []) if str(x).strip()]
    sh.set("B6", a.customer)
    sh.set("B7", a.company)
    sh.set("B8", addr[0] if addr else None)
    sh.set("B9", addr[1] if len(addr) > 1 else None)
    sh.set("B10", f"ph:  {a.phone}" if a.phone else None)

    date = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    sh.set("A13", a.inquiry)
    sh.set("C13", a.ship_date)
    sh.set("D13", a.terms)
    sh.set("G13", a.fob)
    sh.set("J13", date)

    qty, unit = int(a.qty), float(a.unit_cost)
    if qty <= 0:
        sys.exit("Quantity must be more than zero.")
    goods = round(qty * unit, 2)
    sh.set("A17", qty)
    sh.set("B17", "ea")
    sh.set("C17", a.item)
    sh.set("H17", unit)
    sh.set("I17", "ea")
    sh.set("J17", ("f", FORMULAS["J17"]), goods)

    setups = parse_setup(a.setup)
    for row, (label, amount) in zip(CHARGE_ROWS, setups):
        sh.set("C" + row, label)
        sh.set("J" + row, amount)
    shipping = None if a.shipping is None else float(a.shipping)
    if shipping is not None:
        sh.set("C20", "Shipping" + (f" to {a.destination}" if a.destination else ""))
        sh.set("J20", shipping)

    subtotal = round(goods + sum(x for _, x in setups) + (shipping or 0), 2)
    tax = subtotal * GE_TAX_RATE
    total = subtotal + tax
    sh.set("J22", ("f", FORMULAS["J22"]), subtotal)
    sh.set("J23", ("f", FORMULAS["J23"]), tax)
    sh.set("J24", ("f", FORMULAS["J24"]), total)
    sh.set("H24", ("f", FORMULAS["H24"]), total / qty)

    # The URL lives on the "Product Link" label as a hyperlink (set_link below), as on her sheet.
    for ref, text in zip(("A31", "A32", "A33"), (a.note or [])[:3]):
        sh.set(ref, text)
    sh.set("C32", f"Turnaround time: {a.turnaround}" if a.turnaround else None)
    sh.set("F37", 30)

    if "fullCalcOnLoad" not in wb_xml:
        if "<calcPr" in wb_xml:
            wb_xml = wb_xml.replace("<calcPr", '<calcPr fullCalcOnLoad="1"', 1)
        else:
            wb_xml = wb_xml.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')

    rels_xml = zin.read(SHEET_RELS).decode("utf-8") if SHEET_RELS in zin.namelist() else None
    if rels_xml is not None:
        sh.xml, rels_xml = set_link(sh.xml, rels_xml, "C28:G28", a.url)
        sh.xml, rels_xml = set_link(sh.xml, rels_xml, "G10", header.get("from_web"))
    out = Path(a.out) if a.out else default_out(a.company, a.customer, a.item, date)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            name = info.filename
            if name == "xl/calcChain.xml":
                continue  # Excel rebuilds it; a stale one triggers a repair prompt
            data = zin.read(name)
            if name == SHEET:
                data = sh.xml.encode("utf-8")
            elif name == SHEET_RELS and rels_xml is not None:
                data = rels_xml.encode("utf-8")
            elif name == WORKBOOK:
                data = wb_xml.encode("utf-8")
            elif name == "[Content_Types].xml":
                data = re.sub(rb"<Override[^>]*calcChain[^>]*/>", b"", data)
            elif name == "xl/_rels/workbook.xml.rels":
                data = re.sub(rb"<Relationship[^>]*calcChain[^>]*/>", b"", data)
            z.writestr(info, data)

    result = {"file": str(out.resolve()), "qty": qty, "unit_cost": unit, "goods": goods,
              "setups": setups, "shipping": shipping, "subtotal": subtotal,
              "tax": round(tax, 2), "total": round(total, 2), "per_each": round(total / qty, 2)}
    print(f"Quote written: {result['file']}")
    print(f"  {qty} x {a.item} at ${unit:,.2f} = ${goods:,.2f}")
    for label, amount in setups:
        print(f"  {label}: ${amount:,.2f}")
    if shipping is not None:
        print(f"  Shipping{' to ' + a.destination if a.destination else ''}: ${shipping:,.2f}")
    print(f"  Subtotal: ${subtotal:,.2f}")
    print(f"  GE tax 4.712%: ${tax:,.2f}")
    print(f"  Total: ${total:,.2f}  (${total / qty:,.2f} each)")
    print("  Prices good for 30 days.")
    if not header:
        print("  Note: the header is blank. Run setup to add your name, company and contact line.")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Build a quote in your QUOTE sheet layout.")
    p.add_argument("--json", help="read every input from a JSON file instead of flags")
    p.add_argument("--template", default=str(TEMPLATE))
    p.add_argument("--header", default=str(HEADER), help="JSON with your header lines")
    p.add_argument("--out", help="output path; default External/Quotes/<company>/<date>-<item>.xlsx")
    p.add_argument("--customer", help="contact name")
    p.add_argument("--company", help="customer company")
    p.add_argument("--address", action="append", help="address line; repeat for the second line")
    p.add_argument("--phone")
    p.add_argument("--item", help="product description")
    p.add_argument("--qty", type=int)
    p.add_argument("--unit-cost", type=float, help="sell price per unit")
    p.add_argument("--setup", action="append", help='setup or extra charge as "label=amount", up to three')
    p.add_argument("--shipping", type=float, help="freight amount from the rate tools or you")
    p.add_argument("--destination", help="ship-to city, for the shipping line")
    p.add_argument("--url", help="product link")
    p.add_argument("--turnaround", help='for example "10-12 business days"')
    p.add_argument("--date", help="quote date YYYY-MM-DD, default today")
    p.add_argument("--terms", default="Net 30")
    p.add_argument("--inquiry", help="YOUR INQUIRY cell")
    p.add_argument("--ship-date", help="SHIPPING DATE cell")
    p.add_argument("--fob", help="F.O.B. cell")
    p.add_argument("--note", action="append", help="left-margin note (cartons, weight, ship-from), up to three")
    a = p.parse_args(argv)
    if a.json:
        data = json.loads(Path(a.json).read_text(encoding="utf-8"))
        for key, value in data.items():
            setattr(a, key.replace("-", "_"), value)
    for need in ("item", "qty", "unit_cost"):
        if getattr(a, need) in (None, ""):
            sys.exit(f"Missing {need.replace('_', ' ')}. Ask for it; never guess.")
    if isinstance(a.address, str):
        a.address = [a.address]
    if isinstance(a.note, str):
        a.note = [a.note]
    build(a)


if __name__ == "__main__":
    main()
