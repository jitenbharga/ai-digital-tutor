"""
AI Engine Proxy — Transparent HTTP reverse proxy.
When deployed on Vercel (Auth Service), if ADAPTIVE_ENGINE_URL is set,
any AI/Compute request is proxied transparently to the Render AI Engine.
"""

import os
import logging
import urllib.request
import urllib.error
from fastapi import APIRouter, Request, Response

logger = logging.getLogger("ai_proxy")

ADAPTIVE_ENGINE_URL = os.getenv("ADAPTIVE_ENGINE_URL", "").rstrip("/")

proxy_router = APIRouter()


@proxy_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_ai_request(request: Request, path: str):
    """Forward incoming request to the Render AI Engine."""
    if not ADAPTIVE_ENGINE_URL:
        return Response(
            content='{"detail": "Adaptive Engine URL (ADAPTIVE_ENGINE_URL) is not configured on Vercel."}',
            status_code=503,
            media_type="application/json",
        )

    target_url = f"{ADAPTIVE_ENGINE_URL}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    req = urllib.request.Request(
        target_url,
        data=body if body else None,
        headers=headers,
        method=request.method,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            resp_headers = dict(resp.headers)
            return Response(
                content=content,
                status_code=resp.status,
                headers=resp_headers,
            )
    except urllib.error.HTTPError as err:
        err_content = err.read()
        return Response(
            content=err_content,
            status_code=err.code,
            headers=dict(err.headers),
        )
    except Exception as e:
        logger.error("Proxy request to %s failed: %s", target_url, e)
        return Response(
            content=f'{{"detail": "Adaptive Engine communication error: {str(e)}"}}',
            status_code=502,
            media_type="application/json",
        )