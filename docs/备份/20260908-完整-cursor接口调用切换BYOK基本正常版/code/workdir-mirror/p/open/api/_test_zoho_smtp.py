# -*- coding: utf-8 -*-
import smtplib, ssl
from email.message import EmailMessage

HOST = "smtppro.zoho.com"
PORT = 465
USER = "support@ai24x.com"
PWD = "DeVp4y50LTwG"

ctx = ssl.create_default_context()
try:
    with smtplib.SMTP_SSL(HOST, PORT, timeout=25, context=ctx) as s:
        s.login(USER, PWD)
        print("ZOHO LOGIN OK")
        m = EmailMessage()
        m["Subject"] = "AI24X SMTP self-test"
        m["From"] = USER
        m["To"] = USER
        m.set_content("self-test")
        try:
            s.send_message(m)
            print("ZOHO SEND OK")
        except Exception as e:
            print("ZOHO SEND FAIL:", type(e).__name__, e)
except Exception as e:
    print("ZOHO LOGIN FAIL:", type(e).__name__, e)
