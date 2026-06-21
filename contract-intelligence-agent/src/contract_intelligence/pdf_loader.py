"""PDF ingestion and page-aware chunking.

Extracts text per page with ``pypdf`` and groups pages into chunks that fit
comfortably inside the model's context, preserving page boundaries so the agent
can cite page numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lumifie_core import logger
from pypdf import PdfReader


@dataclass(slots=True)
class Page:
    """One extracted page of the contract."""

    number: int  # 1-indexed
    text: str


@dataclass(slots=True)
class Chunk:
    """A contiguous run of pages small enough to send to the model in one turn."""

    index: int  # 0-indexed chunk position
    start_page: int
    end_page: int
    text: str


@dataclass(slots=True)
class ContractDocument:
    """A loaded contract: its name, pages, and chunked representation."""

    name: str
    pages: list[Page]
    chunks: list[Chunk]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


class PDFLoadError(RuntimeError):
    """Raised when a PDF cannot be read or contains no extractable text."""


def _extract_pages(path: Path) -> list[Page]:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pypdf raises a variety of low-level errors
        raise PDFLoadError(f"Could not open PDF {path!s}: {exc}") from exc

    if reader.is_encrypted:
        # Attempt empty-password decryption; many PDFs are "encrypted" with no password.
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PDFLoadError(
                f"PDF {path!s} is encrypted and could not be decrypted."
            ) from exc

    pages: list[Page] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # corrupt page shouldn't abort the whole doc
            logger.warning("Failed to extract text from page {}: {}", i, exc)
            text = ""
        pages.append(Page(number=i, text=text.strip()))
    return pages


def _chunk_pages(pages: list[Page], max_chars: int) -> list[Chunk]:
    """Group pages into chunks of at most ``max_chars`` characters.

    Page boundaries are never split. A single page larger than ``max_chars`` is
    emitted as its own (oversized) chunk rather than truncated — never drop text.
    """
    chunks: list[Chunk] = []
    buf: list[Page] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        body = "\n\n".join(
            f"[Page {p.number}]\n{p.text}" for p in buf if p.text
        )
        chunks.append(
            Chunk(
                index=len(chunks),
                start_page=buf[0].number,
                end_page=buf[-1].number,
                text=body,
            )
        )
        buf = []
        buf_len = 0

    for page in pages:
        page_len = len(page.text)
        if buf and buf_len + page_len > max_chars:
            flush()
        buf.append(page)
        buf_len += page_len
    flush()
    return chunks


def load_contract(path: str | Path, max_chunk_chars: int = 12_000) -> ContractDocument:
    """Load a PDF contract from disk into a chunked :class:`ContractDocument`.

    Raises :class:`PDFLoadError` if the file is missing, unreadable, or yields no
    extractable text (e.g. a scanned image with no OCR layer).
    """
    path = Path(path)
    if not path.exists():
        raise PDFLoadError(f"File not found: {path!s}")
    if path.suffix.lower() != ".pdf":
        raise PDFLoadError(f"Not a PDF file: {path!s}")

    logger.info("Loading contract: {}", path.name)
    pages = _extract_pages(path)

    if not any(p.text for p in pages):
        raise PDFLoadError(
            f"No extractable text in {path!s}. The PDF may be a scanned image "
            "requiring OCR, which this agent does not perform."
        )

    chunks = _chunk_pages(pages, max_chunk_chars)
    logger.info(
        "Loaded {} page(s) into {} chunk(s)", len(pages), len(chunks)
    )
    return ContractDocument(name=path.name, pages=pages, chunks=chunks)
