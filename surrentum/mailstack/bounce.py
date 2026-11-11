"""Parse delivery-failure (RFC 3464) and complaint (ARF, RFC 5965) mail into ListMonk bounces.

Pure functions, no network, so they are unit tested.
"""
import email
import re
from email import policy

CAMPAIGN_RE = re.compile(r"^X-Listmonk-Campaign:\s*([0-9a-fA-F-]{36})", re.M | re.I)
ADDR_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def _addr(value):
    m = ADDR_RE.search(value or "")
    return m.group(0).lower() if m else ""


def parse(raw: bytes):
    """Return a list of {email, type, source, campaign_uuid, meta}; empty if not a bounce."""
    msg = email.message_from_bytes(raw, policy=policy.default)
    rtype = (msg.get_content_type() == "multipart/report") and msg.get_param("report-type")
    if not rtype:
        return []
    text = msg.as_string()
    m = CAMPAIGN_RE.search(text)
    campaign = m.group(1).lower() if m else None
    out = []
    if rtype == "delivery-status":
        for part in msg.walk():
            if part.get_content_type() != "message/delivery-status":
                continue
            for block in part.get_payload():  # one block per recipient (first is per-message)
                fields = {k.lower(): str(v) for k, v in block.items()}
                rcpt = _addr(fields.get("final-recipient", ""))
                if not rcpt or fields.get("action", "").lower() != "failed":
                    continue
                status = fields.get("status", "")
                btype = "hard" if status.startswith("5") else "soft"
                out.append({
                    "email": rcpt, "type": btype, "source": "stalwart-dsn",
                    "campaign_uuid": campaign,
                    "meta": {"status": status, "diagnostic": fields.get("diagnostic-code", "")[:300]},
                })
    elif rtype == "feedback-report":
        for part in msg.walk():
            if part.get_content_type() != "message/feedback-report":
                continue
            blocks = part.get_payload()
            fields = {}
            for b in blocks:
                fields.update({k.lower(): str(v) for k, v in b.items()})
            rcpt = _addr(fields.get("original-rcpt-to", ""))
            if not rcpt:
                m2 = re.search(r"^To:\s*(.+)$", text.split("message/rfc822", 1)[-1], re.M)
                rcpt = _addr(m2.group(1)) if m2 else ""
            if rcpt:
                out.append({"email": rcpt, "type": "complaint", "source": "stalwart-arf",
                            "campaign_uuid": campaign,
                            "meta": {"feedback_type": fields.get("feedback-type", "")}})
    return out
