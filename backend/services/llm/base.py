"""Shared types, constants, and utilities for all LLM backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Iterator
from typing import Protocol
from typing import Sequence
from typing import runtime_checkable

from core.paths import MODELS_DIR
from schemas.config import LLMBackend
from schemas.config import LLMConfig
from schemas.response import QuerySourceItem

DEFAULT_MODELS_DIR: Path = MODELS_DIR


# ── Stream primitive ────────────────────────────────────────────────────────

@dataclass
class StreamChunk:
    delta: str
    finish_reason: str | None


# ── Protocol ────────────────────────────────────────────────────────────────

@runtime_checkable
class LLMClientProtocol(Protocol):
    """Structural interface that every LLM backend must satisfy."""

    @property
    def is_loaded(self) -> bool: ...

    def __enter__(self) -> "LLMClientProtocol": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool: ...

    def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]: ...

    def create_chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> Iterator[StreamChunk]: ...


# ── Factory ─────────────────────────────────────────────────────────────────

def create_llm_factory(llm_cfg: LLMConfig) -> LLMClientProtocol:
    # Lazy imports avoid circular dependency: llama_factory / openai_compat_factory
    # both import from this module, so top-level imports would create a cycle.
    if llm_cfg.backend == LLMBackend.openai_compat:
        from services.llm.openai_compat_factory import OpenAICompatFactory

        oa = llm_cfg.openai_compat
        return OpenAICompatFactory(
            base_url=oa.base_url,
            api_key=oa.api_key,
            model=oa.model,
            temperature=llm_cfg.temperature,
        )

    from services.llm.llama_factory import LlamaFactory

    lc = llm_cfg.llama_cpp
    return LlamaFactory(
        model_dir=DEFAULT_MODELS_DIR,
        repo_id=lc.repo_id,
        filename=lc.filename,
        n_gpu_layers=lc.n_gpu_layers,
        n_ctx=lc.n_ctx,
    )


# ── Query rewrite ───────────────────────────────────────────────────────────

_QUERY_REWRITE_PROMPT = (
    "Rewrite the following question into a concise, keyword-rich search query "
    "optimized for semantic similarity search in an academic paper database. "
    "Focus on technical terms, algorithm names, variable names, and key concepts. "
    "Output ONLY the rewritten query string, no explanation, no punctuation at the end."
)


def rewrite_query(question: str, llm: LLMClientProtocol) -> str:
    messages = [
        {"role": "system", "content": _QUERY_REWRITE_PROMPT},
        {"role": "user", "content": question},
    ]
    response = llm.create_chat_completion(messages, max_tokens=128, temperature=0.0)
    content: str = response["choices"][0]["message"]["content"]
    rewritten = content.strip()
    return rewritten if rewritten else question


# ── Query prompt & message builder ──────────────────────────────────────────

QUERY_SYSTEM_PROMPT = (
    "You are an academic paper assistant. "
    "Answer questions strictly based on provided source passages. "
    "If the sources are insufficient, explicitly say what is missing. "
    "Use the same language as the user's question. "
    "Each source is formatted as: [Source N] Page X | Section: <section title>, followed by the source text. "
    "The section title tells you what topic the source belongs to — use it to understand context. "
    "Think step by step based on both the section titles and the source text, and provide detailed answers. "
    "Math formatting rules: wrap inline mathematical symbols or variables with single dollar signs, e.g. $x$, $\\alpha$; "
    "wrap standalone equations or multi-term formulas with double dollar signs on their own line, e.g. $$E = mc^2$$."
)


def _build_sources_block(sources: Sequence[QuerySourceItem]) -> str:
    blocks: list[str] = []
    for index, source in enumerate(sources, start=1):
        header = f"[Source {index}] Page {source.page_idx + 1}"
        if source.section_title.strip():
            header += f" | Section: {source.section_title.strip()}"
        blocks.append(f"{header}\n{source.text}")
    return "\n\n".join(blocks)


def build_query_messages(
    question: str,
    sources: Sequence[QuerySourceItem],
    history: list[dict[str, str]] | None = None,
    history_turns: int = 3,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": QUERY_SYSTEM_PROMPT}
    ]

    recent_turns = (history or [])[-history_turns:]
    for turn in recent_turns:
        old_question = str(turn.get("question", "") or "").strip()
        old_answer = str(turn.get("answer", "") or "").strip()
        if old_question:
            messages.append({"role": "user", "content": old_question})
        if old_answer:
            messages.append({"role": "assistant", "content": old_answer})

    context_block = _build_sources_block(sources)
    messages.append({"role": "user", "content": f"{context_block}\n\nQuestion: {question}"})
    return messages
