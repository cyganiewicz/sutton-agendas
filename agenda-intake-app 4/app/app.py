import logging
import os
import shutil
import uuid

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

load_dotenv()

from converter import convert_to_pdf, is_allowed_file, make_temp_workdir, ConversionError
from stamper import stamp_pdf
from mailer import send_agenda_email, MailError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agenda-intake")

app = Flask(__name__)
# `or`, not .get()'s default: a FLASK_SECRET_KEY that's set-but-empty in the
# hosting platform is falsy, and Flask treats a falsy secret_key as "no key
# set" -- flash() then raises RuntimeError on every request. `or` catches
# that case the same way it does for STAMP_TEXT below.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev-secret-change-me"

# The form is designed to be embedded in an <iframe> on the town website,
# which is a different domain than wherever this app is hosted. Flask's
# session cookie (which is what makes flash() messages survive the redirect
# after submit) defaults to a SameSite setting that browsers block inside
# cross-origin iframes -- so on the embedded page, the success/error message
# would silently vanish after submit while still working fine standalone.
# SameSite=None (plus Secure, required by browsers whenever SameSite=None is
# used) tells the browser this cookie is intentionally meant to work in that
# cross-site iframe context.
app.config["SESSION_COOKIE_SAMESITE"] = "None"
# Secure is required by browsers whenever SameSite=None is used, and Railway
# always serves over HTTPS, so this should stay True in production. It's
# environment-controlled only so local testing over plain http://localhost
# (no TLS) can still see flash messages by setting SESSION_COOKIE_SECURE=false
# in a local .env -- see .env.example.
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower() != "false"
)

MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Use `or` rather than os.environ.get's default parameter: if STAMP_TEXT is
# set in the hosting platform but left blank (present with an empty value,
# rather than not set at all), .get()'s default would never kick in and the
# stamp would silently render with no label text. `or` treats blank the same
# as unset.
STAMP_TEXT = os.environ.get("STAMP_TEXT") or "Received by Town of Sutton Clerk's Office"


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

    # The form is submitted via JavaScript (fetch), which marks the request
    # with this header. That path returns JSON so the page can show the
    # result directly, without depending on a cookie surviving a redirect --
    # which cross-origin iframes on the town website can't rely on in every
    # browser (see the SESSION_COOKIE_SAMESITE note above). If JavaScript is
    # unavailable for some reason, the plain form still POSTs here without
    # the header, and gets the classic flash-then-redirect behavior instead.
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def respond(success: bool, message: str):
        if wants_json:
            return jsonify({"success": success, "message": message})
        flash(message, "success" if success else "error")
        return redirect(url_for(redirect_target))

    submitter_name = (request.form.get("submitter_name") or "").strip()
    submitter_email = (request.form.get("submitter_email") or "").strip()
    body_name = (request.form.get("body_name") or "").strip()
    uploaded_file = request.files.get("agenda_file")

    if not submitter_name or not submitter_email or not body_name:
        return respond(False, "Please fill in your name, email, and the board/committee name.")

    if not uploaded_file or uploaded_file.filename == "":
        return respond(False, "Please choose a Word (.doc/.docx) or PDF file to upload.")

    if not is_allowed_file(uploaded_file.filename):
        return respond(False, "Only .pdf, .doc, and .docx files are accepted.")

    work_dir = make_temp_workdir()
    submission_id = uuid.uuid4().hex[:8]
    try:
        try:
            original_filename = uploaded_file.filename
            safe_name = f"{uuid.uuid4().hex}_{os.path.basename(original_filename)}"
            input_path = os.path.join(work_dir, safe_name)
            uploaded_file.save(input_path)

            try:
                converted_pdf_path = convert_to_pdf(input_path, work_dir)
            except ConversionError as e:
                logger.exception("[%s] Conversion failed", submission_id)
                return respond(False, f"Could not convert your document: {e}")

            stamped_path = os.path.join(work_dir, "stamped.pdf")
            try:
                received_dt = stamp_pdf(
                    converted_pdf_path, stamped_path, stamp_text=STAMP_TEXT
                )
            except Exception as e:
                logger.exception("[%s] Stamping failed", submission_id)
                return respond(False, f"Could not stamp your document: {e}")

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
                logger.exception("[%s] Email send failed", submission_id)
                return respond(
                    False,
                    "Your document was processed but could not be emailed to the "
                    f"Clerk's office. Please contact them directly. ({e})",
                )

            return respond(
                True,
                f"Success! Your agenda was received {received_str} and sent to the "
                "Clerk's office for posting.",
            )

        except Exception as e:
            # Safety net: any unexpected failure (not one of the specific
            # cases above) should still show the user a normal page instead
            # of a raw 500, and should be easy to find in the logs by its
            # submission id.
            logger.exception("[%s] Unexpected error processing submission", submission_id)
            try:
                return respond(
                    False,
                    "Something went wrong processing your submission (reference "
                    f"{submission_id}). Please try again, or contact the Clerk's "
                    "office directly if it keeps happening.",
                )
            except Exception:
                # If even building the response fails (e.g. misconfigured
                # secret key breaking flash() on the no-JS path), fall back
                # to the simplest possible reply instead of a second crash.
                logger.exception(
                    "[%s] Could not build the error response either", submission_id
                )
                if wants_json:
                    return jsonify(
                        {
                            "success": False,
                            "message": (
                                "Something went wrong processing your submission "
                                f"(reference {submission_id})."
                            ),
                        }
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
