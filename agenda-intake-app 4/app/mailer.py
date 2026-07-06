"""
Sends the final, stamped PDF to the Clerk's office via Resend
(https://resend.com).

Configured entirely through environment variables (see .env.example / README)
so the sending domain/API key can be changed without any code changes.
"""
import os

import resend


class MailError(Exception):
    pass


def send_agenda_email(
    pdf_path: str,
    original_filename: str,
    submitter_name: str,
    submitter_email: str,
    body_name: str,
    received_str: str,
) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    mail_from = os.environ.get("MAIL_FROM")
    mail_to = os.environ.get("AGENDAS_EMAIL", "agendas@town.sutton.ma.us")

    if not api_key or not mail_from:
        raise MailError(
            "Email is not configured. Set RESEND_API_KEY and MAIL_FROM "
            "(see .env.example)."
        )

    resend.api_key = api_key

    out_filename = os.path.splitext(original_filename)[0] + " - stamped.pdf"
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    attachment: resend.Attachment = {
        "filename": out_filename,
        "content": list(file_bytes),
    }

    text_body = (
        "A new meeting agenda was submitted through the town website intake form.\n\n"
        f"Body/Board: {body_name}\n"
        f"Submitted by: {submitter_name} <{submitter_email}>\n"
        f"Received: {received_str}\n"
        f"Original filename: {original_filename}\n\n"
        "The attached PDF has been converted (if needed) and stamped with the "
        "received date/time. It is ready for posting.\n"
    )

    params: resend.Emails.SendParams = {
        "from": mail_from,
        "to": [mail_to],
        "reply_to": submitter_email,
        "subject": f"Agenda submission: {body_name} ({received_str})",
        "text": text_body,
        "attachments": [attachment],
    }

    try:
        resend.Emails.send(params)
    except Exception as e:
        raise MailError(f"Failed to send email via Resend: {e}") from e
