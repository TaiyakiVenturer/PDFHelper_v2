from __future__ import annotations

import gc
import logging
from pathlib import Path
import time
from typing import Any
from typing import Iterator
from typing import Sequence

from schemas.response import QuerySourceItem
from services.translator import translator_config as cfg

logger = logging.getLogger(__name__)

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


def ensure_model_ready(
    model_dir: Path,
    repo_id: str,
    filename: str,
) -> Path:
    """Ensure target GGUF model file exists in local models directory."""
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / filename
    if model_path.exists():
        return model_path

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise RuntimeError(
            "huggingface_hub 未安裝，無法自動下載模型。請先安裝 huggingface-hub。"
        )

    logger.info("模型不存在，開始從 HuggingFace 下載: %s", model_path)
    hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(model_dir),
    )

    if not model_path.exists():
        raise FileNotFoundError(f"模型下載完成後仍找不到檔案: {model_path}")

    logger.info("模型下載完成: %s", model_path)
    return model_path


class LlamaFactory:
    def __init__(
        self,
        model_dir: Path = cfg.DEFAULT_MODEL_DIR,
        repo_id: str = cfg.HF_REPO_ID,
        filename: str = cfg.HF_FILENAME,
        n_gpu_layers: int = -1,
        n_ctx: int = 4096,
        verbose: bool = False,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.repo_id = repo_id
        self.filename = filename
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.verbose = verbose

        self._llm: Any | None = None

    def __enter__(self) -> "LlamaFactory":
        if self._llm is not None:
            logger.warning("模型已載入，跳過重複載入")
            return self

        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python 未安裝，無法載入模型。請先安裝 llama-cpp-python。"
            )

        model_path = ensure_model_ready(
            model_dir=self.model_dir,
            repo_id=self.repo_id,
            filename=self.filename,
        )
        logger.info("[llm] 開始載入模型: %s", model_path.name)
        t0 = time.perf_counter()
        self._llm = Llama(
            model_path=str(model_path),
            n_gpu_layers=self.n_gpu_layers,
            n_ctx=self.n_ctx,
            verbose=self.verbose,
        )
        logger.info("[llm] 模型載入完成 (%.2fs)", time.perf_counter() - t0)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if self._llm is not None:
            del self._llm
            self._llm = None

        gc.collect()
        try:
            import torch as _torch
            if _torch.cuda.is_available():
                _torch.cuda.empty_cache()
        except ImportError:  # pragma: no cover
            pass

        logger.info("模型已卸載，VRAM 已釋放")
        return False

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        if self._llm is None:
            raise RuntimeError("LlamaFactory 尚未載入模型，請在 with 區塊內呼叫")

        return self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def create_chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> Iterator[dict[str, Any]]:
        if self._llm is None:
            raise RuntimeError("LlamaFactory 尚未載入模型，請在 with 區塊內呼叫")

        return self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
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
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": QUERY_SYSTEM_PROMPT}
    ]

    history_turns = (history or [])[-3:]
    for turn in history_turns:
        old_question = str(turn.get("question", "") or "").strip()
        old_answer = str(turn.get("answer", "") or "").strip()
        if old_question:
            messages.append({"role": "user", "content": old_question})
        if old_answer:
            messages.append({"role": "assistant", "content": old_answer})

    context_block = _build_sources_block(sources)
    user_content = f"{context_block}\n\nQuestion: {question}"
    messages.append({"role": "user", "content": user_content})
    return messages
