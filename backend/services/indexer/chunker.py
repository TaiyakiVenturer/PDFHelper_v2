from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from services.indexer import indexer_config as cfg
from services.parser.content_merger import MinerUItem

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None


logger = logging.getLogger(__name__)


@dataclass
class IndexChunk:
    chunk_id: str
    embedding_text: str
    metadata: dict[str, Any]


class StructureAwareChunker:
    _SKIP_TYPES = {
        "page_header",
        "page_footer",
        "page_number",
        "page_footnote",
        "list",
    }

    def __init__(self) -> None:
        if tiktoken is None:
            raise RuntimeError("tiktoken is not installed")
        self._token_counter = tiktoken.get_encoding(cfg.TIKTOKEN_ENCODING)

    def chunk(self, items: list[MinerUItem]) -> list[IndexChunk]:
        chunks: list[IndexChunk] = []
        current_section_title = ""
        prev_paragraph_text = ""
        seq = 0

        for item in items:
            type_v2 = str(item.type_v2 or "").strip()

            if type_v2 in self._SKIP_TYPES:
                continue

            if type_v2 == "title":
                current_section_title = str(item.text or "").strip()
                continue

            rendered: list[tuple[str, dict[str, Any]]] = []
            if type_v2 == "paragraph":
                rendered = self._render_paragraph(item, current_section_title)
                paragraph_text = str(item.text or "").strip()
                if paragraph_text:
                    prev_paragraph_text = paragraph_text
            elif type_v2 == "equation_interline":
                rendered = self._render_equation(
                    item,
                    current_section_title,
                    prev_paragraph_text,
                )
            elif type_v2 == "table":
                rendered = self._render_table(item, current_section_title)
            elif type_v2 == "image":
                rendered = self._render_visual(item, current_section_title, "image")
            elif type_v2 == "chart":
                rendered = self._render_visual(item, current_section_title, "chart")
            elif type_v2 == "algorithm":
                rendered = self._render_algorithm(item, current_section_title)

            for embedding_text, metadata in rendered:
                page_idx = int(metadata.get("page_idx", 0) or 0)
                chunk_type = str(metadata.get("type_v2", "unknown") or "unknown")
                chunk_id = f"{page_idx}_{chunk_type}_{seq}"
                chunks.append(
                    IndexChunk(
                        chunk_id=chunk_id,
                        embedding_text=embedding_text,
                        metadata=metadata,
                    )
                )
                seq += 1

        return chunks

    def _render_paragraph(
        self,
        item: MinerUItem,
        section_title: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        text = str(item.text or "").strip()
        if text == "":
            return []

        embedding_text = self._compose_embedding_text(section_title, text)
        if self._count_tokens(embedding_text) <= cfg.CHUNK_TOKEN_LIMIT:
            return [
                (
                    embedding_text,
                    {
                        "page_idx": int(item.page_idx),
                        "type_v2": "paragraph",
                        "section_title": section_title,
                        "text": text,
                    },
                )
            ]

        chunks: list[tuple[str, dict[str, Any]]] = []
        for segment in self._split_long_text(text, section_title):
            chunks.append(
                (
                    self._compose_embedding_text(section_title, segment),
                    {
                        "page_idx": int(item.page_idx),
                        "type_v2": "paragraph",
                        "section_title": section_title,
                        "text": segment,
                    },
                )
            )
        return chunks

    def _render_equation(
        self,
        item: MinerUItem,
        section_title: str,
        prev_paragraph_text: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        math_latex = str(item.math_latex or "").strip()
        if math_latex == "":
            return []

        parts: list[str] = []
        if section_title.strip():
            parts.append(section_title.strip())
        if prev_paragraph_text.strip():
            parts.append(prev_paragraph_text.strip())
        parts.append(math_latex)

        return [
            (
                "\n\n".join(parts),
                {
                    "page_idx": int(item.page_idx),
                    "type_v2": "equation_interline",
                    "section_title": section_title,
                    "text": f"$$\n{math_latex}\n$$",
                    "math_latex": math_latex,
                },
            )
        ]

    def _render_table(
        self,
        item: MinerUItem,
        section_title: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        caption = self._join_caption(item.caption)
        table_html = str(item.table_html or "")
        text = caption

        if text == "":
            stripped = re.sub(r"<[^>]+>", " ", table_html)
            text = " ".join(stripped.split())

        if text == "":
            return []

        return [
            (
                self._compose_embedding_text(section_title, text),
                {
                    "page_idx": int(item.page_idx),
                    "type_v2": "table",
                    "section_title": section_title,
                    "text": text,
                    "table_html": table_html,
                    "caption": caption,
                },
            )
        ]

    def _render_visual(
        self,
        item: MinerUItem,
        section_title: str,
        type_v2: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        caption = self._join_caption(item.caption)
        if caption == "":
            logger.debug("Skip %s chunk without caption on page %s", type_v2, item.page_idx)
            return []

        return [
            (
                self._compose_embedding_text(section_title, caption),
                {
                    "page_idx": int(item.page_idx),
                    "type_v2": type_v2,
                    "section_title": section_title,
                    "text": caption,
                    "img_path": str(item.img_path or ""),
                    "caption": caption,
                },
            )
        ]

    def _render_algorithm(
        self,
        item: MinerUItem,
        section_title: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        code_body = str(item.code_body or "").strip()
        if code_body == "":
            return []

        caption = self._join_caption(item.caption)
        parts: list[str] = []
        if section_title.strip():
            parts.append(section_title.strip())
        if caption.strip():
            parts.append(caption.strip())
        parts.append(code_body)

        return [
            (
                "\n\n".join(parts),
                {
                    "page_idx": int(item.page_idx),
                    "type_v2": "algorithm",
                    "section_title": section_title,
                    "text": code_body,
                    "caption": caption,
                },
            )
        ]

    def _split_long_text(self, text: str, section_title: str) -> list[str]:
        chunks: list[str] = []
        remaining = text.strip()
        if remaining == "":
            return chunks

        prefix = ""
        if section_title.strip():
            prefix = f"{section_title.strip()}\n\n"
        prefix_tokens = self._count_tokens(prefix)
        body_token_limit = max(1, cfg.CHUNK_TOKEN_LIMIT - prefix_tokens)

        while remaining:
            full_text = self._compose_embedding_text(section_title, remaining)
            if self._count_tokens(full_text) <= cfg.CHUNK_TOKEN_LIMIT:
                chunks.append(remaining.strip())
                break

            encoded = self._token_counter.encode(remaining)
            if len(encoded) <= body_token_limit:
                chunks.append(remaining.strip())
                break

            target_text = self._token_counter.decode(encoded[:body_token_limit])
            target_index = len(target_text)
            split_index = self._find_split_index(remaining, target_index)

            if split_index <= 0:
                split_index = target_index
                logger.warning(
                    "Long paragraph hard-cut at token boundary (no punctuation within backtrack window)"
                )

            segment = remaining[:split_index].strip()
            if segment == "":
                split_index = max(1, target_index)
                segment = remaining[:split_index].strip()
                if segment == "":
                    break

            chunks.append(segment)
            remaining = remaining[split_index:].strip()

        return chunks

    def _find_split_index(self, text: str, target_index: int) -> int:
        bounded_target = min(max(1, target_index), len(text))
        window_start = max(0, bounded_target - 200)
        window = text[window_start:bounded_target]

        for token in cfg.SPLIT_BOUNDARY_PUNCTUATION:
            idx = window.rfind(token)
            if idx != -1:
                return window_start + idx + len(token)

        return -1

    def _count_tokens(self, text: str) -> int:
        return len(self._token_counter.encode(text))

    @staticmethod
    def _compose_embedding_text(section_title: str, text: str) -> str:
        parts: list[str] = []
        if section_title.strip():
            parts.append(section_title.strip())
        if text.strip():
            parts.append(text.strip())
        return "\n\n".join(parts)

    @staticmethod
    def _join_caption(caption: list[str] | None) -> str:
        if caption is None:
            return ""
        parts = [str(item).strip() for item in caption if str(item).strip()]
        return " ".join(parts)