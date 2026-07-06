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

    # LibreOffice writes the output PDF into --outdir using the same base filename.
    cmd = [
        "soffice",
        "--headless",
        "--norestore",
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

    if result.returncode != 0:
        raise ConversionError(
            f"LibreOffice conversion failed: {result.stderr or result.stdout}"
        )

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(work_dir, f"{base_name}.pdf")

    if not os.path.exists(output_path):
        raise ConversionError("Conversion completed but no output PDF was found.")

    return output_path


def make_temp_workdir() -> str:
    base = tempfile.gettempdir()
    path = os.path.join(base, f"agenda-intake-{uuid.uuid4().hex}")
    os.makedirs(path, exist_ok=True)
    return path
