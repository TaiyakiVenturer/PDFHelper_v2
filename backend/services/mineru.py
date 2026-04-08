import hashlib
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]

_TQDM_PERCENT_PATTERN = re.compile(r"(?P<pct>\d{1,3})%\|")
_PROGRESS_STAGES: tuple[tuple[tuple[str, ...], float, float, str], ...] = (
    (("submitting batch", "start mineru fastapi service",), 2.0, 4.0, "處理中: 初始化 MinerU 服務",),
    (("fetching", "docanalysis init", "model init",), 4.0, 20.0, "處理中: 載入模型與資源",),
    (("layout predict",), 20.0, 45.0, "處理中: 版面預測"),
    (("table-ocr det", "table-ocr rec", "table-ocr",), 45.0, 65.0, "處理中: 表格 OCR 辨識",),
    (("table-wireless", "table-wired",), 65.0, 78.0, "處理中: 表格結構預測",),
    (("ocr-det", "ocr-rec", "seal predict",), 78.0, 90.0, "處理中: 文字辨識",),
    (("processing pages",), 90.0, 99.0, "處理中: 最後處理頁面"),
    (("completed batch", "batch finished",), 99.0, 100.0, "處理完成",),
)


class OutputFilePaths(BaseModel):
    markdown: str | None
    json: str | None
    images: list[str] = Field(default_factory=list)


class ProcessResult(BaseModel):
    success: bool
    output_path: str
    output_file_paths: OutputFilePaths
    processing_time: float
    stdout: str
    error: str
    returncode: int


def _resolve_safe_filename(
    pdf_path: str,
    output_dir: str,
) -> tuple[str, str, str | None]:
    """Resolve a safe filename for CLI processing without side effects."""
    original_stem = Path(pdf_path).stem
    projected_output = os.path.join(
        os.path.abspath(output_dir),
        original_stem,
        "auto",
        f"{original_stem}_content_list.json",
    )

    has_illegal_chars = re.match(r"^[a-zA-Z0-9.-]+$", original_stem) is None
    name_too_short = len(original_stem) < 3
    name_too_long = len(original_stem) > 50
    path_too_long = len(projected_output) > 250

    if not any([has_illegal_chars, name_too_short, name_too_long, path_too_long]):
        return original_stem, pdf_path, None

    hash_part = hashlib.md5(original_stem.encode("utf-8")).hexdigest()[:8]
    safe_stem = f"doc_{hash_part}"
    safe_pdf_path = str(Path(pdf_path).with_name(f"{safe_stem}.pdf"))

    if os.path.normcase(os.path.abspath(pdf_path)) == os.path.normcase(
        os.path.abspath(safe_pdf_path)
    ):
        return safe_stem, pdf_path, None

    return safe_stem, safe_pdf_path, safe_pdf_path


def _parse_progress_line(line: str) -> tuple[float, str] | None:
    """Parse one MinerU output line into a progress update tuple."""
    if not line:
        return None

    normalized = line.strip().lower()
    percent_match = _TQDM_PERCENT_PATTERN.search(normalized)
    percent: float | None = None
    if percent_match is not None:
        raw_percent = float(percent_match.group("pct"))
        percent = max(0.0, min(100.0, raw_percent))

    for keywords, stage_start, stage_end, message in _PROGRESS_STAGES:
        if not any(keyword in normalized for keyword in keywords):
            continue

        if percent is None:
            return stage_start, message

        stage_percent = stage_start + (
            (stage_end - stage_start) * (percent / 100.0)
        )
        return round(stage_percent, 2), message

    return None


