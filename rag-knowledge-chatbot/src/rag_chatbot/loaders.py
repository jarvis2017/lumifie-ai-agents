"""Document loaders and chunking.

Turns a path or URL into a list of :class:`Chunk` objects with per-chunk
provenance (source name, source type, page number for PDFs, chunk index).

Supported inputs:
  * ``.pdf``  — via ``pypdf`` (page numbers preserved)
  * ``.docx`` — via ``python-docx``
  * ``.md``   — Markdown, read as plain text
  * ``.txt``  — plain text
  * ``http(s)://…`` URLs — fetched with ``httpx`` and stripped to text with
    ``beautifulsoup4``

The HTTP fetch is injectable (``fetch_fn``) so URL ingestion is fully testable
offline with no network. Chunking is character-based with a configurable
``chunk_size`` and ``overlap``; long inputs are never truncated silently — every
character ends up in some chunk.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from lumifie_core import logger

from rag_chatbot.models import Chunk, SourceType

# A fetcher takes a URL and a user-agent and returns raw HTML/text.
FetchFn = Callable[[str, str], str]

_TEXT_EXTS = {".txt"}
_MD_EXTS = {".md", ".markdown"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx"}


def chunk_id(source: str, text: str) -> str:
    """Stable id for de-duplication: md5(source + chunk content)."""
    h = hashlib.md5(f"{source}\x00{text}".encode())
    return h.hexdigest()


def chunk_text(
    text: str,
    *,
    source: str,
    source_type: SourceType,
    chunk_size: int,
    overlap: int,
    page: int | None = None,
    start_index: int = 0,
) -> list[Chunk]:
    """Split ``text`` into overlapping character chunks. Never truncates.

    Returns chunks numbered from ``start_index`` (so a multi-page PDF can keep a
    single monotonically increasing chunk index across pages).
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    cleaned = text.strip()
    if not cleaned:
        return []

    step = chunk_size - overlap
    chunks: list[Chunk] = []
    idx = start_index
    pos = 0
    n = len(cleaned)
    while pos < n:
        end = min(pos + chunk_size, n)
        # Prefer to end on a whitespace boundary so chunks don't split words.
        # Only back off into the last portion of the window (so chunks stay near
        # full size); fall back to a hard cut if no good boundary is found.
        if end < n:
            window = cleaned[pos:end]
            cut = window.rfind(" ")
            if cut > step:  # only trim within the overlap tail, keeps chunks full
                end = pos + cut
        piece = cleaned[pos:end].strip()
        if piece:
            chunks.append(
                Chunk(
                    id=chunk_id(source, piece),
                    text=piece,
                    source=source,
                    source_type=source_type,
                    chunk_index=idx,
                    page=page,
                )
            )
            idx += 1
        if end >= n:
            break  # consumed everything; the overlap tail is already covered
        # Advance by the consumed length minus overlap, always moving forward.
        pos = end - overlap if end - overlap > pos else end
    return chunks


# -- per-format extraction --------------------------------------------------


def _load_txt(path: Path, source_type: SourceType) -> list[tuple[str, int | None]]:
    return [(path.read_text(encoding="utf-8", errors="replace"), None)]


def _load_pdf(path: Path) -> list[tuple[str, int | None]]:
    from pypdf import PdfReader  # noqa: PLC0415

    reader = PdfReader(str(path))
    pages: list[tuple[str, int | None]] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((text, i + 1))  # 1-based page numbers
    return pages


def _load_docx(path: Path) -> list[tuple[str, int | None]]:
    from docx import Document  # noqa: PLC0415

    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs)
    return [(text, None)]


def _default_fetch(url: str, user_agent: str) -> str:
    import httpx  # noqa: PLC0415

    resp = httpx.get(
        url, headers={"User-Agent": user_agent}, follow_redirects=True, timeout=30.0
    )
    resp.raise_for_status()
    return resp.text


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup  # noqa: PLC0415

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n")


# -- public API -------------------------------------------------------------


def is_url(spec: str) -> bool:
    return spec.startswith(("http://", "https://"))


def load_source(
    spec: str,
    *,
    chunk_size: int,
    overlap: int,
    fetch_fn: FetchFn | None = None,
    user_agent: str = "lumifie-rag-chatbot/0.1",
) -> list[Chunk]:
    """Load one path or URL into chunks. Raises on unsupported/missing input."""
    if is_url(spec):
        fetch = fetch_fn or _default_fetch
        html = fetch(spec, user_agent)
        text = _html_to_text(html)
        logger.info("Fetched URL {} ({} chars of text).", spec, len(text))
        return chunk_text(
            text,
            source=spec,
            source_type=SourceType.URL,
            chunk_size=chunk_size,
            overlap=overlap,
        )

    path = Path(spec)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {spec}")

    ext = path.suffix.lower()
    if ext in _PDF_EXTS:
        source_type = SourceType.PDF
        pages = _load_pdf(path)
    elif ext in _DOCX_EXTS:
        source_type = SourceType.DOCX
        pages = _load_docx(path)
    elif ext in _MD_EXTS:
        source_type = SourceType.MARKDOWN
        pages = _load_txt(path, source_type)
    elif ext in _TEXT_EXTS:
        source_type = SourceType.TEXT
        pages = _load_txt(path, source_type)
    else:
        raise ValueError(
            f"Unsupported file type '{ext}' for {spec}. "
            "Supported: .pdf, .docx, .md, .txt, or an http(s) URL."
        )

    source = path.name
    chunks: list[Chunk] = []
    for text, page in pages:
        chunks.extend(
            chunk_text(
                text,
                source=source,
                source_type=source_type,
                chunk_size=chunk_size,
                overlap=overlap,
                page=page,
                start_index=len(chunks),
            )
        )
    logger.info("Loaded {} ({} chunk(s)).", source, len(chunks))
    return chunks


def load_sources(
    specs: list[str],
    *,
    chunk_size: int,
    overlap: int,
    fetch_fn: FetchFn | None = None,
    user_agent: str = "lumifie-rag-chatbot/0.1",
) -> list[Chunk]:
    """Load many paths/URLs into a single flat list of chunks."""
    out: list[Chunk] = []
    for spec in specs:
        out.extend(
            load_source(
                spec,
                chunk_size=chunk_size,
                overlap=overlap,
                fetch_fn=fetch_fn,
                user_agent=user_agent,
            )
        )
    return out


__all__ = [
    "chunk_id",
    "chunk_text",
    "is_url",
    "load_source",
    "load_sources",
]
