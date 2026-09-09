#!/usr/bin/env python3
"""Dev convenience: recreate the household/owner, extra members and entities
after `./fm reset`, so a fresh volume doesn't mean re-filling forms by hand.

Every write goes through the same public HTTP API the browser uses (POST
/api/setup, POST /api/members, POST /api/entities) — no direct database
access, no new backend capability. Idempotent: re-running skips whatever
already exists (matched by email for members, by name for entities), so it's
safe to add a member/entity to the data file and re-run without duplicating
what's already there.

    ./dev/bootstrap-household.py

Data file: dev/bootstrap-household.json (copied from the .example on first
run; gitignored, so a local password never lands in the repository — see
docs/decisions/0011-first-run-setup-over-seeded-credentials.md).
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "dev" / "bootstrap-household.json"
EXAMPLE_FILE = DATA_FILE.with_suffix(".json.example")


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def main() -> None:
    env = read_env()
    if env.get("APP_ENV", "development") != "development":
        sys.exit(f"Refusing to run: APP_ENV is '{env.get('APP_ENV')}', not 'development'.")

    if not DATA_FILE.exists():
        shutil.copyfile(EXAMPLE_FILE, DATA_FILE)
        print(f"Created {DATA_FILE.relative_to(ROOT)} from the .example")
    data = json.loads(DATA_FILE.read_text())

    base_url = f"http://localhost:{env.get('API_PORT', '8000')}/api"
    # Ignores any http_proxy/https_proxy in the environment: those are for
    # reaching the internet, never for a container publishing to localhost.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(CookieJar()),
    )

    def call(method: str, path: str, payload: dict | None = None, csrf: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(base_url + path, data=body, headers=headers, method=method)
        try:
            with opener.open(request) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            sys.exit(f"{method} {path} -> HTTP {exc.code}: {detail}")

    print(f"Waiting for the API on {base_url}...")
    for _ in range(30):
        try:
            with opener.open(urllib.request.Request(base_url + "/health")):
                break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(1)
    else:
        sys.exit("API never became healthy.")

    owner = data["owner"]
    status = call("GET", "/setup/status")
    if status["needs_setup"]:
        session = call("POST", "/setup", owner)
        print(f"Owner created: {owner['display_name']} <{owner['email']}>")
    else:
        session = call(
            "POST", "/auth/login", {"email": owner["email"], "password": owner["password"]}
        )
    csrf = session["csrf_token"]

    members = call("GET", "/members")
    name_to_id = {m["display_name"]: m["user_id"] for m in members}
    email_to_id = {m["email"]: m["user_id"] for m in members if m["email"]}

    for member in data.get("members", []):
        if member["email"] in email_to_id:
            print(f"Member already exists, skipping: {member['display_name']}")
            continue
        created = call("POST", "/members", member, csrf=csrf)
        name_to_id[created["display_name"]] = created["user_id"]
        email_to_id[created["email"]] = created["user_id"]
        print(f"Member created: {member['display_name']} <{member['email']}>")

    existing_entities = {e["name"] for e in call("GET", "/entities")}
    for entity in data.get("entities", []):
        if entity["name"] in existing_entities:
            print(f"Entity already exists, skipping: {entity['name']}")
            continue
        try:
            member_ids = [name_to_id[name] for name in entity["members"]]
        except KeyError as exc:
            sys.exit(f"Entity '{entity['name']}' references unknown member {exc}.")
        payload = {"name": entity["name"], "member_ids": member_ids, "color": entity.get("color")}
        call("POST", "/entities", payload, csrf=csrf)
        print(f"Entity created: {entity['name']} ({', '.join(entity['members'])})")


if __name__ == "__main__":
    main()
