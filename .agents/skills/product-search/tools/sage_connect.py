"""SAGE Connect API client. Product search, product detail, inventory.

Her account details come from secrets/keys.xlsx (or environment variables of the same name)
through .claude/tools/keys.py: SAGE_ACCT_ID, SAGE_LOGIN_ID, SAGE_API_KEY, and optionally
SAGE_ENDPOINT. Nothing secret is printed. Search and detail calls count against the account's
monthly query credit, so keep record counts small.

Usage (from the pack folder):
  python .claude/skills/product-search/tools/sage_connect.py search "pull apart keyring" --qty 150 --max-price 5 --n 8
  python .claude/skills/product-search/tools/sage_connect.py detail <prodEId>
  python .claude/skills/product-search/tools/sage_connect.py inventory <prodEId>
  add --json to dump the raw response, --save to keep it under .tmp/sage/
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PACK_ROOT / ".claude" / "tools"))
import keys  # noqa: E402

DEFAULT_ENDPOINT = "https://www.promoplace.com/ws/ws.dll/ConnectAPI"
API_VER = 130
TMP = PACK_ROOT / ".tmp" / "sage"


_AUTH = None
FIELDS = ("SAGE_CONNECT_ENDPOINT", "SAGE_CONNECT_ACCT_ID", "SAGE_CONNECT_LOGIN_ID", "SAGE_CONNECT_KEY")


def vault_auth() -> dict:
    """Her SAGE Connect details from the keys file; cached for the process. Values never printed."""
    global _AUTH
    if _AUTH is not None:
        return _AUTH
    found = {
        "SAGE_CONNECT_ENDPOINT": keys.get("SAGE_ENDPOINT") or DEFAULT_ENDPOINT,
        "SAGE_CONNECT_ACCT_ID": keys.get("SAGE_ACCT_ID"),
        "SAGE_CONNECT_LOGIN_ID": keys.get("SAGE_LOGIN_ID"),
        "SAGE_CONNECT_KEY": keys.get("SAGE_API_KEY"),
    }
    missing = [n for n, k in (("SAGE_ACCT_ID", "SAGE_CONNECT_ACCT_ID"), ("SAGE_LOGIN_ID", "SAGE_CONNECT_LOGIN_ID"),
                              ("SAGE_API_KEY", "SAGE_CONNECT_KEY")) if not found[k]]
    if missing:
        sys.exit("SAGE is not set up yet. Add " + ", ".join(missing) + " to secrets/keys.xlsx "
                 "(account number, login and API key from sagemember.com, Users tab).")
    _AUTH = found
    return _AUTH


def vault_field(name: str) -> str:
    return vault_auth()[name]


def call(service_id: int, body: dict, dry_run: bool = False) -> dict:
    endpoint = vault_field("SAGE_CONNECT_ENDPOINT")
    payload = {"serviceId": service_id, "apiVer": API_VER, **body}
    if dry_run:
        print(json.dumps({**payload, "auth": "<from keys file>"}, indent=1))
        return {}
    payload["auth"] = {"acctId": int(vault_field("SAGE_CONNECT_ACCT_ID")),
                       "loginId": vault_field("SAGE_CONNECT_LOGIN_ID"),
                       "key": vault_field("SAGE_CONNECT_KEY")}
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "fuel-starter-pack/1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", "replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"non-JSON response ({len(raw)} chars): {raw[:300]}")
    if data.get("ok") is False or data.get("errNum"):
        sys.exit(f"API error {data.get('errNum')}: {data.get('errMsg')}")
    return data


def api_search(query: str, qty=None, n: int = 12, min_price=None, max_price=None, sort: str = "POPULARITY") -> dict:
    search = {"quickSearch": query, "maxRecs": n, "startNum": 1, "maxTotalItems": max(n, 50), "sort": sort,
              "extraReturnFields": "ITEMNUM,SUPPLIER,SUPPID,NET,PRODTIME"}
    if qty: search["qty"] = int(qty)
    if min_price is not None: search["priceLow"] = float(min_price)
    if max_price is not None: search["priceHigh"] = float(max_price)
    return call(103, {"search": search})


def api_detail(prod_eid) -> dict:
    return call(105, {"prodEId": int(prod_eid), "includeSuppInfo": 1})


def money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v or "")


def cmd_search(a) -> dict:
    search = {"quickSearch": a.query, "maxRecs": a.n, "startNum": 1, "maxTotalItems": max(a.n, 50),
              "sort": a.sort, "extraReturnFields": "ITEMNUM,SUPPLIER,SUPPID,NET,PRODTIME"}
    if a.qty:
        search["qty"] = a.qty
    if a.max_price:
        search["priceHigh"] = a.max_price
    if a.min_price:
        search["priceLow"] = a.min_price
    if a.category:
        search["categories"] = a.category
    if a.made_in:
        search["madeIn"] = a.made_in
    data = call(103, {"search": search}, a.dry_run)
    if not data:
        return data
    print(f"totalFound {data.get('totalFound')}  showing {len(data.get('products', []))}  "
          f"qty {a.qty or '-'}  max ${a.max_price or '-'}")
    print(f"{'prodEId':>10}  {'item#':<14} {'price':>8} {'net':>8}  {'supplier':<28} name")
    for p in data.get("products", []):
        net = p.get("net")
        if isinstance(net, dict):
            net = (net.get("net") or [""])[0] if isinstance(net.get("net"), list) else net.get("net")
        print(f"{p.get('prodEId'):>10}  {str(p.get('itemNum', ''))[:14]:<14} {money(p.get('prc')):>8} {money(net):>8}  "
              f"{str(p.get('supplier') or p.get('line') or '')[:28]:<28} {str(p.get('name', ''))[:60]}")
    return data


def cmd_detail(a) -> dict:
    data = call(105, {"prodEId": int(a.prod_eid), "includeSuppInfo": 1}, a.dry_run)
    if not data:
        return data
    p = data.get("product", {})
    print(f"{p.get('prName')}  item# {p.get('itemNum')}  SPC {p.get('spc')}")
    print(f"supplier SAGE {p.get('suppId')}  line {p.get('lineName')}  category {p.get('category')}")
    qty, prc, net, cat = p.get("qty", []), p.get("prc", []), p.get("net", []), p.get("catPrc", [])
    print(f"{'qty':>8} {'price':>9} {'catalog':>9} {'net':>9}")
    for i, q in enumerate(qty):
        if str(q) in ("", "0"):
            continue
        print(f"{q:>8} {money(prc[i] if i < len(prc) else ''):>9} {money(cat[i] if i < len(cat) else ''):>9} {money(net[i] if i < len(net) else ''):>9}")
    print(f"price code {p.get('priceCode')}  currency {p.get('currency')}  price includes: {p.get('priceIncludes')}")
    for k in ("setupChg", "repeatSetupChg", "addClrChg", "addClrRunChg", "screenChg", "pmsCharge", "proofCharge"):
        if p.get(k) not in (None, "", 0, "0", "0.00", []):
            print(f"  {k}: {p.get(k)} {p.get(k + 'Code', '')}")
    print(f"carton: {p.get('unitsPerCarton')} units, {p.get('weightPerCarton')} lb, "
          f"{p.get('cartonL')}x{p.get('cartonW')}x{p.get('cartonH')} in")
    print(f"ships from {p.get('shipPointZip')} {p.get('shipPointCountry')}  made in {p.get('madeInCountry') or '?'}  "
          f"decorated in {p.get('decoratedInCountry') or '?'}  production {p.get('prodTime')}")
    sup = data.get("supplier") or p.get("supplier") or {}
    if isinstance(sup, dict) and sup:
        print(f"supplier: {sup.get('coName') or sup.get('name')}  {sup.get('city', '')} {sup.get('state', '')}  "
              f"{sup.get('tel') or sup.get('phone', '')}  {sup.get('web') or sup.get('website', '')}")
    return data


def cmd_inventory(a) -> dict:
    data = call(107, {"products": [{"productId": int(a.prod_eid)}]}, a.dry_run)
    if data:
        print(json.dumps(data.get("products"), indent=1)[:3000])
    return data


def cmd_research(a) -> dict:
    data = call(101, {"fieldName": a.field}, a.dry_run)
    if data:
        print(json.dumps(data, indent=1)[:4000])
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the raw response")
    ap.add_argument("--save", action="store_true", help="save the raw response under .tmp/sage/")
    ap.add_argument("--dry-run", action="store_true", help="print the request, send nothing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--qty", type=int)
    s.add_argument("--max-price", type=float)
    s.add_argument("--min-price", type=float)
    s.add_argument("--category")
    s.add_argument("--made-in", help="two-letter country code")
    s.add_argument("--sort", default="PRICE", choices=["PRICE", "PRICEHIGHLOW", "BESTMATCH", "POPULARITY", "PREFGROUP"])
    s.add_argument("--n", type=int, default=8, help="records to return (each call is one query regardless)")
    s.set_defaults(fn=cmd_search)
    d = sub.add_parser("detail")
    d.add_argument("prod_eid")
    d.set_defaults(fn=cmd_detail)
    i = sub.add_parser("inventory")
    i.add_argument("prod_eid")
    i.set_defaults(fn=cmd_inventory)
    r = sub.add_parser("research-list")
    r.add_argument("field", help="categories, themes, colors, ...")
    r.set_defaults(fn=cmd_research)
    a = ap.parse_args()
    data = a.fn(a)
    if data and a.json:
        print(json.dumps(data, indent=1))
    if data and a.save:
        TMP.mkdir(parents=True, exist_ok=True)
        out = TMP / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{a.cmd}.json"
        out.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"saved {out}")


if __name__ == "__main__":
    main()
