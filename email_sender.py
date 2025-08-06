import logging
import smtplib
from email.message import EmailMessage
from config import SMTP_HOST, SMTP_PORT, FROM_EMAIL, EMAIL_PASSWORD, TO_EMAIL

def send_email(subject: str, body: str, attachment_path: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = FROM_EMAIL
    msg["To"]      = TO_EMAIL
    msg.set_content(body)

    with open(attachment_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=attachment_path.rsplit("/", 1)[-1],
        )

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(FROM_EMAIL, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as err:
        logging.exception("Ошибка отправки письма: %s", err)
