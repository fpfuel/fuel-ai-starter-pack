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
import unicodedata
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

PACK_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = PACK_ROOT / ".claude" / "tools" / "quote_template.xlsx"
HEADER = PACK_ROOT / "internal" / "Domains" / "Work" / "ASB" / "quote-header.json"
QUOTES = PACK_ROOT / "External" / "Quotes"

SHEET = "xl/worksheets/sheet1.xml"
WORKBOOK = "xl/workbook.xml"
STYLES = "xl/styles.xml"
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
        self.texts = {}  # ref -> text written, for fit_text

    def _find(self, ref):
        return re.search(r'<c r="' + ref + r'"(?P<a>[^>]*?)(?:/>|>(?P<b>.*?)</c>)', self.xml, re.S)

    def set(self, ref, value, cached=None):
        self.texts.pop(ref, None)
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
            self.texts[ref] = str(value)
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

    def style_of(self, ref):
        m = self._find(ref)
        st = re.search(r'\bs="(\d+)"', m.group("a")) if m else None
        return int(st.group(1)) if st else 0

    def restyle(self, ref, style):
        m = self._find(ref)
        attrs = re.sub(r'\s*\bs="\d+"', "", m.group("a"))
        start = m.start() + len(f'<c r="{ref}"')
        self.xml = (self.xml[:m.start()] + f'<c r="{ref}" s="{style}"{attrs}'
                    + self.xml[start + len(m.group("a")):])

    def set_row_height(self, row, points):
        m = re.search(r'<row r="' + str(row) + r'"([^>]*?)(/?)>', self.xml)
        attrs = re.sub(r'\s*\b(?:ht|customHeight)="[^"]*"', "", m.group(1))
        self.xml = (self.xml[:m.start()] + f'<row r="{row}"{attrs} ht="{points:g}" customHeight="1"'
                    + m.group(2) + ">" + self.xml[m.end():])


# Arial advance widths (the same as Helvetica) in 1/1000 em, for ASCII 32 to 126.
_ARIAL = ([278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278]
          + [556] * 10 + [278, 278, 584, 584, 584, 556, 1015]
          + [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833,
             722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611]
          + [278, 278, 278, 469, 556, 333]
          + [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833,
             556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500]
          + [334, 260, 334, 584])
# Measured in Excel on this template: a column-width unit draws as 5 points and an indent level
# as 8. text_width never comes out narrower than what Excel's AutoFit asks for.
PT_PER_WIDTH_UNIT = 5.0
INDENT_PT = 8.0


def text_width(text, size, bold):
    em = 0
    for ch in text:
        o = ord(ch)
        if 32 <= o < 127:
            em += _ARIAL[o - 32]
        else:
            em += 1000 if unicodedata.east_asian_width(ch) in "WF" else 667
    return em / 1000 * size * 1.05 * (1.05 if bold else 1) + 4


def wrap_lines(text, room, size, bold):
    """The lines Excel needs to show text in `room` points, breaking at spaces."""
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}" if line else word
            if text_width(trial, size, bold) <= room:
                line = trial
                continue
            if line:
                lines.append(line)
            line = ""
            for ch in word:  # a word wider than the cell breaks mid-word
                if line and text_width(line + ch, size, bold) > room:
                    lines.append(line)
                    line = ""
                line += ch
        lines.append(line)
    return lines


