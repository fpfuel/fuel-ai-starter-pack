"""Local server for the sourcing review page. Standard library only.

  python .claude/tools/review/server.py            -> http://127.0.0.1:8765
  python .claude/tools/review/server.py --port N --dir FOLDER   (tests)
  python .claude/tools/review/server.py --export [RUN.json] [--out FILE.html]
      saves a run as one HTML file that opens without the server (for cloud sessions)

Routes
  GET  /                      the page
  GET  /favicon.svg
  GET  /api/runs              newest first: [{file, generated, query, qty, shipToLabel, image}]
  GET  /api/latest            newest run, 204 when none
  GET  /api/run?f=NAME        one run
  POST /api/ups-show          {run, candidateId} -> raises the real UPS quote in Chrome (own computer only)
  POST /api/quote             {run, candidateId, optionIndex, customer, company, address1,
                               address2, phone, unitCost, turnaround} -> builds the xlsx with
                               the quote tool, returns {ok, file, lines}
  GET  /api/quotes            [{file, modified, size}] newest first; file is <company>/<name>.xlsx
  GET  /quotes/<company>/NAME.xlsx   download
  POST /api/quote/delete      {file, confirm: true} -> moves it to internal/Trash/Quotes/
"""

import json
import os
import shutil
import re
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # review -> tools -> .claude -> pack
INDEX = os.path.join(HERE, "index.html")
REVIEW_DIR = os.path.join(PACK_ROOT, "internal", "Domains", "Work", "ASB", "sourcing")
QUOTES_DIR = os.path.join(PACK_ROOT, "External", "Quotes")
TRASH_DIR = os.path.join(PACK_ROOT, "internal", "Trash", "Quotes")
QUOTE_TOOL = os.path.join(PACK_ROOT, ".claude", "skills", "quote", "tools", "build_quote.py")
SHIP_TOOLS = os.path.join(PACK_ROOT, ".claude", "skills", "shipping", "tools")
HIDE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HOST, PORT = "127.0.0.1", 8765
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#1f5f4a"/>'
    '<rect x="7" y="9" width="7" height="14" rx="1.5" fill="#f7f5f0"/>'
    '<rect x="18" y="13" width="7" height="10" rx="1.5" fill="#f7f5f0" opacity=".75"/>'
    "</svg>"
).encode("utf-8")


def _args():
    port, folder, quotes, trash = PORT, REVIEW_DIR, QUOTES_DIR, TRASH_DIR
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])
        if a == "--dir" and i + 1 < len(argv):
            folder = os.path.abspath(argv[i + 1])
            quotes = os.path.join(folder, "quotes")
            trash = os.path.join(folder, "trash")
    return port, folder, quotes, trash


def safe_name(name, ext=".json"):
    if not name or not name.endswith(ext):
        return False
    if "/" in name or "\\" in name or os.sep in name or ".." in name or name.startswith("."):
        return False
    return True


