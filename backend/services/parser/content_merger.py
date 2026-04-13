"""Utilities for merging MinerU v1 and v2 content JSON into a unified schema."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MinerUItem:
    """Unified item schema merged from MinerU v1 and v2 outputs."""

    type_v1: str
    type_v2: str
    text: str
    translated_text: str | None
    bbox: list[int]
    page_idx: int
    img_path: str | None
    table_html: str | None
    math_latex: str | None
    title_level: int | None
    caption: list[str] | None


def _load_v2_flat(path: str) -> list[dict]:
    """Load v2 page-grouped JSON and flatten items with inferred page index."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        logger.warning("Unexpected v2 root type in %s: %s", file_path, type(data))
        return []

    flat_items: list[dict] = []
    for page_idx, page_items in enumerate(data):
        if not isinstance(page_items, list):
            logger.warning(
                "Skip non-list v2 page entry at index %s in %s",
                page_idx,
                file_path,
            )
            continue

        for item in page_items:
            if not isinstance(item, dict):
                logger.warning(
                    "Skip non-dict v2 item at page %s in %s",
                    page_idx,
                    file_path,
                )
                continue

            item["_page_idx_inferred"] = page_idx
            flat_items.append(item)

    return flat_items


def _load_v1(path: str) -> list[dict]:
    """Load v1 flat JSON array and return list items."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"v1 content list file not found: {file_path.resolve()}")

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        logger.warning("Unexpected v1 root type in %s: %s", file_path, type(data))
        return []

    return data


def _extract_spans(spans: list[dict] | None, skip_equation_inline: bool = False) -> str:
    """Extract readable text from MinerU span arrays."""
    if not spans:
        return ""

    collected: list[str] = []
    for span in spans:
        if not isinstance(span, dict):
            logger.warning("Skip non-dict span: %r", span)
            continue

        span_type = span.get("type")
        content = str(span.get("content", "") or "")

        if span_type == "text":
            collected.append(content)
            continue

        if span_type == "equation_inline":
            if not skip_equation_inline:
                collected.append(content)
            continue

        logger.warning("Skip unsupported span type: %r", span_type)

    return " ".join(collected).strip()


def _merge_item(v1: dict, v2: dict) -> MinerUItem:
    """Merge one v1 item and one matched v2 item into a MinerUItem."""
    type_v1 = str(v1.get("type", "unknown") or "unknown")
    type_v2 = str(v2.get("type", "unknown") or "unknown")

    text = str(v1.get("text", "") or "")
    page_idx = int(v1.get("page_idx", 0) or 0)

    raw_bbox = v1.get("bbox", [])
    bbox = raw_bbox if isinstance(raw_bbox, list) else []

    raw_content = v2.get("content", {})
    content = raw_content if isinstance(raw_content, dict) else {}

    title_level: int | None = None
    if type_v2 == "title":
        level = content.get("level")
        title_level = int(level) if isinstance(level, int) else None

    math_latex: str | None = None
    if type_v2 == "equation_interline":
        math_content = content.get("math_content")
        if isinstance(math_content, str) and math_content.strip():
            math_latex = math_content.strip()
        else:
            fallback = str(v1.get("text", "") or "")
            if fallback.strip():
                stripped = re.sub(r"^\s*\$\$\s*|\s*\$\$\s*$", "", fallback, flags=re.DOTALL)
                stripped = stripped.strip()
                math_latex = stripped or None

    table_html: str | None = None
    html_v2 = content.get("html")
    if isinstance(html_v2, str) and html_v2.strip():
        table_html = html_v2
    else:
        html_v1 = v1.get("table_body")
        if isinstance(html_v1, str) and html_v1.strip():
            table_html = html_v1

    img_path: str | None = None
    image_source = content.get("image_source")
    if isinstance(image_source, dict):
        image_path = image_source.get("path")
        if isinstance(image_path, str) and image_path.strip():
            img_path = image_path

    caption_key_by_type = {
        "image": "image_caption",
        "table": "table_caption",
        "chart": "chart_caption",
        "algorithm": "algorithm_caption",
        "code": "code_caption",
    }
    caption: list[str] | None = None
    caption_key = caption_key_by_type.get(type_v2)
    if caption_key is not None:
        raw_caption = content.get(caption_key)
        spans = raw_caption if isinstance(raw_caption, list) else []
        caption_text = _extract_spans(spans)
        if caption_text:
            caption = [caption_text]

    return MinerUItem(
        type_v1=type_v1,
        type_v2=type_v2,
        text=text,
        translated_text=None,
        bbox=bbox,
        page_idx=page_idx,
        img_path=img_path,
        table_html=table_html,
        math_latex=math_latex,
        title_level=title_level,
        caption=caption,
    )


def load_and_merge(v1_path: str, v2_path: str) -> list[MinerUItem]:
    """Load MinerU v1/v2 JSON files and merge them by bbox join key."""
    v1_items = _load_v1(v1_path)
    v2_items = _load_v2_flat(v2_path)

    v2_by_bbox: dict[tuple[int, ...], dict] = {}
    for item in v2_items:
        bbox = item.get("bbox")
        if isinstance(bbox, list):
            v2_by_bbox[tuple(bbox)] = item

    merged: list[MinerUItem] = []
    for item_v1 in v1_items:
        if not isinstance(item_v1, dict):
            logger.warning("Skip non-dict v1 item: %r", item_v1)
            continue

        bbox_key = tuple(item_v1.get("bbox", []))
        item_v2 = v2_by_bbox.get(bbox_key, {})
        if not item_v2:
            logger.debug(
                "Unmatched bbox for v1 item (page_idx=%s, type_v1=%s)",
                item_v1.get("page_idx"),
                item_v1.get("type", "unknown"),
            )

        merged.append(_merge_item(item_v1, item_v2))

    return merged


__all__ = ["MinerUItem", "load_and_merge"]
