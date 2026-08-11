"""
Optional-dependency availability flags.

Probed once at import time. Each missing package logs a WARNING naming
the pip package and the feature it disables.  The ``status()`` function
returns a dict suitable for the /health endpoint.
"""

import logging

logger = logging.getLogger("capabilities")

# -- FAISS (RAG retrieval) --
HAS_FAISS = False
try:
    import faiss as _faiss  # noqa: F401
    HAS_FAISS = True
except ImportError:
    logger.warning(
        "faiss-cpu not installed -- RAG retrieval (core/retriever.py) is DISABLED. "
        "Install with: pip install faiss-cpu"
    )

# -- scikit-learn (RAG embeddings) --
HAS_SKLEARN = False
try:
    from sklearn.feature_extraction.text import TfidfVectorizer as _Tv  # noqa: F401
    from sklearn.decomposition import TruncatedSVD as _Ts  # noqa: F401
    HAS_SKLEARN = True
except ImportError:
    logger.warning(
        "scikit-learn not installed -- RAG embeddings are DISABLED. "
        "Install with: pip install scikit-learn"
    )

# -- reportlab (PDF reports) --
HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A4 as _a4  # noqa: F401
    HAS_REPORTLAB = True
except ImportError:
    logger.warning(
        "reportlab not installed -- PDF report generation (core/report_builder.py) is DISABLED. "
        "Install with: pip install reportlab"
    )

# -- sympy (symbolic math verification) --
HAS_SYMPY = False
try:
    import sympy as _sympy  # noqa: F401
    HAS_SYMPY = True
except ImportError:
    logger.warning(
        "sympy not installed -- symbolic math verification (answer_verifier, answer_evaluator) "
        "is DISABLED. Install with: pip install sympy"
    )


# Composite: RAG needs both faiss AND sklearn
HAS_RAG = HAS_FAISS and HAS_SKLEARN


def _kt_model_info() -> dict:
    """Read DKT checkpoint metadata (trained_at, age in days)."""
    import os
    kt_info = {"dkt_available": False, "trained_at": None, "age_days": None, "stale": True}
    dkt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "checkpoints", "dkt_model.pt",
    )
    if not os.path.exists(dkt_path):
        return kt_info

    try:
        import torch
        from datetime import datetime, timezone
        # SEC (BUG-1/SEC-1): weights_only=True blocks arbitrary code execution
        # from a tampered checkpoint (Torch restricted unpickler). Checkpoint
        # holds only tensors + plain dict/str/int metadata, all load-safe.
        ckpt = torch.load(dkt_path, map_location="cpu", weights_only=True)
        kt_info["dkt_available"] = True
        trained_at = ckpt.get("trained_at")
        if trained_at:
            kt_info["trained_at"] = trained_at
            dt = datetime.fromisoformat(trained_at)
            age = (datetime.now(timezone.utc) - dt).days
            kt_info["age_days"] = age
            kt_info["stale"] = age > 14  # stale after 2 weeks
    except Exception as e:
        logger.warning("Could not read DKT checkpoint metadata: %s", e)

    return kt_info


def status() -> dict:
    """Return a capabilities map for the /health endpoint."""
    kt = _kt_model_info()
    return {
        "rag": HAS_RAG,
        "pdf": HAS_REPORTLAB,
        "sympy": HAS_SYMPY,
        "kt_model_age_days": kt["age_days"],
        "kt_model_stale": kt["stale"],
        "kt_model_trained_at": kt["trained_at"],
    }
