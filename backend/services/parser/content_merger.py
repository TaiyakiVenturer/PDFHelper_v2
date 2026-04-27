"""Utilities for merging MinerU v1 and v2 content JSON into a unified schema."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _norm_optional_str(raw: object) -> str | None:
    if raw is None:
        return None
    value = str(raw)
    return value if value != "" else None


def _norm_optional_int(raw: object) -> int | None:
    try:
        if raw is None:
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _norm_int(raw: object, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _norm_string_list(raw: object) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    normalized = [str(item) for item in raw]
    return normalized or None


def _norm_bbox(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    bbox: list[int] = []
    for value in raw:
        try:
            bbox.append(int(value))
        except (TypeError, ValueError):
            continue
    return bbox


@dataclass
class MinerUItem:
    """Unified item schema merged from MinerU v1 and v2 outputs."""

    type_v1: str
    type_v2: str
    text: str
    translated_text: str | None
    list_items: list[str] | None
    sub_type: str | None
    text_level: int | None
    bbox: list[int]
    page_idx: int
    img_path: str | None
    table_html: str | None
    math_latex: str | None
    code_body: str | None
    footnote: list[str] | None
    title_level: int | None
    caption: list[str] | None

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "MinerUItem":
        """Deserialize a MinerUItem from a flat dict (e.g. from DB or cache)."""
        return cls(
            type_v1=str(raw.get("type_v1", "unknown") or "unknown"),
            type_v2=str(raw.get("type_v2", "unknown") or "unknown"),
            text=str(raw.get("text", "") or ""),
            translated_text=_norm_optional_str(raw.get("translated_text")),
            list_items=_norm_string_list(raw.get("list_items")),
            sub_type=_norm_optional_str(raw.get("sub_type")),
            text_level=_norm_optional_int(raw.get("text_level")),
            bbox=_norm_bbox(raw.get("bbox")),
            page_idx=_norm_int(raw.get("page_idx"), default=0),
            img_path=_norm_optional_str(raw.get("img_path")),
            table_html=_norm_optional_str(raw.get("table_html")),
            math_latex=_norm_optional_str(raw.get("math_latex")),
            code_body=_norm_optional_str(raw.get("code_body")),
            footnote=_norm_string_list(raw.get("footnote")),
            title_level=_norm_optional_int(raw.get("title_level")),
            caption=_norm_string_list(raw.get("caption")),
        )


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


def _extract_text_list(
    raw_entries: object,
    *,
    field_name: str,
    nested_span_key: str | None = None,
) -> list[str] | None:
    """Normalize mixed list payloads into a list of plain text strings."""
    if raw_entries is None:
        return None

    if not isinstance(raw_entries, list):
        logger.warning("Skip non-list %s: %r", field_name, raw_entries)
        return None

    normalized: list[str] = []
    for entry in raw_entries:
        text = ""

        if isinstance(entry, str):
            text = entry.strip()
        elif isinstance(entry, dict):
            if nested_span_key is not None and isinstance(entry.get(nested_span_key), list):
                text = _extract_spans(entry.get(nested_span_key))
            else:
                text = _extract_spans([entry])
        elif isinstance(entry, list) and all(isinstance(span, dict) for span in entry):
            text = _extract_spans(entry)
        else:
            logger.warning("Skip unsupported %s entry: %r", field_name, entry)

        stripped = text.strip()
        if stripped:
            normalized.append(stripped)

    return normalized or None


def _normalize_list_items(v1_list_items: object, v2_list_items: object) -> list[str] | None:
    """Normalize reference/list entries from v1 and v2 formats."""
    from_v1 = _extract_text_list(v1_list_items, field_name="list_items")
    if from_v1:
        return from_v1

    return _extract_text_list(
        v2_list_items,
        field_name="list_items",
        nested_span_key="item_content",
    )


def _extract_v2_text(content: dict, key: str) -> str:
    """Extract text from a v2 content key that stores span arrays."""
    value = content.get(key)
    if isinstance(value, list):
        return _extract_spans(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _extract_single_span_block(raw_value: object) -> list[str] | None:
    """Treat a span array as one logical text block."""
    if isinstance(raw_value, list) and all(isinstance(item, dict) for item in raw_value):
        text = _extract_spans(raw_value)
        if text:
            return [text]
    return None


def _derive_text(v1: dict, type_v2: str, content: dict) -> str:
    """Derive primary text with v1-first and v2 fallback strategy."""
    from_v1 = str(v1.get("text", "") or "").strip()
    if from_v1:
        return from_v1

    key_by_v2_type = {
        "paragraph": "paragraph_content",
        "title": "title_content",
        "page_header": "page_header_content",
        "page_footer": "page_footer_content",
        "page_number": "page_number_content",
        "page_footnote": "page_footnote_content",
        "aside_text": "aside_text_content",
    }
    key = key_by_v2_type.get(type_v2)
    if key is not None:
        return _extract_v2_text(content, key)

    return ""


def _derive_sub_type(v1: dict, type_v2: str, content: dict) -> str | None:
    """Normalize sub_type across v1/v2 conventions."""
    v1_sub_type = v1.get("sub_type")
    if isinstance(v1_sub_type, str) and v1_sub_type.strip():
        return v1_sub_type.strip()

    if type_v2 == "list":
        list_type = content.get("list_type")
        if isinstance(list_type, str) and list_type.strip():
            if list_type == "reference_list":
                return "ref_text"
            return list_type.strip()

    if type_v2 == "algorithm":
        return "algorithm"

    if type_v2 == "code":
        for key in ("sub_type", "code_subtype", "code_type"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _derive_code_body(v1: dict, type_v2: str, content: dict) -> str | None:
    """Derive code/algorithm body with v1-first and v2 fallback."""
    v1_code_body = v1.get("code_body")
    if isinstance(v1_code_body, str) and v1_code_body.strip():
        return v1_code_body

    if type_v2 == "algorithm":
        text = _extract_v2_text(content, "algorithm_content")
        return text or None

    if type_v2 == "code":
        text = _extract_v2_text(content, "code_content")
        return text or None

    return None


def _derive_text_level(v1: dict, type_v2: str, content: dict) -> int | None:
    """Derive heading level from v1 text_level or v2 title level."""
    raw_text_level = v1.get("text_level")
    if isinstance(raw_text_level, int):
        return raw_text_level

    if type_v2 == "title":
        raw_level = content.get("level")
        if isinstance(raw_level, int):
            return raw_level

    return None


def _derive_title_level(type_v2: str, content: dict, text_level: int | None) -> int | None:
    """Keep backward-compatible title_level while supporting v1 heading levels."""
    if type_v2 == "title":
        raw_level = content.get("level")
        if isinstance(raw_level, int):
            return raw_level
    return text_level


def _derive_img_path(v1: dict, content: dict) -> str | None:
    """Derive image path from v2 image_source with v1 img_path fallback."""
    image_source = content.get("image_source")
    if isinstance(image_source, dict):
        image_path = image_source.get("path")
        if isinstance(image_path, str) and image_path.strip():
            return image_path

    v1_img_path = v1.get("img_path")
    if isinstance(v1_img_path, str) and v1_img_path.strip():
        return v1_img_path

    return None


def _derive_caption(v1: dict, type_v2: str, content: dict) -> list[str] | None:
    """Derive caption list from v2 content or v1 fallback fields."""
    key_by_type = {
        "image": "image_caption",
        "table": "table_caption",
        "chart": "chart_caption",
        "algorithm": "algorithm_caption",
        "code": "code_caption",
    }
    key = key_by_type.get(type_v2)
    if key is None:
        return None

    from_v2 = _extract_single_span_block(content.get(key))
    if from_v2:
        return from_v2

    from_v2 = _extract_text_list(content.get(key), field_name=key)
    if from_v2:
        return from_v2

    return _extract_text_list(v1.get(key), field_name=key)


def _derive_footnote(v1: dict, type_v2: str, content: dict) -> list[str] | None:
    """Derive footnote list from v2 content or v1 fallback fields."""
    key_by_type = {
        "image": "image_footnote",
        "table": "table_footnote",
        "chart": "chart_footnote",
        "algorithm": "algorithm_footnote",
        "code": "code_footnote",
    }
    key = key_by_type.get(type_v2)
    if key is not None:
        from_v2 = _extract_single_span_block(content.get(key))
        if from_v2:
            return from_v2

        from_v2 = _extract_text_list(content.get(key), field_name=key)
        if from_v2:
            return from_v2
        return _extract_text_list(v1.get(key), field_name=key)

    if type_v2 == "page_footnote":
        from_v2 = _extract_single_span_block(content.get("page_footnote_content"))
        if from_v2:
            return from_v2

        from_v2 = _extract_text_list(content.get("page_footnote_content"), field_name="page_footnote")
        if from_v2:
            return from_v2

    return None


def _merge_item(v1: dict, v2: dict) -> MinerUItem:
    """Merge one v1 item and one matched v2 item into a MinerUItem."""
    type_v1 = str(v1.get("type", "unknown") or "unknown")
    type_v2 = str(v2.get("type", "unknown") or "unknown")

    raw_content = v2.get("content", {})
    content = raw_content if isinstance(raw_content, dict) else {}

    text = _derive_text(v1, type_v2, content)
    list_items = _normalize_list_items(v1.get("list_items"), content.get("list_items"))
    sub_type = _derive_sub_type(v1, type_v2, content)
    text_level = _derive_text_level(v1, type_v2, content)
    page_idx = int(v1.get("page_idx", 0) or 0)

    raw_bbox = v1.get("bbox", [])
    bbox = raw_bbox if isinstance(raw_bbox, list) else []

    title_level = _derive_title_level(type_v2, content, text_level)

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

    img_path = _derive_img_path(v1, content)
    code_body = _derive_code_body(v1, type_v2, content)
    caption = _derive_caption(v1, type_v2, content)
    footnote = _derive_footnote(v1, type_v2, content)

    return MinerUItem(
        type_v1=type_v1,
        type_v2=type_v2,
        text=text,
        translated_text=None,
        list_items=list_items,
        sub_type=sub_type,
        text_level=text_level,
        bbox=bbox,
        page_idx=page_idx,
        img_path=img_path,
        table_html=table_html,
        math_latex=math_latex,
        code_body=code_body,
        footnote=footnote,
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
