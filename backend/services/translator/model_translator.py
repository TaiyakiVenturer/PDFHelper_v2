"""Generic model-based translation service wrapper based on llama-cpp-python."""

from __future__ import annotations

import gc
import logging
from pathlib import Path
import re
from typing import Any
from typing import Mapping
from typing import Sequence

from services.translator import translator_config as cfg

try:
    from huggingface_hub import hf_hub_download
except ImportError:  # pragma: no cover
    hf_hub_download = None

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None

logger = logging.getLogger(__name__)


def ensure_model_downloaded(model_dir: Path = cfg.DEFAULT_MODEL_DIR) -> Path:
    """Ensure target GGUF model file exists in local models directory."""
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / cfg.HF_FILENAME
    if model_path.exists():
        return model_path

    if hf_hub_download is None:
        raise RuntimeError(
            "huggingface_hub 未安裝，無法自動下載模型。請先安裝 huggingface-hub。"
        )

    logger.info("模型不存在，開始從 HuggingFace 下載: %s", model_path)
    hf_hub_download(
        repo_id=cfg.HF_REPO_ID,
        filename=cfg.HF_FILENAME,
        local_dir=str(model_dir),
    )

    if not model_path.exists():
        raise FileNotFoundError(f"模型下載完成後仍找不到檔案: {model_path}")

    logger.info("模型下載完成: %s", model_path)
    return model_path


class TranslationGenerationError(RuntimeError):
    """Raised when model output stays empty for non-empty source text."""


class TranslationPlaceholderError(RuntimeError):
    """Raised when placeholder integrity checks fail after all recovery attempts."""


