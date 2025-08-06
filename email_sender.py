import smtplib
import logging
from email.message import EmailMessage
from config import SMTP_HOST, SMTP_PORT, SMTP_LOGIN, SMTP_PASSWORD, EMAIL_TO

def send_email(subject: str, body: str, attachment_path: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = SMTP_LOGIN
    msg["To"]      = ", ".join(EMAIL_TO)
    msg.set_content(body)

    with open(attachment_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=attachment_path.rsplit('/', 1)[-1],
        )

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_LOGIN, SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception as err:
        logging.exception("Ошибка отправки письма: %s", err)
