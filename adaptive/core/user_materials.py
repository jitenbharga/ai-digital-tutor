"""
S1: User Materials — text extraction, chunking, keyword retrieval, grounding.

Students upload their own textbook chapters (PDF/TXT/MD). The system:
  1. Extracts text (pypdf for PDF, direct read for TXT/MD)
  2. Chunks into ~900-char heading-aware pieces (cap ~400 chunks)
  3. Provides lightweight IDF-weighted keyword retrieval over chunks
  4. Builds a strict grounding prompt block for Socratic Q&A
"""

import logging
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("user_materials")

MAX_CHUNKS = 400
CHUNK_SIZE = 900
OVERLAP = 100

# SEC-4: bounds on adversarial input so extraction work stays finite.
MAX_PDF_PAGES = 300           # ignore pages beyond this many
MAX_CHARS_PER_PAGE = 100_000  # ignore runaway text on a single page
MAX_TOTAL_CHARS = 2_000_000   # hard cap on extracted characters


# ---------------------------------------------------------------------------
# Magic-byte / content sniffing (SEC-4)
# ---------------------------------------------------------------------------

def _looks_like_text(file_bytes: bytes) -> bool:
    """True if the bytes decode and are *mostly* printable (not binary junk)."""
    sample = file_bytes[:4096]
    if not sample:
        return False
    try:
        decoded = sample.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded = sample.decode("latin-1")
        except UnicodeDecodeError:
            return False
    if not decoded:
        return True
    printable = sum(1 for ch in decoded if ch in "\t\r\n\f" or ch.isprintable())
    return (printable / len(decoded)) >= 0.85


def verify_magic_bytes(file_bytes: bytes, ext: str) -> None:
    """Verify the declared extension against the actual bytes. Raises ValueError.

    Prevents a mislabeled/binary-garbage file (e.g. a binary blob named .txt or
    a non-PDF named .pdf) from reaching the parser and wasting CPU/RAM.
    """
    if ext == "pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError("File does not look like a PDF (missing %PDF- header).")
    elif ext in ("txt", "md", "markdown", "text"):
        if not _looks_like_text(file_bytes):
            raise ValueError("File does not look like readable text (binary content detected).")


