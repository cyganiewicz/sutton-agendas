import logging
import os
import shutil
import uuid

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

load_dotenv()

from converter import convert_to_pdf, is_allowed_file, make_temp_workdir, ConversionError
from stamper import stamp_pdf
from mailer import send_agenda_email, MailError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agenda-intake")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

STAMP_TEXT = os.environ.get(
    "STAMP_TEXT", "Received by Town of Sutton Clerk's Office"
)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", embed=False)


@app.route("/embed", methods=["GET"])
def embed():
    # Same form, but stripped of header/nav chrome so it drops cleanly into an
    # <iframe> on the town website.
    return render_template("index.html", embed=True)


@app.route("/submit", methods=["POST"])
def submit():
    embed = request.form.get("embed") == "1"
    redirect_target = "embed" if embed else "index"

    submitter_name = (request.form.get("submitter_name") or "").strip()
    submitter_email = (request.form.get("submitter_email") or "").strip()
    body_name = (request.form.get("body_name") or "").strip()
    uploaded_file = request.files.get("agenda_file")

    if not submitter_name or not submitter_email or not body_name:
        flash("Please fill in your name, email, and the board/committee name.", "error")
        return redirect(url_for(redirect_target))

    if not uploaded_file or uploaded_file.filename == "":
        flash("Please choose a Word (.doc/.docx) or PDF file to upload.", "error")
        return redirect(url_for(redirect_target))

    if not is_allowed_file(uploaded_file.filename):
        flash("Only .pdf, .doc, and .docx files are accepted.", "error")
        return redirect(url_for(redirect_target))

    work_dir = make_temp_workdir()
    try:
        original_filename = uploaded_file.filename
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(original_filename)}"
        input_path = os.path.join(work_dir, safe_name)
        uploaded_file.save(input_path)

        try:
            converted_pdf_path = convert_to_pdf(input_path, work_dir)
        except ConversionError as e:
            logger.exception("Conversion failed")
            flash(f"Could not convert your document: {e}", "error")
            return redirect(url_for(redirect_target))

        stamped_path = os.path.join(work_dir, "stamped.pdf")
        try:
            received_dt = stamp_pdf(
                converted_pdf_path, stamped_path, stamp_text=STAMP_TEXT
            )
        except Exception as e:
            logger.exception("Stamping failed")
            flash(f"Could not stamp your document: {e}", "error")
            return redirect(url_for(redirect_target))

        received_str = received_dt.strftime("%m/%d/%Y at %I:%M %p %Z").replace(" 0", " ")

        try:
            send_agenda_email(
                pdf_path=stamped_path,
                original_filename=original_filename,
                submitter_name=submitter_name,
                submitter_email=submitter_email,
                body_name=body_name,
                received_str=received_str,
            )
        except MailError as e:
            logger.exception("Email send failed")
            flash(
                "Your document was processed but could not be emailed to the "
                f"Clerk's office. Please contact them directly. ({e})",
                "error",
            )
            return redirect(url_for(redirect_target))

        flash(
            f"Success! Your agenda was received {received_str} and sent to the "
            "Clerk's office for posting.",
            "success",
        )
        return redirect(url_for(redirect_target))

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
