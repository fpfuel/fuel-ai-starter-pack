"""Read her meetings from Fireflies. Standard library only; the key comes from keys.py.

  python fireflies.py check            is the key there and does Fireflies accept it
  python fireflies.py list [--limit N] recent meetings: date, title, length, id
  python fireflies.py get ID [--out FILE.md]
                                       summary, action items and the transcript as markdown
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PACK_ROOT / ".claude" / "tools"))
import keys  # noqa: E402

ENDPOINT = "https://api.fireflies.ai/graphql"
LIST = """query($limit: Int) { transcripts(limit: $limit) {
  id title dateString duration participants summary { gist } } }"""
GET = """query($id: String!) { transcript(id: $id) {
  id title dateString duration participants
  summary { gist overview action_items keywords }
  sentences { speaker_name text start_time } } }"""


def call(query, variables):
    key = keys.get("FIREFLIES_API_KEY")
    if not key:
        sys.exit("No Fireflies key yet. Put FIREFLIES_API_KEY in secrets/keys.xlsx "
                 "(from app.fireflies.ai, Integrations, Fireflies API).")
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "starter-pack-meetings/1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            code = json.loads(e.read())["errors"][0].get("code", "")
        except (ValueError, KeyError, IndexError, TypeError):
            code = ""
        if e.code in (401, 403) or code == "auth_failed":
            sys.exit("Fireflies did not accept the key. Copy it again from Integrations, Fireflies API.")
        if e.code == 429:
            sys.exit("Fireflies says too many requests for now. Try again in a minute.")
        sys.exit(f"Fireflies answered with an error ({e.code}).")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach Fireflies ({e.reason}). In a cloud session, allow api.fireflies.ai.")
    if data.get("errors"):
        msg = data["errors"][0].get("message", "unknown error")
        if "auth" in msg.lower() or "api key" in msg.lower():
            sys.exit("Fireflies did not accept the key. Copy it again from Integrations, Fireflies API.")
        sys.exit(f"Fireflies error: {msg}")
    return data["data"]


def minutes(d):
    try:
        return f"{float(d):.0f} min"
    except (TypeError, ValueError):
        return ""


def stamp(seconds):
    s = int(float(seconds or 0))
    return f"{s // 60}:{s % 60:02d}"


def to_markdown(t):
    s = t.get("summary") or {}
    out = [f"# {t.get('title') or 'Meeting'}", "",
           f"- When: {(t.get('dateString') or '')[:16].replace('T', ' ')} UTC",
           f"- Length: {minutes(t.get('duration'))}",
           f"- Who: {', '.join(t.get('participants') or []) or 'not listed'}",
           f"- Recording: https://app.fireflies.ai/view/{t['id']}", ""]
    if s.get("overview") or s.get("gist"):
        out += ["## Summary", "", s.get("overview") or s.get("gist"), ""]
    if s.get("action_items"):
        out += ["## Action items (from Fireflies)", "", s["action_items"].strip(), ""]
    out += ["## Transcript", ""]
    last = None
    for line in t.get("sentences") or []:
        who = line.get("speaker_name") or "Speaker"
        if who != last:
            out += ["", f"**{who}** ({stamp(line.get('start_time'))})"]
            last = who
        out.append(line.get("text") or "")
    return "\n".join(out).strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    ls = sub.add_parser("list")
    ls.add_argument("--limit", type=int, default=10)
    g = sub.add_parser("get")
    g.add_argument("id")
    g.add_argument("--out")
    a = ap.parse_args()

    if a.cmd == "check":
        rows = call(LIST, {"limit": 5})["transcripts"] or []
        print(f"Fireflies key works. Recent meetings found: {len(rows)}"
              + ("" if rows else " (none yet; record one and check again)"))
    elif a.cmd == "list":
        rows = call(LIST, {"limit": max(1, min(a.limit, 50))})["transcripts"] or []
        if not rows:
            print("No meetings in Fireflies yet.")
        for r in rows:
            print(f"{(r.get('dateString') or '')[:10]}  {minutes(r.get('duration')):>7}  {r.get('title') or '(untitled)'}  [{r['id']}]")
    else:
        t = call(GET, {"id": a.id})["transcript"]
        if not t:
            sys.exit("No meeting with that id in this Fireflies account.")
        md = to_markdown(t)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(md, encoding="utf-8")
            print(f"Saved {a.out}")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(md)


if __name__ == "__main__":
    main()
