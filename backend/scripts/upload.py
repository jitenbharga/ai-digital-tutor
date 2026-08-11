"""
Shared file-upload helpers (SEC-4).

Extracted from api/extras.py so both the materials router and the vision
routes (solution-check / step-check) can share the same size-cap read and
path-traversal-safe filename logic without importing from api.extras.
"""

import os

from fastapi import HTTPException


async def read_capped(upload, max_bytes: int) -> bytes:
    """Read an UploadFile in 64 KB chunks, aborting the moment it exceeds
    max_bytes (SEC-4: enforce the size cap before the whole body is buffered)."""
    size = 0
    chunks = []
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                400, f"File too large. Maximum size: {max_bytes // (1024 * 1024)} MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def safe_basename(filename: str) -> str:
    """Strip any directory components from an uploaded filename (SEC-4)."""
    base = os.path.basename((filename or "").replace("\\", "/")).strip()
    return (base or "document.txt")[:200]
