from __future__ import annotations

import gc
import logging
from pathlib import Path
import time
from typing import Any
from typing import Iterator

from services.llm.base import DEFAULT_MODELS_DIR
from services.llm.base import LLMClientProtocol
from services.llm.base import StreamChunk

logger = logging.getLogger(__name__)


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


class LlamaFactory(LLMClientProtocol):
    def __init__(
        self,
        repo_id: str,
        filename: str,
        model_dir: Path = DEFAULT_MODELS_DIR,
        n_gpu_layers: int = 0,
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
    ) -> Iterator[StreamChunk]:
        if self._llm is None:
            raise RuntimeError("LlamaFactory 尚未載入模型，請在 with 區塊內呼叫")

        raw_stream = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in raw_stream:
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta_text = str((choice.get("delta") or {}).get("content", "") or "")
            finish_reason = choice.get("finish_reason")
            yield StreamChunk(delta=delta_text, finish_reason=finish_reason)
