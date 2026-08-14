"""
F3: Resource-link validation utilities.

Rules (from NEEDED_FEATURES_PROMPTS.md N11):
- Never present an unvalidated URL as a curated resource.
- Search-page fallbacks must be labeled type="search", never "video"/"article".
- Re-validate cached links periodically (link rot).

Wire-up: call `validate_resources()` on the candidate list inside
_fetch_resources (serve.py) before caching on the canonical node, and
`revalidate_node_resources()` from a periodic task / on stale cache reads.
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

VALIDATE_TIMEOUT = 6  # seconds per URL
REVALIDATE_AFTER = 7 * 86400  # links older than a week get re-checked


async def url_is_alive(url: str) -> bool:
    """HEAD (fallback GET) the URL; True only on HTTP 200-399."""
    try:
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=VALIDATE_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.head(url, allow_redirects=True) as resp:
                    if resp.status < 400:
                        return True
                    # Some sites reject HEAD — retry with GET
            except Exception:
                pass
            async with session.get(url, allow_redirects=True) as resp:
                return resp.status < 400
    except Exception as e:
        logger.info("link validation failed for %s: %s", url, e)
        return False


async def validate_resources(resources: list) -> list:
    """
    Filter a resource list:
    - type "search" items pass through (they're honest search links, labeled as such)
    - all other items must have a live URL; dead ones are dropped
    Adds validated_at timestamp to survivors.
    """
    if not resources:
        return []

    async def _check(r):
        if r.get("type") == "search":
            r["validated_at"] = time.time()
            return r
        alive = await url_is_alive(r.get("url", ""))
        if alive:
            r["validated_at"] = time.time()
            return r
        logger.info("dropping dead resource link: %s", r.get("url"))
        return None

    checked = await asyncio.gather(*[_check(dict(r)) for r in resources])
    return [r for r in checked if r]


def needs_revalidation(resources: list) -> bool:
    """True if any cached resource is older than REVALIDATE_AFTER."""
    now = time.time()
    return any(
        now - (r.get("validated_at") or 0) > REVALIDATE_AFTER
        for r in (resources or [])
    )
