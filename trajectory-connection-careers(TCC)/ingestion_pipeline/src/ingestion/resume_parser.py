import re
import logging

logger = logging.getLogger("ingestion.resume_parser")

# Common section headers to detect structure
SECTION_KEYWORDS = [
    "experience", "education", "skills", "projects", "summary",
    "work history", "certifications", "awards", "publications",
    "objective", "profile", "languages", "interests"
]

def _detect_section_headers(text: str) -> str:
    """
    Adds a blank line before detected section headers to preserve structure.
    """
    lines = text.split("\n")
    output = []
    for line in lines:
        stripped = line.strip().lower()
        if any(stripped.startswith(kw) or stripped == kw for kw in SECTION_KEYWORDS):
            output.append("")  # blank line before section
            output.append(line.strip())
        else:
            output.append(line)
    return "\n".join(output)


def _clean_text(text: str) -> str:
    """
    Strips excessive whitespace and blank lines, preserving intentional structure.
    """
    # Collapse 3+ consecutive blank lines into one
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def parse_resume(file_path: str) -> str:
    """
    Parses a PDF or plain-text resume into structured plain text.

    Args:
        file_path: Absolute or relative path to the resume file (.pdf or .txt)

    Returns:
        Cleaned plain text extracted from the resume, with section structure preserved.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not .pdf or .txt.
    """
    import os

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    ext = os.path.splitext(file_path)[-1].lower()

    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber is required for PDF parsing. Install it with: pip install pdfplumber"
            )
        logger.info(f"Parsing PDF resume: {file_path}")
        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
                else:
                    logger.debug(f"Page {i+1} returned no extractable text, skipping.")
        raw_text = "\n".join(pages_text)

    elif ext == ".txt":
        logger.info(f"Parsing plain-text resume: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

    else:
        raise ValueError(f"Unsupported file type '{ext}'. Only .pdf and .txt are supported.")

    structured_text = _detect_section_headers(raw_text)
    cleaned_text = _clean_text(structured_text)

    logger.info(f"Resume parsed successfully: {len(cleaned_text)} characters extracted.")
    return cleaned_text
