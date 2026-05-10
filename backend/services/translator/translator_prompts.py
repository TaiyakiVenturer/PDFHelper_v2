"""Shared constants, patterns, and prompts for the model translator."""

from __future__ import annotations

import re


CONTEXT_PREVIEW_CHARS = 180
MAX_EMPTY_OUTPUT_ATTEMPTS = 3
MATH_PLACEHOLDER_PREFIX = "__EQ_{index:04d}__"

MATH_SEGMENT_PATTERN = re.compile(
    r"(?<!\\)\$\$(?:.|\n)+?(?<!\\)\$\$|(?<!\\)\$(?!\$)(?:[^$\\\n]|\\.)*?(?<!\\)\$"
)
PLACEHOLDER_PATTERN = re.compile(r"__EQ_\d{4}__")

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
    "7) For zh-TW output, use Traditional Chinese only; any Simplified Chinese characters are invalid output.\n"
    "8) Placeholder tokens matching __EQ_0001__ style are immutable. Copy them exactly as-is; do not add, remove, reorder, split, or alter characters around placeholders."
)

PLACEHOLDER_REPAIR_SYSTEM_RULES = (
    "Placeholder-repair mode: keep every __EQ_0001__ style token exactly unchanged. "
    "Do not add, remove, reorder, split, or merge placeholder tokens. "
    "Do not introduce or modify any $ or $$ delimiters outside placeholders."
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
