"""Content moderation hook.

Production runs every client message and every assistant reply through a
moderation model. Here that is the OpenAI moderation endpoint when a key is
configured; without a key, or if moderation is unreachable, the turn proceeds
and the gap is logged rather than silently pretended away.
"""
from __future__ import annotations

import logging

from ..config import settings

logger = logging.getLogger("createchat.moderation")

NEUTRAL_MESSAGE = ("I can't help with that message. Tell me about your shoot or project "
                   "and I'll pick it up from there.")


class Moderation:
    def __init__(self) -> None:
        self._client = None

    def _client_or_none(self):
        if not settings.model_configured or not settings.moderation_enabled:
            return None
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                kwargs = {"api_key": settings.openai_api_key, "timeout": 15.0}
                if settings.openai_base_url:
                    kwargs["base_url"] = settings.openai_base_url
                self._client = AsyncOpenAI(**kwargs)
            except Exception as exc:  # pragma: no cover - import/config failure
                logger.warning("moderation unavailable: %s", exc)
                return None
        return self._client

    async def check(self, text: str, *, where: str) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        client = self._client_or_none()
        if not text.strip() or client is None:
            return True, "unchecked"
        try:
            response = await client.moderations.create(model=settings.moderation_model, input=text[:8000])
            result = response.results[0]
            if result.flagged:
                categories = [name for name, flag in result.categories.model_dump().items() if flag]
                logger.warning("moderation flagged %s: %s", where, categories)
                return False, ",".join(categories) or "flagged"
            return True, "ok"
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("moderation call failed for %s: %s", where, exc)
            return True, "unavailable"


moderation = Moderation()
