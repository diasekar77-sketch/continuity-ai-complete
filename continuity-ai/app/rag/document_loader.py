from pathlib import Path


def load_text(filename: str, data: bytes) -> str:
    """Extract plain text from an uploaded policy file (.pdf, .md, .txt)."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        import pymupdf
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    if ext in (".md", ".txt"):
        return data.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {ext or 'none'} (use .pdf, .md or .txt)")