class MinerUCLIWrapper:
    """Stateless wrapper around MinerU CLI."""

    def __init__(
        self,
        output_dir: str,
        on_progress: ProgressCallback | None = None,
        verbose: bool = False,
    ) -> None:
        if not os.path.isabs(output_dir):
            raise ValueError("output_dir must be an absolute path")

        self.output_dir = os.path.abspath(output_dir)
        self._on_progress = on_progress
        self.verbose = verbose

        os.makedirs(self.output_dir, exist_ok=True)

    def _build_command(
        self,
        pdf_path: str,
        method: Literal["auto", "txt", "ocr"],
        lang: str,
        formula: bool,
        table: bool,
        start: int | None,
        end: int | None,
    ) -> list[str]:
        # pipeline is the only supported backend.
        command = [
            "mineru",
            "-p", pdf_path,
            "-o", self.output_dir,
            "-m", method,
            "-b", "pipeline",
            "-l", lang,
            "-f", str(formula).lower(),
            "-t", str(table).lower(),
        ]

        if start is not None:
            command.extend(["-s", str(start)])
        if end is not None:
            command.extend(["-e", str(end)])

        return command

    def _find_output_files(
        self,
        output_dir: str,
        stem: str,
        method: Literal["auto", "txt", "ocr"],
    ) -> OutputFilePaths:
        root = os.path.join(output_dir, stem, method)
        markdown_path = os.path.join(root, f"{stem}.md")
        json_path_v1 = os.path.join(root, f"{stem}_content_list.json")
        json_path_v2 = os.path.join(root, f"{stem}_content_list_v2.json")
        images_dir = os.path.join(root, "images")

        if not os.path.exists(root):
            logger.warning("Expected output directory missing: %s", root)
        if not os.path.exists(markdown_path):
            logger.warning("Expected markdown file missing: %s", markdown_path)
        has_json_v1 = os.path.exists(json_path_v1)
        has_json_v2 = os.path.exists(json_path_v2)
        if not has_json_v2 and not has_json_v1:
            logger.warning(
                "Expected json file missing: %s or %s",
                json_path_v1,
                json_path_v2,
            )
        if not os.path.exists(images_dir):
            logger.warning("Expected image directory missing: %s", images_dir)

        json_path: str | None = None
        if has_json_v2:
            json_path = json_path_v2
        elif has_json_v1:
            json_path = json_path_v1

        images: list[str] = []
        if os.path.isdir(images_dir):
            with os.scandir(images_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    if entry.name.lower().endswith((".png", ".jpg", ".jpeg")):
                        images.append(entry.path)
            images.sort()

        return OutputFilePaths(
            markdown=markdown_path if os.path.exists(markdown_path) else None,
            json=json_path,
            images=images,
        )

    def process(
        self,
        pdf_path: str,
        method: Literal["auto", "txt", "ocr"] = "auto",
        lang: str = "en",
        formula: bool = True,
        table: bool = True,
        start: int | None = None,
        end: int | None = None,
    ) -> ProcessResult:
        base_result = {
            "success": False,
            "output_path": self.output_dir,
            "output_file_paths": {
                "markdown": None,
                "json": None,
                "images": [],
            },
            "processing_time": 0.0,
            "stdout": "",
            "error": "",
            "returncode": -1,
        }

        if not os.path.isabs(pdf_path):
            result = dict(base_result)
            result["error"] = "pdf_path must be an absolute path"
            return ProcessResult.model_validate(result)

        if not os.path.exists(pdf_path):
            result = dict(base_result)
            result["error"] = f"PDF file not found: {pdf_path}"
            return ProcessResult.model_validate(result)

        processing_stem = Path(pdf_path).stem
        pdf_path_to_use = pdf_path
        temp_pdf_to_cleanup: str | None = None
        start_time = time.time()
        full_output: list[str] = []
        last_progress = 0.0

        try:
            (
                processing_stem,
                pdf_path_to_use,
                temp_pdf_to_cleanup,
            ) = _resolve_safe_filename(pdf_path, self.output_dir)

            if temp_pdf_to_cleanup is not None:
                shutil.copy2(pdf_path, pdf_path_to_use)

            command = self._build_command(
                pdf_path=pdf_path_to_use,
                method=method,
                lang=lang,
                formula=formula,
                table=table,
                start=start,
                end=end,
            )

            if self.verbose:
                logger.info("Running MinerU command: %s", " ".join(command))

            if self._on_progress is not None:
                try:
                    self._on_progress(1.0, "處理中: 初始化 MinerU CLI")
                    last_progress = 1.0
                except Exception as callback_error:
                    logger.warning(
                        "Progress callback raised error: %s",
                        callback_error,
                    )

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                text=True,
            )

            if process.stdout is None:
                raise RuntimeError("Unable to read MinerU stdout stream")

            for output_line in process.stdout:
                line = output_line.strip()
                if not line:
                    continue

                full_output.append(line)

                parsed = _parse_progress_line(line)
                if parsed is not None and self._on_progress is not None:
                    progress_percent, progress_message = parsed
                    if progress_percent < last_progress:
                        progress_percent = last_progress
                    else:
                        last_progress = progress_percent
                    try:
                        self._on_progress(progress_percent, progress_message)
                    except Exception as callback_error:
                        logger.warning(
                            "Progress callback raised error: %s",
                            callback_error,
                        )

                if self.verbose:
                    logger.debug(line)

            return_code = process.wait()
            processing_time = time.time() - start_time
            stdout = "\n".join(full_output)

            if return_code != 0:
                result = dict(base_result)
                result["processing_time"] = processing_time
                result["stdout"] = stdout
                result["error"] = (
                    "MinerU execution failed "
                    f"with return code {return_code}"
                )
                result["returncode"] = return_code
                return ProcessResult.model_validate(result)

            output_files = self._find_output_files(
                output_dir=self.output_dir,
                stem=processing_stem,
                method=method,
            )
            result = {
                "success": True,
                "output_path": self.output_dir,
                "output_file_paths": output_files,
                "processing_time": processing_time,
                "stdout": stdout,
                "error": "",
                "returncode": return_code,
            }

            if self._on_progress is not None and last_progress < 100.0:
                try:
                    self._on_progress(100.0, "處理完成")
                except Exception as callback_error:
                    logger.warning(
                        "Progress callback raised error: %s",
                        callback_error,
                    )

            return ProcessResult.model_validate(result)
        except FileNotFoundError as error:
            result = dict(base_result)
            result["processing_time"] = time.time() - start_time
            result["stdout"] = "\n".join(full_output)
            result["error"] = f"MinerU CLI not found: {error}"
            return ProcessResult.model_validate(result)
        except Exception as error:
            result = dict(base_result)
            result["processing_time"] = time.time() - start_time
            result["stdout"] = "\n".join(full_output)
            result["error"] = str(error)
            return ProcessResult.model_validate(result)
        finally:
            if temp_pdf_to_cleanup and os.path.exists(temp_pdf_to_cleanup):
                try:
                    os.remove(temp_pdf_to_cleanup)
                except OSError as cleanup_error:
                    logger.warning(
                        "Failed to clean temporary file %s: %s",
                        temp_pdf_to_cleanup,
                        cleanup_error,
                    )