class Styles:
    """Reads fonts and cell formats from styles.xml and adds wrapping copies of formats."""

    def __init__(self, xml):
        self.xml = xml
        fonts = re.search(r"<fonts\b[^>]*>(.*?)</fonts>", xml, re.S).group(1)
        self.fonts = re.findall(r"<font\b[^>]*?/>|<font\b[^>]*>.*?</font>", fonts, re.S)
        block = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", xml, re.S).group(1)
        self.xfs = re.findall(r"<xf\b[^>]*?/>|<xf\b[^>]*?>.*?</xf>", block, re.S)
        self.wrapped = {}

    def font(self, style):
        fid = re.search(r'fontId="(\d+)"', self.xfs[style])
        f = self.fonts[int(fid.group(1)) if fid else 0]
        sz = re.search(r'<sz val="([\d.]+)"', f)
        bold = re.search(r'<b(?: val="(?:1|true)")?/>', f) is not None
        return (float(sz.group(1)) if sz else 11.0), bold

    def alignment(self, style):
        m = re.search(r"<alignment\b[^>]*/>", self.xfs[style])
        a = m.group(0) if m else ""
        indent = re.search(r'indent="(\d+)"', a)
        return {"indent": int(indent.group(1)) if indent else 0,
                "shrink": 'shrinkToFit="1"' in a, "wrap": 'wrapText="1"' in a}

    def wrap(self, style):
        """Index of a format identical to `style` except that its text wraps."""
        if style in self.wrapped:
            return self.wrapped[style]
        xf = self.xfs[style]
        if "<alignment" in xf:
            xf = re.sub(r"<alignment\b([^>]*?)/>",
                        lambda m: "<alignment" + re.sub(r'\s*\b(?:wrapText|shrinkToFit)="[^"]*"', "",
                                                        m.group(1)) + ' wrapText="1"/>', xf)
        elif xf.endswith("/>"):
            xf = xf[:-2] + '><alignment wrapText="1"/></xf>'
        else:
            xf = re.sub(r"^(<xf\b[^>]*>)", r'\1<alignment wrapText="1"/>', xf)
        head, rest = xf.split(">", 1)
        if "applyAlignment" not in head:
            xf = head.replace("<xf ", '<xf applyAlignment="1" ', 1) + ">" + rest
        self.xfs.append(xf)
        self.xml = re.sub(r"(<cellXfs\b[^>]*>).*?(</cellXfs>)",
                          lambda m: re.sub(r'count="\d+"', f'count="{len(self.xfs)}"', m.group(1))
                          + "".join(self.xfs) + m.group(2), self.xml, count=1, flags=re.S)
        self.wrapped[style] = len(self.xfs) - 1
        return self.wrapped[style]


def _cell(ref):
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    return _col(m.group(1)), int(m.group(2))


