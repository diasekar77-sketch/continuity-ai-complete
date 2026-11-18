"""Section-aware chunking: policies are organised by headings, so we keep each section together
(and attach the heading to every chunk) instead of cutting blindly every N characters."""
import re

_HEADING = re.compile(r"^(#{1,4}\s+.+|\d+(\.\d+)*[.)]?\s+[A-Z][^\n]{2,80})$")


def clean(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_policy(text: str, max_chars: int = 900) -> list[dict]:
    sections, title, buf = [], "Introduction", []
    for line in clean(text).split("\n"):
        if _HEADING.match(line.strip()):
            if buf and "".join(buf).strip():
                sections.append((title, "\n".join(buf).strip()))
            title, buf = re.sub(r"^#+\s*", "", line.strip()), []
        else:
            buf.append(line)
    if buf and "".join(buf).strip():
        sections.append((title, "\n".join(buf).strip()))

    chunks = []
    for title, body in sections:
        if len(body) <= max_chars:
            chunks.append({"section": title, "text": body})
            continue
        cur = ""
        for para in re.split(r"\n\s*\n|(?<=[.!?])\s+", body):
            if cur and len(cur) + len(para) > max_chars:
                chunks.append({"section": title, "text": cur.strip()})
                cur = ""
            cur += para + " "
        if cur.strip():
            chunks.append({"section": title, "text": cur.strip()})
    return chunks
