"""
Retrieval-Augmented Generation (RAG) content retriever.

Indexes curated markdown content from /content directory into a FAISS
vector index. Retrieves top-k relevant chunks for grounding LLM
responses in vetted material.

Embedding strategy: TF-IDF → Truncated SVD for dense vectors (no API
keys required). Can be upgraded to sentence-transformers or API-based
embeddings by swapping the embed() method.
"""

import os
import re
import logging
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("retriever")

from adaptive.core.capabilities import HAS_RAG

# Lazy imports — only loaded if HAS_RAG is True
_faiss = None
_TfidfVectorizer = None
_TruncatedSVD = None


def _ensure_imports():
    """Lazy-import heavy deps. Raises ImportError if unavailable."""
    global _faiss, _TfidfVectorizer, _TruncatedSVD
    if not HAS_RAG:
        raise ImportError("RAG disabled: faiss-cpu and/or scikit-learn not installed")
    if _faiss is None:
        import faiss
        _faiss = faiss
    if _TfidfVectorizer is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        _TfidfVectorizer = TfidfVectorizer
        _TruncatedSVD = TruncatedSVD


# ----------------------------------
# CONTENT PARSING
# ----------------------------------

def _parse_markdown_sections(filepath: str) -> List[Dict]:
    """
    Parse a markdown file into sections split by ## headings.
    Returns list of {topic, section, content, source_file}.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    filename = os.path.basename(filepath).replace(".md", "")
    # Extract top-level topic from # heading
    topic_match = re.match(r"^#\s+(.+)", text)
    topic = topic_match.group(1).strip() if topic_match else filename.replace("_", " ").title()

    sections = []
    # Split by ## headings
    parts = re.split(r"\n(?=## )", text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract section heading
        heading_match = re.match(r"##\s+(.+)", part)
        if heading_match:
            section_name = heading_match.group(1).strip()
            content = part[heading_match.end():].strip()
        else:
            section_name = "Overview"
            # Remove the # heading line
            content = re.sub(r"^#\s+.+\n*", "", part).strip()

        if len(content) < 20:
            continue

        sections.append({
            "topic": topic,
            "section": section_name,
            "content": content,
            "source_file": filepath,
        })

    return sections


def _load_content_dir(content_dir: str) -> List[Dict]:
    """Load all markdown files from the content directory."""
    chunks = []
    if not os.path.isdir(content_dir):
        logger.warning("Content directory not found: %s", content_dir)
        return chunks

    for fname in sorted(os.listdir(content_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(content_dir, fname)
        try:
            sections = _parse_markdown_sections(fpath)
            chunks.extend(sections)
            logger.info("Loaded %d sections from %s", len(sections), fname)
        except Exception as e:
            logger.error("Failed to parse %s: %s", fname, e)

    return chunks


# ----------------------------------
# VECTOR INDEX
# ----------------------------------

# Embedding dimension for dense vectors (TF-IDF → SVD)
EMBED_DIM = 128


class ContentIndex:
    """FAISS-backed vector index over content chunks."""

    def __init__(self, content_dir: str = None):
        _ensure_imports()

        if content_dir is None:
            content_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "content",
            )

        self.content_dir = content_dir
        self.chunks: List[Dict] = []
        self.index = None
        self.vectorizer = None
        self.svd = None
        self._built = False
        self._lock = threading.Lock()

    def build(self):
        """Load content and build the FAISS index."""
        with self._lock:
            if self._built:
                return

            self.chunks = _load_content_dir(self.content_dir)

            if not self.chunks:
                logger.warning("No content chunks found. RAG will be unavailable.")
                self._built = True
                return

            # Build TF-IDF matrix
            texts = [
                f"{c['topic']} {c['section']} {c['content']}"
                for c in self.chunks
            ]

            self.vectorizer = _TfidfVectorizer(
                max_features=5000,
                stop_words="english",
                ngram_range=(1, 2),
            )
            tfidf_matrix = self.vectorizer.fit_transform(texts)

            # Reduce to dense via SVD
            dim = min(EMBED_DIM, tfidf_matrix.shape[1], len(self.chunks))
            self.svd = _TruncatedSVD(n_components=dim, random_state=42)
            dense_matrix = self.svd.fit_transform(tfidf_matrix).astype(np.float32)

            # Normalize for cosine similarity
            norms = np.linalg.norm(dense_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            dense_matrix = dense_matrix / norms

            # Build FAISS index (inner product on normalized = cosine sim)
            self.index = _faiss.IndexFlatIP(dim)
            self.index.add(dense_matrix)

            self._built = True
            logger.info(
                "Content index built: %d chunks, %d dims",
                len(self.chunks), dim,
            )

    def _embed_query(self, query: str) -> np.ndarray:
        """Embed a query string into the same vector space as the index."""
        tfidf = self.vectorizer.transform([query])
        dense = self.svd.transform(tfidf).astype(np.float32)
        norm = np.linalg.norm(dense)
        if norm > 0:
            dense = dense / norm
        return dense

    def search(
        self,
        query: str,
        topic: str = "",
        k: int = 3,
        topic_boost: float = 0.3,
        min_score: float = 0.15,
    ) -> List[Dict]:
        """
        Search for the top-k most relevant content chunks.

        Args:
            query: search query (e.g., "quadratic formula")
            topic: optional topic filter/boost
            k: number of results to return
            topic_boost: bonus score for chunks matching the topic
            min_score: drop chunks whose (boosted) cosine score is below this.
                Prevents off-corpus topics (e.g. "History Of Computing", which
                has no matching content) from being grounded on the nearest
                unrelated chunks (which were Calculus/math). 0.0 = no filtering.

        Returns:
            List of {topic, section, content, score, source_file}
        """
        if not self._built:
            self.build()

        if not self.chunks or self.index is None:
            return []

        # Combine topic with query for better matching
        full_query = f"{topic} {query}" if topic else query
        query_vec = self._embed_query(full_query)

        # Search more than k to allow topic filtering
        search_k = min(k * 3, len(self.chunks))
        scores, indices = self.index.search(query_vec, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = self.chunks[idx]
            # Boost score for matching topic
            final_score = float(score)
            if topic and topic.lower() in chunk["topic"].lower():
                final_score += topic_boost

            # Relevance gate: skip chunks that aren't actually about the topic.
            if final_score < min_score:
                continue

            results.append({
                "topic": chunk["topic"],
                "section": chunk["section"],
                "content": chunk["content"],
                "score": round(final_score, 4),
                "source_file": os.path.basename(chunk["source_file"]),
            })

        # Re-sort by boosted score and take top k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]


# ----------------------------------
# SINGLETON
# ----------------------------------

_index_instance: Optional[ContentIndex] = None
_index_lock = threading.Lock()


def get_index() -> ContentIndex:
    """Return shared ContentIndex singleton (lazy-built)."""
    global _index_instance
    if _index_instance is not None:
        return _index_instance
    with _index_lock:
        if _index_instance is not None:
            return _index_instance
        _index_instance = ContentIndex()
    return _index_instance


def retrieve(
    topic: str,
    query: str = "",
    k: int = 3,
    min_score: float = 0.15,
) -> List[Dict]:
    """
    Public API: retrieve top-k grounding chunks for a topic/query.

    Args:
        topic: the current teaching topic
        query: optional more specific query
        k: number of chunks to return
        min_score: relevance floor — pass a positive value (e.g. 0.15) to avoid
            grounding on unrelated chunks when the topic isn't in the corpus.

    Returns:
        list of {topic, section, content, score, source_file}
    """
    idx = get_index()
    return idx.search(query=query or topic, topic=topic, k=k, min_score=min_score)


def format_grounding_context(chunks: List[Dict]) -> str:
    """
    Format retrieved chunks into a string suitable for prompt injection.

    Returns empty string if no chunks found.
    """
    if not chunks:
        return ""

    parts = ["GROUNDING CONTEXT (from verified reference material):"]
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"\n--- Source {i}: {c['topic']} > {c['section']} ---\n"
            f"{c['content']}"
        )
    parts.append(
        "\nIMPORTANT: Base your explanation on the reference material above. "
        "Do NOT invent facts, formulas, or definitions not supported by this content. "
        "If the topic is not covered above, say so clearly."
    )
    return "\n".join(parts)
