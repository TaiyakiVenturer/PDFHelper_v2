from __future__ import annotations

import json
import re
from pathlib import Path


class MarkdownReconstructor:
    def __init__(self) -> None:
        pass

    def reconstruct(
        self,
        json_path: str,
        use_translated: bool = False,
    ) -> str:
        source_path = Path(json_path)
        if not source_path.exists():
            raise FileNotFoundError(
                f"Input json file not found: {source_path.resolve()}"
            )

        with source_path.open("r", encoding="utf-8") as source_file:
            source_data = json.load(source_file)

        if not isinstance(source_data, list):
            raise ValueError("Input json root must be a list")

        output_stem = self._derive_output_stem(source_path.stem)
        if use_translated:
            output_name = f"{output_stem}_translated.md"
        else:
            output_name = f"{output_stem}.md"
        output_path = source_path.with_name(output_name)

        rendered_blocks: list[str] = []
        for item in source_data:
            if not isinstance(item, dict):
                continue

            rendered = self._render_item(item, use_translated)
            if rendered != "":
                rendered_blocks.append(rendered)

        markdown_content = "\n\n".join(rendered_blocks)
        with output_path.open("w", encoding="utf-8") as output_file:
            output_file.write(markdown_content)

        return str(output_path.resolve())

    @staticmethod
    def _derive_output_stem(stem: str) -> str:
        normalized_stem = stem
        for suffix in ("_content_list_merged", "_translated"):
            if normalized_stem.endswith(suffix):
                normalized_stem = normalized_stem.removesuffix(suffix)
        return normalized_stem

    def _render_item(self, item: dict, use_translated: bool) -> str:
        item_type = str(item.get("type_v2", "unknown") or "unknown")
        text = self._normalize_math_block(self._resolve_text(item, use_translated))

        match item_type:
            case "title":
                return self._render_title(item, text)
            case "paragraph":
                return self._render_paragraph(item, text)
            case "equation_interline":
                return self._render_equation(item)
            case "table":
                return self._render_table(item)
            case "image" | "chart" | "seal":
                return self._render_image(item)
            case "list":
                return self._render_list(item)
            case "code":
                return self._render_code(item)
            case "algorithm":
                return self._render_algorithm(item)
            case "page_header" | "page_footer" | "page_number":
                return ""
            case _:
                if text.strip() == "":
                    return ""
                return self._render_paragraph(item, text)

    @staticmethod
    def _resolve_text(item: dict, use_translated: bool) -> str:
        if use_translated:
            translated_text = item.get("translated_text")
            if translated_text:
                return str(translated_text)
        return str(item.get("text", "") or "")

    @staticmethod
    def _normalize_math_block(text: str) -> str:
        if text == "":
            return ""

        normalized = re.sub(r"(?<!\n)\$\$", "\n$$", text)
        normalized = re.sub(r"\$\$(?!\n)", "$$\n", normalized)
        return normalized

    def _render_title(self, item: dict, text: str) -> str:
        if text.strip() == "":
            return ""

        level = item.get("title_level", 1)
        if not isinstance(level, int):
            level = 1
        level = max(1, min(level, 6))

        return f"{'#' * level} {text.strip()}"

    @staticmethod
    def _render_paragraph(item: dict, text: str) -> str:
        _ = item
        if text.strip() == "":
            return ""
        return text

    @staticmethod
    def _render_equation(item: dict) -> str:
        latex = str(item.get("math_latex", "") or "").strip()
        if latex != "":
            return f"$$\n{latex}\n$$"

        image_path = str(item.get("img_path", "") or "").strip()
        if image_path == "":
            return ""
        return f"![equation]({image_path})"

    def _render_table(self, item: dict) -> str:
        table_body = str(item.get("table_html", "") or "").strip()
        if table_body == "":
            image_path = str(item.get("img_path", "") or "").strip()
            if image_path == "":
                return ""
            table_body = f"![table]({image_path})"

        parts: list[str] = []
        caption_text = self._join_text_list(item.get("caption"))
        if caption_text != "":
            parts.append(caption_text)

        parts.append(table_body)

        footnote_text = self._join_text_list(item.get("footnote"))
        if footnote_text != "":
            parts.append(footnote_text)

        return "\n\n".join(parts)

    def _render_image(self, item: dict) -> str:
        image_path = str(item.get("img_path", "") or "").strip()
        if image_path == "":
            return ""

        caption = self._first_text(item.get("caption"))
        parts = [f"![{caption}]({image_path})"]

        footnote_text = self._join_text_list(item.get("footnote"))
        if footnote_text != "":
            parts.append(footnote_text)

        return "\n\n".join(parts)

    @staticmethod
    def _render_list(item: dict) -> str:
        list_items = item.get("list_items")
        if not isinstance(list_items, list):
            return ""

        rows: list[str] = []
        for list_item in list_items:
            row = str(list_item or "").strip()
            if row != "":
                rows.append(row)

        return "\n\n".join(rows)

    _ALGORITHM_KEYWORDS = re.compile(
        r'\b(for|if|else|then|do|end|repeat|until|while|return|break|to|not|and|or)\b'
    )

    def _render_algorithm(self, item: dict) -> str:
        code_body = item.get("code_body")
        if not isinstance(code_body, str) or code_body.strip() == "":
            return ""

        rendered: list[str] = []
        first_content = True

        for raw_line in code_body.split("\n"):
            line = raw_line.rstrip()
            if line == "":
                rendered.append(">")
                continue

            if first_content:
                first_content = False
                rendered.append(f"> **{line}**")
                rendered.append(">")
                continue

            io_match = re.match(r'^(Input|Output):(.*)', line)
            if io_match:
                label = io_match.group(1)
                rest = io_match.group(2).strip()
                rendered.append(f"> **{label}:** {rest}  ")
                continue

            num_match = re.match(r'^(\d+)\s+(.*)', line)
            if num_match:
                num = num_match.group(1)
                rest = self._bold_keywords(num_match.group(2))
                rendered.append(f"> `{num}` {rest}  ")
            else:
                rendered.append(f"> {line}  ")

        block = "\n".join(rendered)
        caption = self._join_text_list(item.get("caption"))
        if caption:
            return "\n\n".join([caption, block])
        return block

    def _bold_keywords(self, text: str) -> str:
        def replacer(m: re.Match) -> str:
            kw = m.group(0)
            return f"**{kw}**"
        return self._ALGORITHM_KEYWORDS.sub(replacer, text)

    def _render_code(self, item: dict) -> str:
        code_body = item.get("code_body")
        if not isinstance(code_body, str) or code_body.strip() == "":
            return ""

        code_block = "\n".join(["```", code_body.rstrip("\n"), "```"])
        caption = self._join_text_list(item.get("caption"))
        if caption == "":
            return code_block
        return "\n\n".join([caption, code_block])

    @staticmethod
    def _join_text_list(value: object) -> str:
        if not isinstance(value, list):
            return ""

        segments: list[str] = []
        for entry in value:
            segment = str(entry or "").strip()
            if segment != "":
                segments.append(segment)
        return "\n".join(segments)

    @staticmethod
    def _first_text(value: object) -> str:
        if not isinstance(value, list) or len(value) == 0:
            return ""

        first = str(value[0] or "").strip()
        return first