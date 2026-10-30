"""Create, read and delete Pipedrive records from the command line.

Standard library only (urllib). The API token comes from .claude/tools/keys.py
(environment variable or secrets/keys.xlsx) or, with --from-vault, from
a Proton Pass vault named by PIPEDRIVE_VAULT_NAME and PIPEDRIVE_VAULT_ITEM, read in-process. The token is never printed,
never put in a URL, a filename or an error message.

Endpoints (developers.pipedrive.com/docs/api/v1/{Persons,Organizations,Activities,Users}):
  GET    /api/v1/users/me
  GET    /api/v2/organizations/search?term=&fields=name&exact_match=true
  POST   /api/v2/organizations          {name}
  POST   /api/v2/persons                {name, org_id, emails[], phones[]}
  POST   /api/v2/activities             {subject, type, due_date, note, org_id, participants[]}
  GET    /api/v2/{persons|organizations|activities}/{id}
  DELETE /api/v2/{persons|organizations|activities}/{id}

Usage:
  pipedrive_api.py whoami [--from-vault]
  pipedrive_api.py add --name "Pat Sample" --org "Sample Contracting" --email x --phone y
                       --title "Owner" --activity "Locker forms quote" --type task
                       --due 2026-11-03 --note "..." [--dry-run] [--from-vault]
  pipedrive_api.py get    [--person ID] [--org ID] [--activity ID] [--from-vault]
  pipedrive_api.py delete [--person ID] [--org ID] [--activity ID] [--from-vault]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PACK_ROOT / ".claude" / "tools"))
import keys  # noqa: E402

GENERIC_HOST = "https://api.pipedrive.com"
VAULT_CMD = ["pass-cli", "item", "view", "--vault-name", os.environ.get("PIPEDRIVE_VAULT_NAME", ""),
             "--item-title", os.environ.get("PIPEDRIVE_VAULT_ITEM", ""), "--field"]
ACTIVITY_TYPES = ("call", "meeting", "task", "deadline", "email", "lunch")


# ---------------------------------------------------------------- credentials

class Client:
    def __init__(self, token, domain=None):
        self._token = token
        self.domain = domain

    @property
    def base(self):
        return f"https://{self.domain}.pipedrive.com" if self.domain else GENERIC_HOST

    def mask(self, text):
        if not text:
            return text
        return text.replace(self._token, "<token>")

    def request(self, method, path, body=None, params=None):
        """Return (status, parsed_json_or_text). Never raises on HTTP errors."""
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("x-api-token", self._token)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status, raw = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read().decode("utf-8", "replace")
        except urllib.error.URLError as e:
            print(f"network error on {method} {url}: {self.mask(str(e.reason))}")
            sys.exit(2)
        raw = self.mask(raw)
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw

    def call(self, method, path, body=None, params=None):
        """request() plus: print status and body and exit on a non-2xx answer."""
        status, data = self.request(method, path, body, params)
        if status >= 300:
            print(f"{method} {path} failed with HTTP {status}")
            print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)
            sys.exit(1)
        return data


def _vault_field(name):
    r = subprocess.run(VAULT_CMD + [name], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"vault read of field '{name}' failed (rc {r.returncode}); "
              "run `pass-cli login` and retry")
        sys.exit(2)
    return r.stdout.strip()


def _domain_from_note(note):
    m = re.search(r"([A-Za-z0-9][A-Za-z0-9-]*)\.pipedrive\.com", note or "")
    host = m.group(1).lower() if m else None
    return None if host in (None, "app", "api", "www") else host


def _domain_from_api(client):
    me = client.call("GET", "/api/v1/users/me")
    return me["data"]["company_domain"]


def load_client(from_vault):
    if from_vault:
        token = _vault_field("Pipedrive API")
        domain = _domain_from_note(_vault_field("note"))
    else:
        token = keys.get("PIPEDRIVE_API_TOKEN")
        domain = keys.get("PIPEDRIVE_DOMAIN")
    if not token:
        print("No Pipedrive token found. Put PIPEDRIVE_API_TOKEN in secrets/keys.xlsx "
              "(copy secrets/keys.example.xlsx) or set it as an environment variable.")
        sys.exit(3)
    client = Client(token, domain)
    if not client.domain:
        client.domain = _domain_from_api(client)
    return client


# ----------------------------------------------------------------- helpers

def app_url(client, kind, rec_id):
    return f"{client.base}/{kind}/{rec_id}"


def show(label, rec_id, url):
    print(f"{label}: id {rec_id}  {url}")


def dry(method, path, body=None, params=None, note=None):
    url = path + ("?" + urllib.parse.urlencode(params) if params else "")
    print(f"{method} {url}")
    if body is not None:
        print(json.dumps(body, indent=2))
    if note:
        print(f"  ({note})")
    print()


def find_org(client, name):
    """Exact-name match (case-insensitive) via v2 organizations search."""
    params = {"term": name, "fields": "name", "exact_match": "true", "limit": 20}
    data = client.call("GET", "/api/v2/organizations/search", params=params)
    for it in (data.get("data") or {}).get("items") or []:
        item = it.get("item") or {}
        if (item.get("name") or "").strip().lower() == name.strip().lower():
            # search also returns organizations deleted within the last 30 days
            status, rec = client.request("GET", f"/api/v2/organizations/{item['id']}")
            if status == 200 and not (rec.get("data") or {}).get("is_deleted"):
                return item["id"]
    return None


# ----------------------------------------------------------------- commands

def cmd_whoami(args):
    client = load_client(args.from_vault)
    me = client.call("GET", "/api/v1/users/me")["data"]
    print(f"user: {me.get('name')}")
    print(f"company domain: {me.get('company_domain')}")


def cmd_add(args):
    if args.type not in ACTIVITY_TYPES:
        print(f"--type must be one of {', '.join(ACTIVITY_TYPES)}")
        sys.exit(1)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.due or ""):
        print("--due must be YYYY-MM-DD")
        sys.exit(1)

    person_body = {"name": args.name}
    if args.email:
        person_body["emails"] = [{"value": args.email, "primary": True, "label": "work"}]
    if args.phone:
        person_body["phones"] = [{"value": args.phone, "primary": True, "label": "work"}]
    note = args.note or ""
    if args.title:
        # job_title on a person is contact-sync only (403 otherwise), so the
        # title travels in the activity note instead.
        note = f"{args.name}, {args.title}" + (f"\n{note}" if note else "")
    activity_body = {"subject": args.activity, "type": args.type, "due_date": args.due}
    if note:
        activity_body["note"] = note

    org_search = {"term": args.org, "fields": "name", "exact_match": "true", "limit": 20}

    if args.dry_run:
        print(f"DRY RUN against {client_base_for_dry(args)}; nothing is sent.\n")
        dry("GET", "/api/v2/organizations/search", params=org_search,
            note="if an organization with exactly this name exists, its id is reused")
        dry("POST", "/api/v2/organizations", {"name": args.org},
            note="only if the search above finds nothing")
        person_body["org_id"] = "<org id>"
        dry("POST", "/api/v2/persons", person_body)
        activity_body["org_id"] = "<org id>"
        activity_body["participants"] = [{"person_id": "<person id>", "primary": True}]
        dry("POST", "/api/v2/activities", activity_body)
        return

    client = load_client(args.from_vault)
    org_id = find_org(client, args.org)
    if org_id:
        show("organization (existing)", org_id, app_url(client, "organization", org_id))
    else:
        org = client.call("POST", "/api/v2/organizations", {"name": args.org})["data"]
        org_id = org["id"]
        show("organization (created)", org_id, app_url(client, "organization", org_id))

    person_body["org_id"] = org_id
    person = client.call("POST", "/api/v2/persons", person_body)["data"]
    person_id = person["id"]
    show("person (created)", person_id, app_url(client, "person", person_id))

    activity_body["org_id"] = org_id
    activity_body["participants"] = [{"person_id": person_id, "primary": True}]
    act = client.call("POST", "/api/v2/activities", activity_body)["data"]
    act_id = act["id"]
    show("activity (created)", act_id,
         f"{app_url(client, 'person', person_id)}  (activity #{act_id} is on the person's page)")


def client_base_for_dry(args):
    if args.from_vault:
        return "<company>.pipedrive.com (vault)"
    d = keys.get("PIPEDRIVE_DOMAIN")
    return f"{d}.pipedrive.com" if d else "<company>.pipedrive.com"


def _targets(args):
    out = []
    if args.person:
        out.append(("person", "persons", args.person))
    if args.org:
        out.append(("organization", "organizations", args.org))
    if args.activity:
        out.append(("activity", "activities", args.activity))
    if not out:
        print("give at least one of --person ID, --org ID, --activity ID")
        sys.exit(1)
    return out


def cmd_get(args):
    client = load_client(args.from_vault)
    for label, coll, rec_id in _targets(args):
        status, data = client.request("GET", f"/api/v2/{coll}/{rec_id}")
        print(f"GET {label} {rec_id}: HTTP {status}")
        rec = data.get("data") if isinstance(data, dict) else None
        if rec:
            keep = {k: rec.get(k) for k in
                    ("id", "name", "org_id", "emails", "phones", "subject", "type",
                     "due_date", "note", "person_id", "participants", "is_deleted")
                    if k in rec}
            print(json.dumps(keep, indent=2))
        else:
            print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)


def cmd_delete(args):
    client = load_client(args.from_vault)
    for label, coll, rec_id in _targets(args):
        status, data = client.request("DELETE", f"/api/v2/{coll}/{rec_id}")
        ok = status < 300 and isinstance(data, dict) and data.get("success")
        print(f"DELETE {label} {rec_id}: HTTP {status} {'deleted' if ok else 'FAILED'}")
        if not ok:
            print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)


# ----------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--from-vault", action="store_true",
                        help="read the token from a Proton Pass vault (PIPEDRIVE_VAULT_NAME, PIPEDRIVE_VAULT_ITEM) instead of the keys file")

    sp = sub.add_parser("whoami", help="print the user name and company domain")
    common(sp)
    sp.set_defaults(fn=cmd_whoami)

    sp = sub.add_parser("add", help="find-or-create org, create person, create activity")
    sp.add_argument("--name", required=True)
    sp.add_argument("--org", required=True)
    sp.add_argument("--email")
    sp.add_argument("--phone")
    sp.add_argument("--title")
    sp.add_argument("--activity", required=True, help="activity subject")
    sp.add_argument("--type", default="task", help=", ".join(ACTIVITY_TYPES))
    sp.add_argument("--due", required=True, help="YYYY-MM-DD")
    sp.add_argument("--note")
    sp.add_argument("--dry-run", action="store_true")
    common(sp)
    sp.set_defaults(fn=cmd_add)

    for name, fn, h in (("get", cmd_get, "fetch records by id"),
                        ("delete", cmd_delete, "delete records by id")):
        sp = sub.add_parser(name, help=h)
        sp.add_argument("--person", type=int)
        sp.add_argument("--org", type=int)
        sp.add_argument("--activity", type=int)
        common(sp)
        sp.set_defaults(fn=fn)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