def read_run(folder, name):
    with open(os.path.join(folder, name), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("run file is not an object")
    data["file"] = name
    return data


def list_runs(folder):
    out = []
    try:
        names = [n for n in os.listdir(folder) if safe_name(n)]
    except OSError:
        return out
    for n in names:
        try:
            d = read_run(folder, n)
        except (OSError, ValueError):
            continue
        req = d.get("request") or {}
        cands = d.get("candidates") or []
        img = next((c.get("imageUrl") for c in cands if c.get("imageUrl")), None)
        out.append({"file": n, "generated": d.get("generated", ""), "query": req.get("query", ""), "qty": req.get("qty"),
                    "shipToLabel": req.get("shipToLabel", ""), "shipTo": req.get("shipTo", ""), "image": img, "candidates": len(cands)})
    out.sort(key=lambda r: (r["generated"] or "", r["file"]), reverse=True)
    return out


def safe_rel(rel):
    """A quote path under the quotes folder: '<company>/<name>.xlsx' or '<name>.xlsx'."""
    if not isinstance(rel, str) or not rel.endswith(".xlsx") or "\\" in rel or rel.startswith("/"):
        return False
    parts = rel.split("/")
    return 1 <= len(parts) <= 2 and all(p and p not in (".", "..") and not p.startswith(".") for p in parts)


def folder_name(text):
    name = re.sub(r'[<>:"/\\|?*]+', "", str(text or "").strip()).rstrip(". ")
    return name or "Unsorted"


def list_quotes(folder):
    out = []
    names = []
    try:
        for entry in os.listdir(folder):
            full = os.path.join(folder, entry)
            if os.path.isdir(full) and not entry.startswith("."):
                names += [entry + "/" + n for n in os.listdir(full) if safe_name(n, ".xlsx")]
            elif safe_name(entry, ".xlsx"):
                names.append(entry)
    except OSError:
        return out
    for n in names:
        try:
            st = os.stat(os.path.join(folder, *n.split("/")))
        except OSError:
            continue
        out.append({"file": n, "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)), "size": st.st_size})
    out.sort(key=lambda r: r["modified"], reverse=True)
    return out


def money(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_quote(review_dir, quotes_dir, payload):
    """Turn a selection on the page into the quote tool's inputs and run it."""
    run = payload.get("run")
    if not isinstance(run, str) or not safe_name(run):
        return 400, {"ok": False, "error": "bad run name"}
    try:
        data = read_run(review_dir, run)
    except (OSError, ValueError):
        return 404, {"ok": False, "error": "run not found"}
    cand = next((c for c in data.get("candidates", []) if str(c.get("id")) == str(payload.get("candidateId"))), None)
    if not cand:
        return 400, {"ok": False, "error": "pick a product first"}
    opts = (cand.get("freight") or {}).get("options") or []
    try:
        opt = opts[int(payload.get("optionIndex"))]
    except (TypeError, ValueError, IndexError):
        return 400, {"ok": False, "error": "pick a shipping option first"}
    req = data.get("request") or {}
    unit = money(payload.get("unitCost"))
    if unit is None or unit <= 0:
        return 400, {"ok": False, "error": "sell price per unit is required; no markup rule is recorded, so Karen sets it"}
    customer = (payload.get("customer") or "").strip()
    if not customer:
        return 400, {"ok": False, "error": "customer contact name is required"}
    for k in ("customer", "company", "address1", "address2", "phone", "turnaround", "inquiry"):
        v = payload.get(k)
        if v is not None and (not isinstance(v, str) or len(v) > 200):
            return 400, {"ok": False, "error": f"{k} must be text under 200 characters"}

    setups = []
    if money(cand.get("setupChg")):
        label = "Setup" + (f", {cand['decorationMethod'].split(',')[0].strip().lower()}" if cand.get("decorationMethod") else "")
        setups.append(f"{label}={money(cand.get('setupChg')):.2f}")
    notes = []
    k = cand.get("carton") or {}
    if k.get("units"):
        notes.append(f"{cand.get('cartons')} cartons of {k['units']}, {k['lbs']} lb, {k['L']}x{k['W']}x{k['H']} in")
    if cand.get("shipFromZip"):
        notes.append(f"ships from {cand['shipFromZip']}")
    notes.append(f"freight: {opt.get('carrier')} {opt.get('service')} retail estimate, {opt.get('delivery') or ''}".strip())
    address = [a for a in (payload.get("address1"), payload.get("address2")) if isinstance(a, str) and a.strip()]
    spec = {
        "customer": customer, "company": (payload.get("company") or "").strip() or None,
        "address": address or None, "phone": (payload.get("phone") or "").strip() or None,
        "item": cand.get("name"), "qty": int(req.get("qty") or 0), "unit_cost": unit,
        "setup": setups, "shipping": round(float(opt.get("totalUSD") or 0), 2),
        "destination": req.get("shipToLabel") or req.get("shipTo"), "url": cand.get("supplierUrl"),
        "turnaround": (payload.get("turnaround") or cand.get("prodTime") or "").strip() or None,
        "inquiry": (payload.get("inquiry") or "").strip() or None, "note": notes,
    }
    company_dir = os.path.join(quotes_dir, folder_name(spec["company"] or customer))
    os.makedirs(company_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", str(cand.get("name", "")).lower()).strip("-")[:60] or "quote"
    out = os.path.join(company_dir, f"{time.strftime('%Y-%m-%d')}-{slug}.xlsx")
    n = 2
    while os.path.exists(out):
        out = os.path.join(company_dir, f"{time.strftime('%Y-%m-%d')}-{slug}-{n}.xlsx"); n += 1
    spec["out"] = out
    fd, tmp = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in spec.items() if v is not None}, fh)
    try:
        r = subprocess.run([sys.executable, QUOTE_TOOL, "--json", tmp], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if r.returncode != 0 or not os.path.exists(out):
        return 500, {"ok": False, "error": (r.stderr or r.stdout).strip()[-300:] or "quote tool failed"}
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("Quote written")]
    rel = os.path.relpath(out, quotes_dir).replace(os.sep, "/")
    return 200, {"ok": True, "file": rel, "path": out, "lines": lines}


def in_cloud():
    return bool(os.environ.get("CLAUDE_CODE_REMOTE") or os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID"))


def ups_show(review_dir, payload):
    """Raise the real UPS Calculate Time and Cost page in Chrome with this candidate's shipment."""
    if in_cloud():
        return 409, {"ok": False, "error": "The live UPS page opens only on your own computer."}
    if not shutil.which("node"):
        return 409, {"ok": False, "error": "Node.js is not installed, so the UPS page cannot be opened."}
    run = payload.get("run")
    if not isinstance(run, str) or not safe_name(run):
        return 400, {"ok": False, "error": "bad run name"}
    try:
        data = read_run(review_dir, run)
    except (OSError, ValueError):
        return 404, {"ok": False, "error": "run not found"}
    cand = next((c for c in data.get("candidates", []) if str(c.get("id")) == str(payload.get("candidateId"))), None)
    k = (cand or {}).get("carton") or {}
    if not cand or not cand.get("shipFromZip") or not k.get("lbs"):
        return 400, {"ok": False, "error": "this product has no ship-from ZIP or carton weight"}
    to = (data.get("request") or {}).get("shipTo")
    args = ["node", os.path.join(SHIP_TOOLS, "ups_ctc.mjs"), f"--from={cand['shipFromZip']}", f"--to={to}",
            f"--weight={float(k['lbs']):g}", "--show"]
    if k.get("L") and k.get("W") and k.get("H"):
        args += [f"--length={float(k['L']):g}", f"--width={float(k['W']):g}", f"--height={float(k['H']):g}"]
    try:
        subprocess.run([sys.executable, os.path.join(SHIP_TOOLS, "ups_chrome.py")], capture_output=True,
                       text=True, timeout=60, creationflags=HIDE)
        subprocess.Popen(args, cwd=SHIP_TOOLS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=HIDE)
    except (OSError, subprocess.SubprocessError) as exc:
        return 500, {"ok": False, "error": "could not start the UPS page: %s" % exc}
    return 202, {"ok": True, "message": "Opening the UPS quote in Chrome; it takes about 20 seconds."}


def export_html(folder, run=None, out=None):
    """Write one run into a copy of the page that works without this server."""
    runs = list_runs(folder)
    name = run or (runs[0]["file"] if runs else None)
    if not name or not safe_name(os.path.basename(name)):
        sys.exit("No sourcing run to export.")
    data = read_run(folder, os.path.basename(name))
    with open(INDEX, "r", encoding="utf-8") as fh:
        page = fh.read()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    anchor = "<script>\n(function () {"
    if anchor not in page:
        sys.exit("index.html changed; cannot find where to put the data")
    page = page.replace(anchor, "<script>window.__RUN__ = " + blob + ";</script>\n" + anchor, 1)
    out = out or os.path.join(folder, os.path.basename(name)[:-5] + ".html")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("Saved:", os.path.abspath(out))
    return out


class Handler(BaseHTTPRequestHandler):
    folder = REVIEW_DIR
    quotes = QUOTES_DIR
    trash = TRASH_DIR

    def log_message(self, fmt, *args):  # keep the console readable
        pass

    def _send(self, status, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            try:
                with open(INDEX, "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(500, "index.html is missing", "text/plain; charset=utf-8")
            return
        if path == "/favicon.svg":
            self._send(200, FAVICON, "image/svg+xml")
            return
        if path == "/api/runs":
            self._send(200, list_runs(self.folder))
            return
        if path == "/api/latest":
            runs = list_runs(self.folder)
            if not runs:
                self.send_response(204)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            self._send(200, read_run(self.folder, runs[0]["file"]))
            return
        if path == "/api/run":
            name = (parse_qs(url.query).get("f") or [""])[0]
            if not safe_name(name):
                self._send(400, {"error": "bad file name"})
                return
            try:
                self._send(200, read_run(self.folder, name))
            except (OSError, ValueError):
                self._send(404, {"error": "run not found"})
            return
        if path == "/api/quotes":
            self._send(200, list_quotes(self.quotes))
            return
        if path.startswith("/quotes/"):
            name = unquote(path[len("/quotes/"):])
            if not safe_rel(name):
                self._send(400, {"error": "bad file name"})
                return
            base = name.split("/")[-1].replace('"', "")
            try:
                with open(os.path.join(self.quotes, *name.split("/")), "rb") as fh:
                    self._send(200, fh.read(), XLSX, {"Content-Disposition": f'attachment; filename="{base}"'})
            except OSError:
                self._send(404, {"error": "quote not found"})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self._json_body()
        if payload is None:
            self._send(400, {"ok": False, "error": "body must be a JSON object"})
            return
        if path == "/api/quote":
            status, body = build_quote(self.folder, self.quotes, payload)
            self._send(status, body)
            return
        if path == "/api/ups-show":
            status, body = ups_show(self.folder, payload)
            self._send(status, body)
            return
        if path == "/api/quote/delete":
            name = payload.get("file")
            if payload.get("confirm") is not True:
                self._send(400, {"ok": False, "error": "confirm must be true"})
                return
            if not safe_rel(name):
                self._send(400, {"ok": False, "error": "bad file name"})
                return
            src = os.path.join(self.quotes, *name.split("/"))
            if not os.path.exists(src):
                self._send(404, {"ok": False, "error": "quote not found"})
                return
            trash = self.trash
            try:
                parts = name.split("/")
                dest_dir = os.path.join(trash, *parts[:-1])
                os.makedirs(dest_dir, exist_ok=True)
                os.replace(src, os.path.join(dest_dir, time.strftime("%Y%m%d-%H%M%S-") + parts[-1]))
            except OSError as exc:
                self._send(500, {"ok": False, "error": "could not delete: %s" % exc})
                return
            self._send(200, {"ok": True})
            return
        self._send(404, {"ok": False, "error": "not found"})


def main():
    if "--export" in sys.argv:
        i = sys.argv.index("--export")
        run = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else None
        out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
        export_html(_args()[1], run, out)
        return
    port, folder, quotes, trash = _args()
    Handler.folder = folder
    Handler.quotes = quotes
    Handler.trash = trash
    os.makedirs(folder, exist_ok=True)
    server = ThreadingHTTPServer((HOST, port), Handler)
    print("Sourcing review: http://%s:%d" % (HOST, port), flush=True)
    print("Run files: %s" % folder, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
