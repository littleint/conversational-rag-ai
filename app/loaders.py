import os
from typing import List
import requests
import html2text
from pypdf import PdfReader
from llama_index.core import Document

def load_web_url(url: str, max_chars: int = 60000) -> List[Document]:
    """Fetch webpage HTML with browser headers, convert to Markdown text, and return as LlamaIndex Documents."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()

    text_maker = html2text.HTML2Text()
    text_maker.ignore_links = True
    text_maker.ignore_images = True
    markdown_text = text_maker.handle(response.text)

    clean_text = markdown_text[:max_chars].strip()
    if not clean_text or len(clean_text) < 50:
        raise ValueError("Could not extract readable text from the provided webpage.")

    return [
        Document(
            text=clean_text,
            metadata={"source_type": "url", "url": url, "char_count": len(clean_text)}
        )
    ]

def load_pdf_file(file_path: str, filename: str = "") -> List[Document]:
    """Extract text from a PDF file page by page and return as LlamaIndex Documents."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("The provided PDF file has 0 pages.")

    documents: List[Document] = []

    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            documents.append(
                Document(
                    text=text,
                    metadata={
                        "source_type": "pdf",
                        "file_name": filename or os.path.basename(file_path),
                        "page_number": page_idx + 1,
                        "total_pages": total_pages
                    }
                )
            )

    if not documents:
        raise ValueError("Could not extract any readable text from this PDF (it might be scanned images).")

    return documents

def load_txt_file(file_path: str, filename: str = "") -> List[Document]:
    """Read a plain text or markdown file and return as LlamaIndex Documents."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Text file not found at: {file_path}")

    # Try utf-8 first, fallback to latin-1
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            content = f.read()

    clean_text = content.strip()
    if not clean_text or len(clean_text) < 10:
        raise ValueError("The text file is empty or contains insufficient text.")

    return [
        Document(
            text=clean_text,
            metadata={
                "source_type": "file",
                "file_name": filename or os.path.basename(file_path),
                "char_count": len(clean_text)
            }
        )
    ]
