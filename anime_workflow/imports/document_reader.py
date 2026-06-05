from __future__ import annotations

import re
from pathlib import Path


PDF_TEXT_ERROR = "PDF text could not be extracted; scanned PDFs need OCR and are not supported yet"


def extract_document_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        text = decode_text(content)
    elif suffix == ".pdf":
        text = extract_pdf_text(content)
    else:
        raise ValueError("unsupported document type")
    if not text.strip():
        raise ValueError("document text is empty")
    return text.strip()


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def extract_pdf_text(content: bytes) -> str:
    raw = content.decode("latin-1", errors="ignore")
    strings = re.findall(r"\((.*?)\)\s*Tj", raw, flags=re.S)
    array_blocks = re.findall(r"\[(.*?)\]\s*TJ", raw, flags=re.S)
    for block in array_blocks:
        strings.extend(re.findall(r"\((.*?)\)", block, flags=re.S))
    text = "\n".join(unescape_pdf_literal(item) for item in strings)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ValueError(PDF_TEXT_ERROR)
    return text


def unescape_pdf_literal(value: str) -> str:
    value = value.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    value = value.replace(r"\n", "\n").replace(r"\r", "\n").replace(r"\t", "\t")
    return value