def is_supported_image(data: bytes) -> bool:
    """SEC-4/M-6: True only if bytes look like a supported image (JPEG/PNG/WebP/
    HEIC) by magic bytes. Shared by the vision endpoints so a non-image upload
    (or binary garbage) can't reach a vision model. Stricter than a bare RIFF
    check — WebP must actually carry the WEBP fourCC."""
    if not data or len(data) < 12:
        return False
    return (
        data[:3] == b"\xff\xd8\xff"                          # JPEG
        or data[:8] == b"\x89PNG\r\n\x1a\n"                  # PNG
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")   # WebP (not any RIFF)
        or b"ftyp" in data[:32]                              # HEIC/HEIF family
    )


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF. Raises ValueError for scanned/image PDFs.

    Bounded by MAX_PDF_PAGES / MAX_CHARS_PER_PAGE / MAX_TOTAL_CHARS so an
    adversarial PDF (many pages, huge per-page text) can't peg CPU/RAM (SEC-4).
    """
    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("File does not look like a PDF (missing %PDF- header).")
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        total = 0
        for i, page in enumerate(reader.pages):
            if i >= MAX_PDF_PAGES:
                logger.warning("PDF exceeds %d pages — truncating", MAX_PDF_PAGES)
                break
            text = (page.extract_text() or "")[:MAX_CHARS_PER_PAGE]
            pages.append(text)
            total += len(text)
            if total >= MAX_TOTAL_CHARS:
                logger.warning("PDF exceeds %d chars — truncating", MAX_TOTAL_CHARS)
                break
        full = "\n\n".join(pages).strip()[:MAX_TOTAL_CHARS]
        if len(full) < 50:
            raise ValueError(
                "This PDF appears to be scanned or image-based — very little text could "
                "be extracted. Please upload a text-based PDF, or copy-paste the content "
                "as a .txt file."
            )
        return full
    except ImportError:
        raise ValueError("pypdf is required for PDF processing. Install: pip install pypdf")
    except ValueError:
        raise
    except Exception as e:
        # SEC-8: log the real parser error server-side; return a generic,
        # user-actionable message (never echo the raw exception to the client).
        logger.warning("PDF parse failed: %s", e)
        raise ValueError(
            "Could not read this PDF. Please upload a text-based PDF, or paste "
            "the content as a .txt file."
        )


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Route to correct extractor based on file extension.

    Verifies magic bytes against the declared type first (SEC-4), so the
    extension alone can't route binary garbage into a parser.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    verify_magic_bytes(file_bytes, ext)
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    if ext in ("txt", "md", "markdown", "text"):
        try:
            text = file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1").strip()
        return text[:MAX_TOTAL_CHARS]
    raise ValueError(f"Unsupported file type: .{ext}. Supported: PDF, TXT, MD.")


# ---------------------------------------------------------------------------
# Heading-aware chunking
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(
    r"^(?:#{1,4}\s|Chapter\s|Section\s|\d+\.\d*\s)", re.MULTILINE
)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[Dict]:
    """
    Split text into ~chunk_size char chunks, preferring heading boundaries.
    Returns list of {index, text, heading} dicts.
    """
    if not text:
        return []

    # Split on headings first
    parts = _HEADING_RE.split(text)
    heading_matches = _HEADING_RE.findall(text)

    # Reassemble paragraphs with their headings
    paragraphs = []
    current_heading = ""
    for i, part in enumerate(parts):
        if i > 0 and i - 1 < len(heading_matches):
            current_heading = heading_matches[i - 1].strip()
        for para in part.split("\n\n"):
            para = para.strip()
            if para:
                paragraphs.append((current_heading, para))

    # Build chunks respecting size limits
    chunks = []
    current_text = ""
    current_heading_label = ""

    for heading, para in paragraphs:
        if heading:
            current_heading_label = heading

        if len(current_text) + len(para) + 2 > chunk_size and current_text:
            chunks.append({
                "index": len(chunks),
                "text": current_text.strip(),
                "heading": current_heading_label,
            })
            # Overlap: keep tail of previous chunk
            if overlap and len(current_text) > overlap:
                current_text = current_text[-overlap:] + "\n\n" + para
            else:
                current_text = para
        else:
            current_text = (current_text + "\n\n" + para).strip() if current_text else para

    if current_text.strip():
        chunks.append({
            "index": len(chunks),
            "text": current_text.strip(),
            "heading": current_heading_label,
        })

    # Cap at MAX_CHUNKS
    if len(chunks) > MAX_CHUNKS:
        logger.warning("Chunk count %d exceeds cap %d, truncating", len(chunks), MAX_CHUNKS)
        chunks = chunks[:MAX_CHUNKS]

    return chunks


# ---------------------------------------------------------------------------
# Lightweight IDF-weighted keyword retrieval
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could am it its this that these those of in to for "
    "on at by with from as into through during before after above below between "
    "and or but not nor so yet both either neither each every all any few more most "
    "other some such no only same than too very just about also back even still "
    "how what which who whom whose when where why".split()
)


def _tokenize(text: str) -> List[str]:
    """Lowercase alpha-numeric tokens, stopwords removed."""
    return [
        w for w in re.findall(r"[a-z0-9]+", text.lower())
        if w not in _STOP_WORDS and len(w) > 1
    ]


def build_idf(chunks: List[Dict]) -> Dict[str, float]:
    """Compute IDF over chunk collection."""
    n = len(chunks)
    if n == 0:
        return {}
    df = Counter()
    for chunk in chunks:
        words = set(_tokenize(chunk["text"]))
        for w in words:
            df[w] += 1
    return {w: math.log((n + 1) / (count + 1)) + 1 for w, count in df.items()}


def retrieve_chunks(
    query: str,
    chunks: List[Dict],
    idf: Dict[str, float],
    top_k: int = 8,
) -> List[Dict]:
    """IDF-weighted keyword retrieval. Returns top_k most relevant chunks."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return chunks[:top_k]

    scored = []
    for chunk in chunks:
        chunk_tokens = Counter(_tokenize(chunk["text"]))
        score = sum(
            chunk_tokens.get(qt, 0) * idf.get(qt, 1.0)
            for qt in query_tokens
        )
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


# ---------------------------------------------------------------------------
# Grounding prompt builder
# ---------------------------------------------------------------------------

def format_material_grounding(
    chunks: List[Dict],
    material_title: str = "uploaded chapter",
) -> str:
    """
    Build a strict grounding block for LLM prompts.
    Instructs the model to teach ONLY from this material.
    """
    if not chunks:
        return ""

    excerpts = "\n\n".join(
        f"[Chunk {c['index'] + 1}]{(' — ' + c['heading']) if c.get('heading') else ''}:\n{c['text']}"
        for c in chunks
    )

    return f"""<reference_material title="{material_title}">
{excerpts}
</reference_material>

CRITICAL GROUNDING RULES:
- Answer ONLY from the reference material above. Use its exact terminology and notation.
- If the question falls outside the material, say: "This isn't covered in your chapter."
- Do NOT add information from your general knowledge unless explicitly asked.
- Quote or paraphrase specific sections when possible.
- If the material is ambiguous on a point, say so honestly.
"""
