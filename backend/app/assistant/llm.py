"""OpenAI chat-completions client with tool calling.

The browser never sees the API key: only this process calls the provider, and
the model name comes from configuration (OPENAI_MODEL).
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..config import settings

logger = logging.getLogger("createchat.llm")


class LLMError(Exception):
    def __init__(self, code: str, message: str, reference: str | None = None, status: int = 503):
        super().__init__(message)
        self.code = code
        self.message = message
        self.reference = reference or f"AI-{uuid.uuid4().hex[:4].upper()}"
        self.status = status


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_message: dict | None = None
    finish_reason: str = "stop"
    model: str = ""
    usage: dict = field(default_factory=dict)


class LLMClient:
    """Thin async wrapper so tests can substitute a scripted model."""

    def __init__(self) -> None:
        self._client: Any = None

    @property
    def configured(self) -> bool:
        return settings.model_configured

    def _ensure_client(self):
        if not settings.model_configured:
            raise LLMError(
                "model_not_configured",
                "The AI model isn't configured yet. Add OPENAI_API_KEY to the project's .env file "
                "and restart the backend; the dashboard, projects and approval cards work without it.",
                reference="AI-CONFIG",
            )
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: dict[str, Any] = {
                "api_key": settings.openai_api_key,
                "timeout": settings.request_timeout_seconds,
                "max_retries": 1,
            }
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _error(self, exc: Exception) -> LLMError:
        code = getattr(exc, "status_code", None)
        logger.warning("model call failed (%s): %s", code, exc)
        return LLMError(
            "model_unavailable",
            "The assistant couldn't reach the model just now. Nothing was changed. "
            "Please try that message again in a moment.",
            status=503 if code in (None, 408, 429, 500, 502, 503, 504) else 502,
        )

    async def stream(self, messages: list[dict], tools: list[dict] | None = None,
                     tool_choice: str = "auto", response_format: dict | None = None,
                     temperature: float = 0.2,
                     max_tokens: int | None = None) -> AsyncIterator[tuple[str, Any]]:
        """Yield ("delta", text) as tokens arrive, then ("reply", LLMReply).

        Tool calls are assembled from their deltas, so a turn that needs a tool
        still streams the natural-language answer produced after the tool runs.
        """
        client = self._ensure_client()
        payload: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or settings.max_output_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        if response_format:
            payload["response_format"] = response_format

        content_parts: list[str] = []
        slots: dict[int, dict[str, str]] = {}
        model_name = settings.openai_model
        finish_reason = "stop"
        try:
            try:
                stream = await client.chat.completions.create(**payload)
            except Exception as first:
                if "response_format" in payload and "response_format" in str(first):
                    payload.pop("response_format", None)
                    stream = await client.chat.completions.create(**payload)
                else:
                    raise
            async for chunk in stream:
                model_name = getattr(chunk, "model", model_name) or model_name
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta and delta.content:
                    content_parts.append(delta.content)
                    yield "delta", delta.content
                for call in (getattr(delta, "tool_calls", None) or []):
                    slot = slots.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                    if call.id:
                        slot["id"] = call.id
                    function = getattr(call, "function", None)
                    if function and function.name:
                        slot["name"] = function.name
                    if function and function.arguments:
                        slot["arguments"] += function.arguments
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        except LLMError:
            raise
        except Exception as exc:  # provider/network failure mid-stream
            raise self._error(exc) from exc

        calls: list[ToolCall] = []
        for index in sorted(slots):
            slot = slots[index]
            raw = slot["arguments"] or "{}"
            try:
                arguments = json.loads(raw)
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be an object")
            except (json.JSONDecodeError, ValueError):
                logger.info("streamed tool call %s had invalid JSON arguments", slot["name"])
                arguments = {"__invalid__": raw[:500]}
            calls.append(ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments=arguments))

        yield "reply", LLMReply(
            content="".join(content_parts).strip(),
            tool_calls=calls,
            assistant_message={
                "role": "assistant",
                "content": "".join(content_parts),
                "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                    for c in calls
                ],
            } if calls else {"role": "assistant", "content": "".join(content_parts)},
            finish_reason=finish_reason,
            model=model_name,
        )

    async def complete(self, messages: list[dict], tools: list[dict] | None = None,
                       tool_choice: str = "auto", response_format: dict | None = None,
                       temperature: float = 0.2, max_tokens: int = 1100) -> LLMReply:
        client = self._ensure_client()
        payload: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        if response_format:
            payload["response_format"] = response_format
        try:
            try:
                response = await client.chat.completions.create(**payload)
            except Exception as first:
                # Some models reject response_format; the envelope parser copes with plain text too.
                if "response_format" in payload and "response_format" in str(first):
                    payload.pop("response_format", None)
                    response = await client.chat.completions.create(**payload)
                else:
                    raise
        except Exception as exc:  # provider/network failure
            raise self._error(exc) from exc

        choice = response.choices[0]
        message = choice.message
        calls: list[ToolCall] = []
        for call in (message.tool_calls or []):
            raw = call.function.arguments or "{}"
            try:
                arguments = json.loads(raw)
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be an object")
            except (json.JSONDecodeError, ValueError):
                logger.info("tool call %s had invalid JSON arguments: %s", call.function.name, raw[:200])
                arguments = {"__invalid__": raw[:500]}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
        usage = {}
        if getattr(response, "usage", None):
            usage = {"prompt_tokens": response.usage.prompt_tokens,
                     "completion_tokens": response.usage.completion_tokens}
        return LLMReply(
            content=(message.content or "").strip(),
            tool_calls=calls,
            assistant_message={
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                    for c in calls
                ],
            } if calls else {"role": "assistant", "content": message.content or ""},
            finish_reason=choice.finish_reason or "stop",
            model=getattr(response, "model", settings.openai_model),
            usage=usage,
        )


llm = LLMClient()


def parse_reply_json(content: str) -> dict:
    """Read the model's JSON envelope, tolerating fences and stray prose."""
    text = (content or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start:end + 1])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def function_schemas(raw_schemas: list[dict]) -> list[dict]:
    return [{"type": "function", "function": schema} for schema in raw_schemas]