def fit_text(sh, styles):
    """Make every written text fully visible: text wider than its cell (or merged cell) wraps,
    and its row grows to show every line. Columns, merges and fonts stay as they are."""
    fmt = re.search(r"<sheetFormatPr\b[^>]*>", sh.xml)
    fmt = fmt.group(0) if fmt else ""
    dw = re.search(r'defaultColWidth="([\d.]+)"', fmt)
    dh = re.search(r'defaultRowHeight="([\d.]+)"', fmt)
    default_w = float(dw.group(1)) if dw else 8.43
    default_h = float(dh.group(1)) if dh else 15.0
    widths = {}
    for c in re.finditer(r'<col min="(\d+)" max="(\d+)"[^>]*?width="([\d.]+)"', sh.xml):
        for i in range(int(c.group(1)), int(c.group(2)) + 1):
            widths[i] = float(c.group(3))
    heights = {int(r.group(1)): float(r.group(2))
               for r in re.finditer(r'<row r="(\d+)"[^>]*?\bht="([\d.]+)"', sh.xml)}
    merges = []
    for m in re.finditer(r'<mergeCell ref="([A-Z]+\d+):([A-Z]+\d+)"', sh.xml):
        (c1, r1), (c2, r2) = _cell(m.group(1)), _cell(m.group(2))
        merges.append((c1, r1, c2, r2))

    def area(ref):
        c, r = _cell(ref)
        for c1, r1, c2, r2 in merges:
            if c1 <= c <= c2 and r1 <= r <= r2:
                return c1, r1, c2, r2
        return c, r, c, r

    need = []  # (first row, last row, points)
    for ref, text in sh.texts.items():
        style = sh.style_of(ref)
        al = styles.alignment(style)
        if al["shrink"]:
            continue  # her format shrinks this one to fit
        size, bold = styles.font(style)
        c1, r1, c2, r2 = area(ref)
        room = sum(widths.get(i, default_w) for i in range(c1, c2 + 1)) * PT_PER_WIDTH_UNIT
        lines = wrap_lines(text, room - al["indent"] * INDENT_PT, size, bold)
        if len(lines) < 2:
            continue
        if not al["wrap"]:
            sh.restyle(ref, styles.wrap(style))
        per_line = {10.0: 12.5, 11.0: 14.0}.get(size, size * 1.3)
        need.append((r1, r2, len(lines) * per_line + 1.5))

    grow = {}
    for r1, r2, pts in sorted(need, key=lambda n: n[1] - n[0]):
        have = sum(grow.get(r, heights.get(r, default_h)) for r in range(r1, r2 + 1))
        if pts > have:
            grow[r2] = grow.get(r2, heights.get(r2, default_h)) + pts - have
    for row, pts in grow.items():
        sh.set_row_height(row, -(-pts * 2 // 1) / 2)


PAPER_HEIGHT_IN = {"1": 11.0, "5": 14.0, "9": 11.69}  # letter, legal, A4


def keep_on_one_page(sh, wb_xml):
    """If grown rows would push the print area onto a second page, print it scaled to one page."""
    area = re.search(r'_xlnm\.Print_Area"[^>]*>[^<]*?\$?[A-Z]+\$?(\d+):\$?[A-Z]+\$?(\d+)<', wb_xml)
    if not area:
        return
    fmt = re.search(r'<sheetFormatPr\b[^>]*?defaultRowHeight="([\d.]+)"', sh.xml)
    default_h = float(fmt.group(1)) if fmt else 15.0
    heights = {int(r.group(1)): float(r.group(2))
               for r in re.finditer(r'<row r="(\d+)"[^>]*?\bht="([\d.]+)"', sh.xml)}
    tall = sum(heights.get(r, default_h) for r in range(int(area.group(1)), int(area.group(2)) + 1))
    setup = re.search(r"<pageSetup\b[^>]*?/>", sh.xml)
    margins = re.search(r'<pageMargins\b[^>]*?top="([\d.]+)"[^>]*?bottom="([\d.]+)"', sh.xml)
    if not setup or not margins:
        return
    paper = re.search(r'paperSize="(\d+)"', setup.group(0))
    page_in = PAPER_HEIGHT_IN.get(paper.group(1) if paper else "1", 11.0)
    if 'orientation="landscape"' in setup.group(0):
        return
    room = (page_in - float(margins.group(1)) - float(margins.group(2))) * 72
    if tall <= room * 0.97 or "fitToPage" in sh.xml:
        return
    fixed = re.sub(r'\s*\bfitTo(?:Width|Height)="\d+"', "", setup.group(0))
    sh.xml = sh.xml.replace(setup.group(0), fixed[:-2] + ' fitToWidth="1" fitToHeight="1"/>', 1)
    if "<pageSetUpPr" in sh.xml:
        sh.xml = sh.xml.replace("<pageSetUpPr", '<pageSetUpPr fitToPage="1"', 1)
    elif re.search(r"<sheetPr\b[^>]*/>", sh.xml):
        sh.xml = re.sub(r"<sheetPr\b([^>]*?)/>", r'<sheetPr\1><pageSetUpPr fitToPage="1"/></sheetPr>',
                        sh.xml, count=1)
    elif "</sheetPr>" in sh.xml:
        sh.xml = sh.xml.replace("</sheetPr>", '<pageSetUpPr fitToPage="1"/></sheetPr>', 1)
    else:
        sh.xml = re.sub(r"(<worksheet\b[^>]*>)", r'\1<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>',
                        sh.xml, count=1)


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
    styles = Styles(zin.read(STYLES).decode("utf-8"))

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
    fit_text(sh, styles)
    keep_on_one_page(sh, wb_xml)

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
            elif name == STYLES:
                data = styles.xml.encode("utf-8")
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
    # Her UNIT COST column holds up to $999.99 and AMOUNT up to $999,999.99; past that Excel
    # shows #### instead of the number.
    amounts = [goods, subtotal, tax, total, shipping or 0] + [x for _, x in setups]
    if round(unit, 2) >= 1000 or round(total / qty, 2) >= 1000 or max(round(x, 2) for x in amounts) >= 1e6:
        print("  Note: a price here is too wide for its column on the sheet, so Excel shows ####."
              " Widen that column in Excel before sending.")
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
