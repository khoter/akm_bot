import smtplib
from email.message import EmailMessage
from config import SMTP_HOST, SMTP_PORT, FROM_EMAIL, EMAIL_PASSWORD, TO_EMAIL

def send_email(subject, body, attachment_path):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = TO_EMAIL
    msg.set_content(body)

    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = attachment_path.split('/')[-1]
        msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(FROM_EMAIL, EMAIL_PASSWORD)
        server.send_message(msg)
