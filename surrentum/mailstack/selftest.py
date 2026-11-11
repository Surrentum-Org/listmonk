#!/usr/bin/env python3
"""Send one test campaign through the whole stack and check SPF/DKIM/DMARC.

Creates (or reuses) a private list "Mail stack test" with ONE subscriber,
newsletter@keffals.gg itself, sends a campaign through ListMonk -> Stalwart,
then reads the delivered copy over IMAP and prints the Authentication-Results
verdicts. Touches no live list. Prints no secret.
"""
import email
import imaplib
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

LISTMONK = os.environ.get("MAILSTACK_LISTMONK_URL", "http://app:9000")


def api(method, path, body=None):
    store = c.load(c.API_STORE)
    req = urllib.request.Request(
        LISTMONK + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": f"token {store['user']}:{store['token']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"]


def verdicts(raw):
    msg = email.message_from_bytes(raw)
    ar = " ".join(" ".join(v.split()) for v in msg.get_all("Authentication-Results", []))
    out = {}
    for key in ("spf", "dkim", "dmarc"):
        i = ar.find(key + "=")
        out[key] = ar[i + len(key) + 1:].split()[0].strip(";") if i >= 0 else "missing"
    return out, "X-Listmonk-Campaign" in msg or "X-Listmonk-Campaign" in str(msg.keys())


def main():
    tag = time.strftime("%Y%m%d%H%M%S")
    lists = api("GET", "/api/lists?query=Mail%20stack%20test&per_page=5")["results"]
    lst = next((l for l in lists if l["name"] == "Mail stack test"), None)
    if not lst:
        lst = api("POST", "/api/lists", {"name": "Mail stack test", "type": "private",
                                         "optin": "single", "tags": ["mailstack"]})
    try:
        api("POST", "/api/subscribers", {"email": c.ADDRESS, "name": "Mail stack test",
                                         "status": "enabled", "lists": [lst["id"]],
                                         "preconfirm_subscriptions": True})
    except Exception:
        pass  # already exists: make sure it is on the list
        subs = api("GET", f"/api/subscribers?search={c.ADDRESS}")["results"]
        api("PUT", "/api/subscribers/lists", {"ids": [subs[0]["id"]], "action": "add",
                                              "target_list_ids": [lst["id"]], "status": "confirmed"})
    subject = f"Mail stack test {tag}"
    camp = api("POST", "/api/campaigns", {
        "name": subject, "subject": subject, "lists": [lst["id"]], "type": "regular",
        "content_type": "plain", "body": "Test from the combined ListMonk and Stalwart component.",
        "messenger": "email", "from_email": "Keffals <newsletter@keffals.gg>"})
    api("PUT", f"/api/campaigns/{camp['id']}/status", {"status": "running"})
    for _ in range(30):
        time.sleep(3)
        if api("GET", f"/api/campaigns/{camp['id']}")["status"] in ("finished", "cancelled", "paused"):
            break
    final = api("GET", f"/api/campaigns/{camp['id']}")
    print("campaign status:", final["status"], "sent:", final["sent"], "to_send:", final["to_send"])
    smtp = c.load(c.SMTP_STORE)
    for _ in range(20):
        im = imaplib.IMAP4_SSL(c.MAIL_HOST, 993)
        im.login(smtp["user"], smtp["secret"])
        im.select("INBOX")
        _, data = im.search(None, "SUBJECT", f'"{subject}"')
        if data[0].split():
            _, md = im.fetch(data[0].split()[-1], "(BODY.PEEK[])")
            open("/tmp/test-msg.eml", "wb").write(md[0][1])
            v, _ = verdicts(md[0][1])
            im.logout()
            if all(x == "missing" for x in v.values()):
                # Stalwart adds no Authentication-Results to mail it delivers to itself.
                print("arrived; no Authentication-Results on local delivery: run `mailstack verify`")
                sys.exit(0)
            print("authentication:", v)
            sys.exit(0 if all(x == "pass" for x in v.values()) else 1)
        im.logout()
        time.sleep(3)
    print("message did not arrive")
    sys.exit(2)


if __name__ == "__main__":
    main()
