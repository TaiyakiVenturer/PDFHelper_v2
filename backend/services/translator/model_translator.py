"""Generic model-based translation service wrapper based on llama-cpp-python."""

from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Any

try:
    from huggingface_hub import hf_hub_download
except ImportError:  # pragma: no cover
    hf_hub_download = None

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None

logger = logging.getLogger(__name__)

HF_REPO_ID = "bartowski/Qwen2.5-7B-Instruct-GGUF"
HF_FILENAME = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "models"

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional translation engine. "
    "Always translate the source text to the target language exactly and faithfully. "
    "Translate every sentence and every line; do not leave translatable text in the source language. "
    "Output translation only, with no explanation, no notes, no markdown fences, and no extra lines. "
    "Preserve original meaning, tone, and formatting (line breaks, numbering, bullet structure). "
    "Do not omit, summarize, or add information. Keep URLs, emails, and code tokens unchanged unless translation is required. "
    "Preserve person names in original Latin spelling; do not transliterate person names into Chinese. "
    "When target language is Traditional Chinese, use zh-TW style and never output Simplified Chinese characters."
)

TRANSLATION_DECISION_RULES = (
    "Hard constraints (must follow):\n"
    "1) Translate all normal narrative words and grammar into the target language.\n"
    "2) NEVER translate or transliterate person names. Keep person names exactly as original Latin text (same spelling and case).\n"
    "3) Keep unchanged: URLs, emails, API/file paths, code identifiers, versions, and numeric values with units.\n"
    "4) Keep acronyms unchanged: MEC, NFV, SFC, DRL, A3C, QIP, NP-hard.\n"
    "5) For mixed lines, translate narrative parts only and preserve technical tokens exactly.\n"
    "6) Person-name detection heuristic: treat a span as person name if it is two or more Latin words in Title Case (e.g., Lei Wang), possibly separated by commas/and in author lists.\n"
    "7) For zh-TW output, use Traditional Chinese only; any Simplified Chinese characters are invalid output."
)

TRANSLATION_FEW_SHOT = (
    "Few-shot examples:\n"
    "[Example 1]\n"
    "Source: Dongliang Zhang, Lei Wang and Amin Rezaeipanah.\n"
    "Target: Dongliang Zhang、Lei Wang 和 Amin Rezaeipanah。\n"
    "[Example 2]\n"
    "Source: The evaluation results of proposed strategy are promising in different scenarios compared to benchmark algorithms.\n"
    "Target: 與基準演算法相比，所提策略在不同情境下的評估結果展現出良好前景。\n"
    "[Example 3]\n"
    "Source: We apply Asynchronous Advantage Actor-Critic (A3C) as a deep reinforcement learning algorithm to assemble sub-SFCs.\n"
    "Target: 我們採用非同步優勢行動者-評論家（A3C）作為深度強化學習演算法，以組裝子服務功能鏈（sub-SFCs）。\n"
    "[Example 4]\n"
    "Source: We finally evaluate the performance of LVPRU through trace-driven simulations.\n"
    "Target: 我們最終透過追蹤驅動模擬評估 LVPRU 的效能。\n"
    "[Example 5]\n"
    "Source: Index Terms—MCE, NFV, SFC, DRL, network function parallelization, resource demand uncertainty.\n"
    "Target: 關鍵詞—MCE、NFV、SFC、DRL、網路功能平行化、資源需求不確定性。"
)

LANG_MAP: dict[str, tuple[str, str]] = {
    "en": ("English", "en"),
    "chinese_cht": ("Traditional Chinese", "zh-TW"),
    "ch": ("Simplified Chinese", "zh-CN"),
    "korean": ("Korean", "ko"),
    "japan": ("Japanese", "ja"),
    "ta": ("Tamil", "ta"),
    "te": ("Telugu", "te"),
    "ka": ("Georgian", "ka"),
    "th": ("Thai", "th"),
    "el": ("Greek", "el"),
    "latin": ("Latin", "la"),
    "arabic": ("Arabic", "ar"),
    "east_slavic": ("Russian", "ru"),
    "cyrillic": ("Bulgarian", "bg"),
    "devanagari": ("Hindi", "hi"),
}


