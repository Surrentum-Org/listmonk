import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mailstack"))
from bounce import parse  # noqa: E402

UUID = "11111111-2222-3333-4444-555555555555"

DSN = f"""From: MAILER-DAEMON@mail.keffals.gg
To: newsletter@keffals.gg
Subject: Delivery Status Notification (Failure)
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b1"

--b1
Content-Type: text/plain

Could not deliver.
--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; mail.keffals.gg

Final-Recipient: rfc822; gone@example.org
Action: failed
Status: 5.1.1
Diagnostic-Code: smtp; 550 no such user

--b1
Content-Type: message/rfc822

X-Listmonk-Campaign: {UUID}
To: gone@example.org
Subject: hi

body
--b1--
"""

SOFT = DSN.replace("5.1.1", "4.2.2").replace("gone@", "full@")

ARF = f"""From: abuse@example.net
To: newsletter@keffals.gg
Subject: complaint
MIME-Version: 1.0
Content-Type: multipart/report; report-type=feedback-report; boundary="b2"

--b2
Content-Type: text/plain

Spam report.
--b2
Content-Type: message/feedback-report

Feedback-Type: abuse
User-Agent: test/1.0
Original-Rcpt-To: <angry@example.net>

--b2
Content-Type: message/rfc822

X-Listmonk-Campaign: {UUID}
To: angry@example.net

x
--b2--
"""


class BounceParse(unittest.TestCase):
    def test_hard(self):
        r = parse(DSN.encode())
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["email"], "gone@example.org")
        self.assertEqual(r[0]["type"], "hard")
        self.assertEqual(r[0]["campaign_uuid"], UUID)

    def test_soft(self):
        r = parse(SOFT.encode())
        self.assertEqual(r[0]["type"], "soft")

    def test_complaint(self):
        r = parse(ARF.encode())
        self.assertEqual(r[0]["type"], "complaint")
        self.assertEqual(r[0]["email"], "angry@example.net")

    def test_ordinary_mail_ignored(self):
        self.assertEqual(parse(b"From: a@b.co\nTo: c@d.co\nSubject: hi\n\nhello\n"), [])


if __name__ == "__main__":
    unittest.main()
