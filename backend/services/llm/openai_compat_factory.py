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
        strip_thinking: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.strip_thinking = strip_thinking
        self.extra_body = extra_body
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
            extra_body=self.extra_body,
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
            stream=True,
            extra_body=self.extra_body,
        )
        raw = self._iter_raw_chunks(stream)
        yield from self._filter_thinking(raw) if self.strip_thinking else raw

    def _iter_raw_chunks(self, stream: Any) -> Iterator[StreamChunk]:
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            yield StreamChunk(delta=choice.delta.content or "", finish_reason=choice.finish_reason)

    def _filter_thinking(self, source: Iterator[StreamChunk]) -> Iterator[StreamChunk]:
        """Strip <think>...</think> blocks from a StreamChunk iterator."""
        OPEN, CLOSE = "<think>", "</think>"
        in_think = False
        buf = ""

        for chunk in source:
            buf += chunk.delta
            output = ""

            while True:
                if in_think:
                    idx = buf.find(CLOSE)
                    if idx != -1:
                        buf = buf[idx + len(CLOSE):]
                        in_think = False
                    else:
                        buf = buf[-(len(CLOSE) - 1):]
                        break
                else:
                    idx = buf.find(OPEN)
                    if idx != -1:
                        output += buf[:idx]
                        buf = buf[idx + len(OPEN):]
                        in_think = True
                    else:
                        keep = len(OPEN) - 1
                        if len(buf) > keep:
                            output += buf[:-keep]
                            buf = buf[-keep:]
                        break

            if output:
                yield StreamChunk(delta=output, finish_reason=None)
            if chunk.finish_reason:
                yield StreamChunk(delta="", finish_reason=chunk.finish_reason)

        if not in_think and buf:
            yield StreamChunk(delta=buf, finish_reason=None)
