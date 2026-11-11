"""Independent SPF + DKIM + DMARC-alignment check of /w/test-msg.eml (run in a throwaway container).

argv[1] = the sending host's public IP. Uses the public DNS records, not Stalwart's own verdict.
"""
import email
import email.utils
import sys

import dkim
import spf

raw = open("/w/test-msg.eml", "rb").read()
msg = email.message_from_bytes(raw)
frm = email.utils.parseaddr(msg["From"])[1]
dom = frm.split("@")[1]
ok_dkim = []
for i in range(len(msg.get_all("DKIM-Signature", []))):
    sig = msg.get_all("DKIM-Signature")[i]
    d = [p.split("=", 1)[1] for p in sig.replace("\n", " ").split(";") if p.strip().startswith("d=")][0].strip()
    ok = dkim.DKIM(raw).verify(idx=i)
    print(f"dkim[{i}] d={d} {'pass' if ok else 'FAIL'}")
    ok_dkim.append(ok and d.endswith(dom))
res = spf.check2(sys.argv[1], frm, "mail.keffals.gg")[0]
print("spf", res)
dmarc = "pass" if (any(ok_dkim) or res == "pass") else "FAIL"
print("dmarc (aligned dkim or spf):", dmarc)
sys.exit(0 if dmarc == "pass" and any(ok_dkim) and res == "pass" else 1)