class ModelTranslator:
    """Single-paragraph translator backed by a local GGUF model."""

    def __init__(
        self,
        model_dir: Path = cfg.DEFAULT_MODEL_DIR,
        n_gpu_layers: int = -1,
        n_ctx: int = 4096,
        verbose: bool = False,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.verbose = verbose

        self._llm: Any | None = None
        # Model file verification/download is deferred until actual load.
        self.model_path = self.model_dir / cfg.HF_FILENAME

    def __enter__(self) -> "ModelTranslator":
        self._load()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        try:
            self._unload()
        finally:
            pass
        return False

    def _load(self) -> None:
        if self._llm is not None:
            logger.warning("模型已載入，跳過重複載入")
            return

        if Llama is None:
            raise RuntimeError(
                "llama-cpp-python 未安裝，無法載入模型。請先安裝 llama-cpp-python。"
            )

        self.model_path = ensure_model_downloaded(self.model_dir)
        logger.info("正在載入翻譯模型: %s", self.model_path)
        self._llm = Llama(
            model_path=str(self.model_path),
            n_gpu_layers=self.n_gpu_layers,
            n_ctx=self.n_ctx,
            verbose=self.verbose,
        )
        logger.info("翻譯模型載入完成")

    def _unload(self) -> None:
        if self._llm is None:
            return

        del self._llm
        self._llm = None
        gc.collect()
        logger.info("模型已卸載，VRAM 已釋放")

    @staticmethod
    def _extract_text_from_response(response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            return ""

        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                return str(message.get("content", "")).strip()
            return str(first.get("text", "")).strip()
        return ""

    def _generate_translation(
        self,
        user_prompt: str,
        extra_system_rules: str = "",
    ) -> str:
        if self._llm is None:
            raise RuntimeError("ModelTranslator 尚未載入模型，請在 with 區塊內呼叫")

        system_content = (
            f"{cfg.TRANSLATION_SYSTEM_PROMPT}\n\n"
            f"{cfg.TRANSLATION_DECISION_RULES}\n\n"
            f"{cfg.TRANSLATION_FEW_SHOT}"
        )
        if extra_system_rules.strip():
            system_content = f"{system_content}\n\n{extra_system_rules.strip()}"

        if hasattr(self._llm, "create_chat_completion"):
            response = self._llm.create_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
                temperature=0.0,
            )
        else:
            response = self._llm(
                (
                    f"[System]\n{system_content}\n\n"
                    f"[User]\n{user_prompt}"
                ),
                max_tokens=512,
                temperature=0.0,
                stop=[],
            )

        return self._extract_text_from_response(response)

    def _generate_translation_with_retry(
        self,
        user_prompt: str,
        src_lang: str,
        tgt_lang: str,
        source_text: str,
        extra_system_rules: str = "",
    ) -> str:
        for attempt in range(1, cfg.MAX_EMPTY_OUTPUT_ATTEMPTS + 1):
            result = self._generate_translation(
                user_prompt,
                extra_system_rules=extra_system_rules,
            ).strip()
            if result:
                return result

            logger.warning(
                "翻譯輸出為空，重試中 (%s/%s, src=%s, tgt=%s)",
                attempt,
                cfg.MAX_EMPTY_OUTPUT_ATTEMPTS,
                src_lang,
                tgt_lang,
            )

        raise TranslationGenerationError(
            "模型在非空輸入下連續產生空翻譯輸出"
            f" (src={src_lang}, tgt={tgt_lang}, text={source_text[:80]!r})"
        )

    @staticmethod
    def _flatten_multiline_text(text: str) -> str:
        parts = [line.strip() for line in text.splitlines() if line.strip()]
        if len(parts) <= 1:
            return text
        return " ".join(parts)

    @staticmethod
    def _mask_math_segments(text: str) -> tuple[str, list[tuple[str, str]]]:
        placeholders: list[tuple[str, str]] = []
        next_index = 1

        def _allocate_placeholder(segment: str) -> str:
            nonlocal next_index
            placeholder = cfg.MATH_PLACEHOLDER_PREFIX.format(index=next_index)
            next_index += 1
            placeholders.append((placeholder, segment))
            return placeholder

        def _replace_math(match: re.Match[str]) -> str:
            return _allocate_placeholder(match.group(0))

        masked = cfg.MATH_SEGMENT_PATTERN.sub(_replace_math, text)
        return masked, placeholders

    @staticmethod
    def _restore_math_segments(
        text: str,
        placeholders: Sequence[tuple[str, str]],
    ) -> str:
        restored = text
        for placeholder, segment in placeholders:
            restored = restored.replace(placeholder, segment)
        return restored

    @staticmethod
    def _extract_placeholder_sequence(text: str) -> list[str]:
        return cfg.PLACEHOLDER_PATTERN.findall(text)

    @classmethod
    def _extract_placeholder_order(cls, text: str) -> list[str]:
        seen: set[str] = set()
        order: list[str] = []
        for token in cls._extract_placeholder_sequence(text):
            if token not in seen:
                seen.add(token)
                order.append(token)
        return order

    @classmethod
    def _validate_placeholder_integrity(
        cls,
        source_text: str,
        translated_text: str,
    ) -> tuple[bool, str]:
        source_sequence = cls._extract_placeholder_sequence(source_text)
        if not source_sequence:
            return True, ""

        translated_sequence = cls._extract_placeholder_sequence(translated_text)
        source_set = set(source_sequence)
        translated_set = set(translated_sequence)
        if source_set != translated_set:
            return False, "set_mismatch"

        source_order = cls._extract_placeholder_order(source_text)
        translated_order = cls._extract_placeholder_order(translated_text)
        if source_order != translated_order:
            return False, "order_mismatch"

        return True, ""

    @staticmethod
    def _iter_masked_segments(masked_text: str) -> list[tuple[bool, str]]:
        """Split masked text into (is_placeholder, segment) tuples."""
        segments: list[tuple[bool, str]] = []
        cursor = 0
        for match in cfg.PLACEHOLDER_PATTERN.finditer(masked_text):
            if match.start() > cursor:
                segments.append((False, masked_text[cursor:match.start()]))
            segments.append((True, match.group(0)))
            cursor = match.end()

        if cursor < len(masked_text):
            segments.append((False, masked_text[cursor:]))

        return segments

    @staticmethod
    def _build_translation_user_prompt(
        src_display: str,
        tgt_display: str,
        context_block: str,
        source_text: str,
    ) -> str:
        return (
            f"Translate the following text from {src_display} to {tgt_display}.\n"
            f"{context_block}"
            "Return only the translated text in the target language.\n"
            "Translate all natural language words. Keep only URLs, emails, code tokens, and file/API paths unchanged.\n"
            "<SOURCE_TEXT>\n"
            f"{source_text}\n"
            "</SOURCE_TEXT>"
        )

    def _translate_with_segment_fallback(
        self,
        masked_text: str,
        src_lang: str,
        tgt_lang: str,
        src_display: str,
        tgt_display: str,
        context_block: str,
    ) -> str:
        translated_parts: list[str] = []

        for is_placeholder, segment in self._iter_masked_segments(masked_text):
            if is_placeholder or segment == "":
                translated_parts.append(segment)
                continue

            leading_ws_len = len(segment) - len(segment.lstrip())
            trailing_ws_len = len(segment) - len(segment.rstrip())
            leading_ws = segment[:leading_ws_len]
            trailing_ws = segment[len(segment) - trailing_ws_len :] if trailing_ws_len else ""

            core_start = leading_ws_len
            core_end = len(segment) - trailing_ws_len if trailing_ws_len else len(segment)
            core_text = segment[core_start:core_end]

            if core_text == "":
                translated_parts.append(segment)
                continue

            segment_prompt = self._build_translation_user_prompt(
                src_display,
                tgt_display,
                context_block,
                core_text,
            )
            translated_core = self._generate_translation_with_retry(
                segment_prompt,
                src_lang,
                tgt_lang,
                core_text,
            )

            translated_parts.append(f"{leading_ws}{translated_core}{trailing_ws}")

        return "".join(translated_parts)

    @staticmethod
    def _normalize_history_pairs(
        history: Sequence[Mapping[str, str]] | None,
    ) -> list[tuple[str, str]]:
        if not history:
            return []

        pairs: list[tuple[str, str]] = []
        pending_user: str | None = None

        for item in history:
            source_text = str(
                item.get("source_text")
                or item.get("source")
                or item.get("text")
                or ""
            ).strip()
            translated_text = str(
                item.get("translated_text")
                or item.get("target_text")
                or item.get("translation")
                or ""
            ).strip()

            if source_text and translated_text:
                pairs.append((source_text, translated_text))
                continue

            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if role == "user" and content:
                pending_user = content
                continue
            if role in ("assistant", "model") and content and pending_user:
                pairs.append((pending_user, content))
                pending_user = None

        return pairs[-5:]

    @classmethod
    def _build_context_block(
        cls,
        history: Sequence[Mapping[str, str]] | None,
    ) -> str:
        context_pairs = cls._normalize_history_pairs(history)
        if not context_pairs:
            return ""

        context_lines = [
            "Previous translation context (most recent last, for terminology consistency only):"
        ]
        for index, (src_text, tgt_text) in enumerate(context_pairs, start=1):
            src_preview = src_text.strip().replace("\n", " ")[: cfg.CONTEXT_PREVIEW_CHARS]
            tgt_preview = tgt_text.strip().replace("\n", " ")[: cfg.CONTEXT_PREVIEW_CHARS]
            context_lines.append(f"[Context {index} Source] {src_preview}")
            context_lines.append(f"[Context {index} Target] {tgt_preview}")
        return "\n".join(context_lines) + "\n\n"

    def translate_paragraph(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        history: Sequence[Mapping[str, str]] | None = None,
    ) -> str:
        if self._llm is None:
            raise RuntimeError("ModelTranslator 尚未載入模型，請在 with 區塊內呼叫")

        if src_lang not in cfg.LANG_MAP or tgt_lang not in cfg.LANG_MAP:
            raise ValueError(f"不支援的語言代碼: {src_lang} / {tgt_lang}")

        if text.strip() == "":
            return ""

        src_display, _src_iso = cfg.LANG_MAP[src_lang]
        tgt_display, _tgt_iso = cfg.LANG_MAP[tgt_lang]
        context_block = self._build_context_block(history)
        source_text_masked_raw, math_placeholders = self._mask_math_segments(text)
        source_text_masked = self._flatten_multiline_text(source_text_masked_raw)
        user_prompt = self._build_translation_user_prompt(
            src_display,
            tgt_display,
            context_block,
            source_text_masked,
        )
        result_masked = self._generate_translation_with_retry(
            user_prompt,
            src_lang,
            tgt_lang,
            source_text_masked,
        )

        integrity_ok, integrity_reason = self._validate_placeholder_integrity(
            source_text_masked,
            result_masked,
        )
        if not integrity_ok:
            logger.warning(
                "翻譯結果占位符驗證失敗，啟用強化規則重試 (reason=%s, src=%s, tgt=%s)",
                integrity_reason,
                src_lang,
                tgt_lang,
            )
            result_masked = self._generate_translation_with_retry(
                user_prompt,
                src_lang,
                tgt_lang,
                source_text_masked,
                extra_system_rules=cfg.PLACEHOLDER_REPAIR_SYSTEM_RULES,
            )

            integrity_ok, integrity_reason = self._validate_placeholder_integrity(
                source_text_masked,
                result_masked,
            )
            if not integrity_ok:
                logger.warning(
                    "強化規則重試後仍失敗，啟用分段翻譯回退 (reason=%s, src=%s, tgt=%s)",
                    integrity_reason,
                    src_lang,
                    tgt_lang,
                )
                result_masked = self._translate_with_segment_fallback(
                    source_text_masked_raw,
                    src_lang,
                    tgt_lang,
                    src_display,
                    tgt_display,
                    context_block,
                )
                integrity_ok, integrity_reason = self._validate_placeholder_integrity(
                    source_text_masked_raw,
                    result_masked,
                )
                if not integrity_ok:
                    raise TranslationPlaceholderError(
                        "翻譯輸出中的公式占位符驗證失敗"
                        "，且分段翻譯回退後仍無法保證安全還原"
                        f" (reason={integrity_reason}, src={src_lang}, tgt={tgt_lang})"
                    )

        result = self._restore_math_segments(result_masked, math_placeholders)

        return result
