"""Shared helpers for the Surrentum mail stack (ListMonk + Stalwart as one component).

Runs on the mail host (kgg-vps). Never prints a secret.
"""
import json
import os
import subprocess
import tempfile

STORE_DIR = os.environ.get("MAILSTACK_STORE", "/etc/mail-stack")
SMTP_STORE = os.path.join(STORE_DIR, "newsletter.json")  # Stalwart app password for newsletter@
API_STORE = os.path.join(STORE_DIR, "listmonk-api.json")  # ListMonk API user for the bridge and self-test
APP_IP = os.environ.get("MAILSTACK_APP_IP", "172.23.43.2")
BRIDGE_IP = os.environ.get("MAILSTACK_BRIDGE_IP", "172.23.43.3")
GATEWAY_IP = os.environ.get("MAILSTACK_GATEWAY_IP", "172.23.43.1")
MAIL_HOST = os.environ.get("MAILSTACK_MAIL_HOST", "mail.keffals.gg")
ACCOUNT = "newsletter"
ADDRESS = "newsletter@keffals.gg"
PG_CONTAINER = os.environ.get("MAILSTACK_PG_CONTAINER", "listmonk-db")


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(path, data):
    """Atomic write, mode 0600, directory 0700."""
    d = os.path.dirname(path)
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(d, 0o700)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def psql(sql):
    """Run SQL in the ListMonk database. The SQL goes in on stdin, never argv."""
    out = subprocess.run(
        ["docker", "exec", "-i", PG_CONTAINER, "psql", "-U", "listmonk", "-d", "listmonk",
         "-v", "ON_ERROR_STOP=1", "-At"],
        input=sql, capture_output=True, text=True, check=True)
    return out.stdout


def lit(value):
    """SQL string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def log(*parts):
    print("mailstack:", *parts, flush=True)
