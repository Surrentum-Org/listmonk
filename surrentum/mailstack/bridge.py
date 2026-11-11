#!/usr/bin/env python3
"""Bounce bridge: newsletter@ mailbox (Stalwart IMAP) -> ListMonk bounce webhook.

Runs in the stack as its own container. Reads unseen mail every MAILSTACK_POLL
seconds, posts each recognised failure or complaint, marks it seen. Never logs a
secret or a mail body.
"""
import imaplib
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from bounce import parse  # noqa: E402

HOST = os.environ.get("MAILSTACK_MAIL_HOST", "mail.keffals.gg")
POLL = int(os.environ.get("MAILSTACK_POLL", "60"))
LISTMONK = os.environ.get("MAILSTACK_LISTMONK", "http://app:9000")
SMTP_STORE = os.environ.get("MAILSTACK_SMTP_STORE", "/run/mailstack/newsletter.json")
API_STORE = os.environ.get("MAILSTACK_API_STORE", "/run/mailstack/listmonk-api.json")


def post_bounce(api, b):
    body = json.dumps({k: v for k, v in b.items() if v is not None}).encode()
    req = urllib.request.Request(
        LISTMONK + "/webhooks/bounce", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"token {api['user']}:{api['token']}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def run_once():
    smtp = json.load(open(SMTP_STORE))
    api = json.load(open(API_STORE))
    im = imaplib.IMAP4_SSL(HOST, 993)
    try:
        im.login(smtp["user"], smtp["secret"])
        done = 0
        # Reports from other mail systems sometimes land in Junk; read both.
        for box in ('INBOX', '"Junk Mail"'):
            if im.select(box)[0] != "OK":
                continue
            _, data = im.search(None, "UNSEEN")
            for num in data[0].split():
                _, msgdata = im.fetch(num, "(BODY.PEEK[])")
                raw = msgdata[0][1]
                ok = True
                for b in parse(raw):
                    try:
                        post_bounce(api, b)
                        done += 1
                    except Exception as e:  # unknown subscriber is a 4xx: nothing to record
                        ok = ok and getattr(e, "code", 0) in (400, 404)
                if ok:
                    im.store(num, "+FLAGS", "\\Seen")
        return done
    finally:
        try:
            im.logout()
        except Exception:
            pass


def main():
    once = "--once" in sys.argv
    while True:
        try:
            n = run_once()
            print(f"bridge: posted {n} bounce(s)", flush=True)
        except Exception as e:
            print(f"bridge: error {type(e).__name__}", flush=True)
        if once:
            return
        time.sleep(POLL)


if __name__ == "__main__":
    main()
