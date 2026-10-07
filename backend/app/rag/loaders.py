"""Extract plain text from uploaded files."""
import io

from pypdf import PdfReader

from .progress import Progress, no_progress

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".csv", ".json", ".html"}


def file_extension(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def check_supported(filename: str) -> None:
    ext = file_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")


def extract_text(filename: str, data: bytes, progress: Progress = no_progress) -> str:
    check_supported(filename)
    if file_extension(filename) == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        total = len(reader.pages)
        progress("extract", "running", f"Reading {total} pages", 0.0)
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            pages.append(page.extract_text() or "")
            if i % 5 == 0 or i == total:
                progress("extract", "running", f"Read page {i} of {total}", i / total)
        text = "\n\n".join(pages)
        if not text.strip():
            raise ValueError("No text found in this PDF (it may be a scanned image without a text layer)")
        progress("extract", "done", f"{total} pages · {len(text):,} characters")
        return text

    text = data.decode("utf-8", errors="ignore")
    progress("extract", "done", f"{len(text):,} characters")
    return text
