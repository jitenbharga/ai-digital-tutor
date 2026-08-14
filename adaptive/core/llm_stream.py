"""
Async generator that streams tokens from LLM models with fallback.
Used by the SSE /tutor/stream endpoint.
"""

import logging
from typing import AsyncGenerator, List, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


async def stream_llm_text(
    models: List[Tuple[str, BaseChatModel]],
    prompt: str,
    engine_name: str = "unknown",
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from the first available LLM model.
    Yields individual text chunks as they arrive.
    Falls back to next model on error.
    """
    for model_name, model in models:
        try:
            async for chunk in model.astream([HumanMessage(content=prompt)]):
                text = getattr(chunk, 'content', '')
                if text:
                    yield text
            # If we get here, streaming succeeded — done
            return
        except Exception as e:
            logger.warning("stream_llm_text %s failed: %s — trying next model", model_name, e)
            continue

    # All models failed — yield a fallback message
    yield "I'm having trouble generating a response right now. Please try again."
