# Upstream sync plan

Remotes: `origin` = Surrentum-Org/listmonk, `upstream` = knadh/listmonk. Our branch carries one folder, `surrentum/`.

1. Monthly, and on any upstream security release: `git fetch upstream && git checkout -b sync/$(date +%F) master && git merge upstream/master`
   (a merge keeps history honest; there is nothing to conflict with).
2. `python3 -m unittest surrentum/tests/test_bounce.py`.
3. Compare ListMonk's `settings`, `users` and `roles` schema with `surrentum/mailstack/bind.py` (it writes those
   tables directly; API tokens are stored as SHA-256 of the token).
4. Bump the image tag in `/opt/listmonk/docker-compose.yml` on the host, then `mailstack up`, `mailstack health`,
   `mailstack test`, `mailstack verify`.
5. If we ever patch Go code, add a source link in the admin footer in the same PR (AGPL-3.0 section 13).
