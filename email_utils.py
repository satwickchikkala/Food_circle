# email_utils.py
import smtplib
from email.message import EmailMessage
import streamlit as st

def send_email(to_email: str, subject: str, body: str):
    try:
        host = st.secrets["smtp_host"]
        port = int(st.secrets["smtp_port"])
        user = st.secrets["smtp_user"]
        password = st.secrets["smtp_password"]
        from_email = st.secrets.get("from_email", user)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(body)

        server = smtplib.SMTP(host, port)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("send_email error:", e)
        return False
