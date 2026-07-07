"""
Converts uploaded agenda documents to PDF.

- If the upload is already a PDF, it is used as-is.
- If it's a Word document (.doc or .docx), LibreOffice (headless) converts it to PDF.

LibreOffice is used because it produces reliable, high-fidelity PDF output from
Word files on a Linux server without needing Microsoft Word installed.
"""
import os
import subprocess
import tempfile
import uuid

from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}


class ConversionError(Exception):
    pass


def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def convert_to_pdf(input_path: str, work_dir: str) -> str:
    """
    Given a path to an uploaded file (pdf/doc/docx), return the path to a PDF
    version of it inside work_dir. Raises ConversionError on failure.
    """
    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".pdf":
        return input_path

    if ext not in (".doc", ".docx"):
        raise ConversionError(f"Unsupported file type: {ext}")

    # LibreOffice keeps a single shared "user profile" (config, locks, etc.)
    # per UserInstallation directory. Under real traffic this app can run
    # more than one conversion at the same time (multiple gunicorn workers,
    # or two people submitting at once), and if those concurrent `soffice`
    # processes all point at the same default profile, they collide over its
    # lock file -- the well-known symptom is that the conversion "succeeds"
    # (exit code 0, a PDF file gets written) but the output is blank because
    # the document never actually got loaded/rendered. Giving every
    # conversion its own throwaway profile directory (inside this request's
    # already-unique work_dir) avoids that collision entirely.
    profile_dir = os.path.join(work_dir, "loffice_profile")
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        "soffice",
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to",
        "pdf",
        "--outdir",
        work_dir,
        input_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as e:
        raise ConversionError("Document conversion timed out.") from e
    except OSError as e:
        # Covers FileNotFoundError (soffice not installed/not on PATH) and
        # other launch failures, so a broken environment produces a clear
        # ConversionError instead of an unhandled exception.
        raise ConversionError(f"Could not launch LibreOffice converter: {e}") from e

    if result.returncode != 0:
        raise ConversionError(
            f"LibreOffice conversion failed: {result.stderr or result.stdout}"
        )

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(work_dir, f"{base_name}.pdf")

    if not os.path.exists(output_path):
        raise ConversionError("Conversion completed but no output PDF was found.")

    _verify_not_blank(output_path)

    return output_path


def _verify_not_blank(pdf_path: str) -> None:
    """
    LibreOffice can exit 0 and still write an empty-looking PDF if the
    conversion silently failed (e.g. the profile-lock collision described
    above, or a corrupt input file). Catch that here instead of silently
    emailing a blank document to the Clerk's office.
    """
    try:
        reader = PdfReader(pdf_path)
        if len(reader.pages) == 0:
            raise ConversionError("Conversion produced a PDF with no pages.")
        text = "".join(page.extract_text() or "" for page in reader.pages).strip()
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"Could not verify the converted PDF: {e}") from e

    if not text:
        raise ConversionError(
            "The converted PDF appears to be blank. This can happen if the "
            "server was converting another document at the same moment -- "
            "please try submitting again."
        )


def make_temp_workdir() -> str:
    base = tempfile.gettempdir()
    path = os.path.join(base, f"agenda-intake-{uuid.uuid4().hex}")
    os.makedirs(path, exist_ok=True)
    return path