def ensure_model_downloaded(model_dir: Path = DEFAULT_MODEL_DIR) -> Path:
    """Ensure target GGUF model file exists in local models directory."""
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / HF_FILENAME
    if model_path.exists():
        return model_path

    if hf_hub_download is None:
        raise RuntimeError(
            "huggingface_hub 未安裝，無法自動下載模型。請先安裝 huggingface-hub。"
        )

    logger.info("模型不存在，開始從 HuggingFace 下載: %s", model_path)
    hf_hub_download(
        repo_id=HF_REPO_ID,
        filename=HF_FILENAME,
        local_dir=str(model_dir),
    )

    if not model_path.exists():
        raise FileNotFoundError(f"模型下載完成後仍找不到檔案: {model_path}")

    logger.info("模型下載完成: %s", model_path)
    return model_path


class ModelTranslator:
    """Single-paragraph translator backed by a local GGUF model."""

    def __init__(
        self,
        model_dir: Path = DEFAULT_MODEL_DIR,
        n_gpu_layers: int = -1,
        n_ctx: int = 2048,
        verbose: bool = False,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.verbose = verbose

        self._llm: Any | None = None
        self.model_path = ensure_model_downloaded(self.model_dir)

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

    def _generate_translation(self, user_prompt: str) -> str:
        if self._llm is None:
            raise RuntimeError("ModelTranslator 尚未載入模型，請在 with 區塊內呼叫")

        if hasattr(self._llm, "create_chat_completion"):
            response = self._llm.create_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"{TRANSLATION_SYSTEM_PROMPT}\n\n"
                            f"{TRANSLATION_DECISION_RULES}\n\n"
                            f"{TRANSLATION_FEW_SHOT}"
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
                temperature=0.0,
            )
        else:
            response = self._llm(
                (
                    f"[System]\n{TRANSLATION_SYSTEM_PROMPT}\n\n"
                    f"{TRANSLATION_DECISION_RULES}\n\n"
                    f"{TRANSLATION_FEW_SHOT}\n\n"
                    f"[User]\n{user_prompt}"
                ),
                max_tokens=512,
                temperature=0.0,
                stop=[],
            )

        return self._extract_text_from_response(response)

    def _load(self) -> None:
        if self._llm is not None:
            logger.warning("模型已載入，跳過重複載入")
            return

        if Llama is None:
            raise RuntimeError(
                "llama-cpp-python 未安裝，無法載入模型。請先安裝 llama-cpp-python。"
            )

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

    def translate_paragraph(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if self._llm is None:
            raise RuntimeError("ModelTranslator 尚未載入模型，請在 with 區塊內呼叫")

        if src_lang not in LANG_MAP or tgt_lang not in LANG_MAP:
            raise ValueError(f"不支援的語言代碼: {src_lang} / {tgt_lang}")

        if text.strip() == "":
            return ""

        src_display, _src_iso = LANG_MAP[src_lang]
        tgt_display, _tgt_iso = LANG_MAP[tgt_lang]
        lines = text.splitlines()
        if len(lines) <= 1:
            user_prompt = (
                f"Translate the following text from {src_display} to {tgt_display}.\n"
                "Return only the translated text in the target language.\n"
                "Translate all natural language words. Keep only URLs, emails, code tokens, and file/API paths unchanged.\n"
                "<SOURCE_TEXT>\n"
                f"{text}\n"
                "</SOURCE_TEXT>"
            )
            result = self._generate_translation(user_prompt)
        else:
            translated_lines: list[str] = []
            for line in lines:
                if line.strip() == "":
                    translated_lines.append("")
                    continue

                line_prompt = (
                    f"Translate this one line from {src_display} to {tgt_display}.\n"
                    "Return exactly one translated line only.\n"
                    "Translate all natural language words. Keep only URLs, emails, code tokens, and file/API paths unchanged.\n"
                    "<SOURCE_LINE>\n"
                    f"{line}\n"
                    "</SOURCE_LINE>"
                )
                translated = self._generate_translation(line_prompt)
                translated_lines.append(translated.replace("\n", " ").strip())

            result = "\n".join(translated_lines).strip()

        if not result:
            logger.warning(
                "翻譯結果為空字串 (src=%s, tgt=%s)",
                src_lang,
                tgt_lang,
            )
        return result
