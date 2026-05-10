from __future__ import annotations

import logging
from typing import Any
from typing import Iterator

from services.llm.base import LLMClientProtocol
from services.llm.base import StreamChunk

logger = logging.getLogger(__name__)


class OpenAICompatFactory(LLMClientProtocol):
    """OpenAI-compatible API client (Ollama, OpenAI, Groq, Custom)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Any | None = None

    def __enter__(self) -> "OpenAICompatFactory":
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai 套件未安裝，請執行 pip install openai")
        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        logger.info("[llm] OpenAI-compatible client 初始化完成: %s", self.base_url)
        return self

    def __exit__(self, *args: Any) -> bool:
        self._client = None
        return False

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OpenAICompatFactory 尚未初始化，請在 with 區塊內呼叫")
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort="none",
        )
        return response.model_dump()

    def create_chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> Iterator[StreamChunk]:
        if self._client is None:
            raise RuntimeError("OpenAICompatFactory 尚未初始化，請在 with 區塊內呼叫")
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort="none",
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta_text = choice.delta.content or ""
            finish_reason = choice.finish_reason
            yield StreamChunk(delta=delta_text, finish_reason=finish_reason)
