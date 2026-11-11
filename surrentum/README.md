# Surrentum mail stack (ListMonk + Stalwart as one component)

This folder is the only difference between this fork and `knadh/listmonk`. No ListMonk code is changed, so the
fork rebases cleanly and AGPL-3.0 section 13 is not triggered (the licence and notices are untouched anyway).

What it does, on the mail host:

- `mailstack up` backs up the ListMonk database, applies `docker-compose.surrentum.yml`, wires ListMonk to the local
  Stalwart (an app password for `newsletter@` pinned to the stack's container addresses, written straight into
  ListMonk's SMTP settings, never printed), and starts the bounce bridge.
- `mailstack health` is the one health check (Stalwart, ListMonk, database, local submission, bridge).
- `mailstack backup`, `rollback [dump]`, `test` (a campaign to a one-subscriber test list) and `verify`
  (SPF, DKIM and DMARC alignment from public DNS) complete the set.
- `mailstack/bridge.py` reads `newsletter@` over IMAP, parses delivery-failure and complaint reports
  (`mailstack/bounce.py`, unit tested in `tests/`) and posts them to ListMonk's bounce webhook.
- `systemd/` holds a nightly backup timer and a 10-minute health timer.

Needs on the host: Docker, the Stalwart mail server, and `/opt/staff-mail/staffmail_common.py` (Stalwart admin
helper). Credentials live in `/etc/mail-stack` (root only) and are never in this repository.

Docs: https://wiki.keffals.gg (Mail server and Newsletter pages), research.keffals.gg "ListMonk and Stalwart as one
component". Upstream sync plan: `UPSTREAM.md`.

Run the tests: `python3 -m unittest surrentum/tests/test_bounce.py`
