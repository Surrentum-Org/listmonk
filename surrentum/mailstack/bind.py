#!/usr/bin/env python3
"""Wire ListMonk to Stalwart: one sending credential, one API user, no typed-in passwords.

1. Stalwart: an app password for newsletter@ pinned to ListMonk's and the bridge's
   container addresses (useless from anywhere else), kept in /etc/mail-stack (0600).
2. ListMonk: its SMTP entry gets that password straight from the store, the bounce
   webhook is switched on, and an API user `mailstack` is made for the bridge and
   the self-test.
Idempotent. Needs /opt/staff-mail (staffmail_common) and the Stalwart admin file,
both root only. Prints status words only.
"""
import hashlib
import os
import re
import secrets
import sys

sys.path.insert(0, os.environ.get("STAFF_MAIL_DIR", "/opt/staff-mail"))
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from staffmail_common import ADMIN_USING, basic, jmap, responses  # noqa: E402

import common as c  # noqa: E402

ADMIN_CREDS = os.environ.get("STAFF_MAIL_ADMIN_CREDS", "/etc/stalwart/admin-credentials.txt")
APP_DESCRIPTION = "mail-stack (ListMonk + bounce bridge, pinned to the stack network)"
API_PERMS = ("webhooks:post_bounce,lists:get_all,lists:manage_all,campaigns:get_all,"
             "campaigns:manage_all,campaigns:get,campaigns:manage,campaigns:send,"
             "subscribers:get_all,subscribers:manage,subscribers:get,templates:get,bounces:get")


class Admin:
    def __init__(self):
        text = open(ADMIN_CREDS).read()
        user = re.search(r"^user:\s*(\S+)", text, re.M).group(1)
        password = re.search(r"^password:\s*(\S+)", text, re.M).group(1)
        self.auth = basic(user, password)

    def call(self, calls):
        return responses(jmap(self.auth, calls, using=ADMIN_USING))

    def account_id(self, name):
        r = self.call([["x:Account/get", {"accountId": "b", "properties": ["name", "@type"]}, "0"]])
        for a in r["0"]["list"]:
            if a["name"] == name and a.get("@type") == "User":
                return a["id"]
        raise RuntimeError(f"account {name} not found; create it first")

    def app_passwords(self, account_id):
        r = self.call([["x:AppPassword/get", {"accountId": account_id}, "0"]])
        return {a["id"]: a for a in r["0"]["list"]}

    def destroy_app_password(self, account_id, app_id):
        self.call([["x:AppPassword/set", {"accountId": account_id, "destroy": [app_id]}, "0"]])

    def create_app_password(self, account_id):
        ips = {c.APP_IP: True, c.BRIDGE_IP: True}
        r = self.call([["x:AppPassword/set", {"accountId": account_id, "create": {"a": {
            "description": APP_DESCRIPTION, "allowedIps": ips}}}, "0"]])
        created = r["0"].get("created", {}).get("a")
        if not created:
            raise RuntimeError(f"could not create the app password: {r['0'].get('notCreated')}")
        return created["id"], created["secret"]


def ensure_smtp_credential(admin, rotate=False):
    store = c.load(c.SMTP_STORE)
    acct = admin.account_id(c.ACCOUNT)
    apps = admin.app_passwords(acct)
    if rotate or not store.get("secret") or store.get("app_id") not in apps:
        # Remove any earlier one of ours so only one credential exists.
        for aid, a in apps.items():
            if a.get("description") == APP_DESCRIPTION:
                admin.destroy_app_password(acct, aid)
        store["app_id"], store["secret"] = admin.create_app_password(acct)
        store["user"] = c.ADDRESS
        c.save(c.SMTP_STORE, store)
        c.log("created the newsletter@ app password (pinned to the stack network)")
    else:
        c.log("newsletter@ app password already present")
    return store


def set_listmonk_smtp(store):
    """Write the credential into ListMonk's SMTP settings and enable bounce webhooks."""
    sql = f"""
update settings set value = (
  select jsonb_agg(
    jsonb_set(jsonb_set(jsonb_set(elem, '{{host}}', to_jsonb({c.lit(c.MAIL_HOST)}::text)),
      '{{username}}', to_jsonb({c.lit(store['user'])}::text)),
      '{{password}}', to_jsonb({c.lit(store['secret'])}::text)))
  from jsonb_array_elements(value) elem), updated_at = now()
where key = 'smtp';
update settings set value = 'true'::jsonb, updated_at = now() where key = 'bounce.webhooks_enabled';
"""
    c.psql(sql)
    c.log("ListMonk SMTP entry now uses the stored credential; bounce webhook on")


def ensure_api_user():
    store = c.load(c.API_STORE)
    if store.get("token"):
        token = store["token"]
    else:
        token = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(token.encode()).hexdigest()  # ListMonk stores SHA-256 of API tokens
    perms = "{" + API_PERMS + "}"
    sql = f"""
insert into roles (type, name, permissions) select 'user', 'mailstack', {c.lit(perms)}::text[]
  where not exists (select 1 from roles where name = 'mailstack');
update roles set permissions = {c.lit(perms)}::text[] where name = 'mailstack';
insert into users (username, password_login, password, email, name, type, user_role_id, status)
  select 'mailstack', false, {c.lit(hashed)}, 'mailstack@localhost', 'mailstack (bridge + self-test)',
         'api', (select id from roles where name = 'mailstack'), 'enabled'
  where not exists (select 1 from users where username = 'mailstack');
update users set password = {c.lit(hashed)}, status = 'enabled' where username = 'mailstack';
"""
    c.psql(sql)
    store.update({"user": "mailstack", "token": token})
    c.save(c.API_STORE, store)
    c.log("ListMonk API user mailstack ready")


def main():
    rotate = "--rotate" in sys.argv
    admin = Admin()
    store = ensure_smtp_credential(admin, rotate=rotate)
    set_listmonk_smtp(store)
    ensure_api_user()
    c.log("done; restart the ListMonk container so it re-reads its settings")


if __name__ == "__main__":
    main()
