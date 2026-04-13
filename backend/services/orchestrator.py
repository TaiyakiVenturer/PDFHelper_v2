from __future__ import annotations

from collections import deque
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import time
from typing import Callable

from schemas.response import ErrorCategory
from schemas.response import DeleteResponse
from schemas.response import FileStatusResponse
from schemas.response import IndexResultMessage
from schemas.response import ParseResultMessage
from schemas.response import QueryResponse
from schemas.response import TranslateResultMessage
from services.error_utils import classify_error_message
from services.parser import content_merger
from services.parser.mineru import MinerUCLIWrapper
from services.translator.model_translator import ModelTranslator


class PipelineOrchestrator:
    def __init__(self, data_dir: str) -> None:
        if not os.path.isabs(data_dir):
            raise ValueError("data_dir must be an absolute path")

        data_dir_abs = os.path.abspath(data_dir)

        self._data_dir = data_dir_abs
        self._pdf_dir = os.path.join(self._data_dir, "pdfs")
        self._mineru_output_dir = os.path.join(self._data_dir, "mineru_outputs")
        self._translated_dir = os.path.join(self._data_dir, "translated")
        self._chroma_dir = os.path.join(self._data_dir, "chroma")

        os.makedirs(self._pdf_dir, exist_ok=True)
        os.makedirs(self._mineru_output_dir, exist_ok=True)
        os.makedirs(self._translated_dir, exist_ok=True)
        os.makedirs(self._chroma_dir, exist_ok=True)

        self._mineru_wrapper = MinerUCLIWrapper(output_dir=self._mineru_output_dir)
        self._translate_service = ModelTranslator()
        
        # TODO: initialize markdown reconstructor service instance.
        self._md_reconstructor = None
        # TODO: initialize ChromaDB indexer/retrieval service instance.
        self._chroma_service = None

    @staticmethod
    def _derive_collection_stem(json_path: str) -> str:
        stem = Path(json_path).stem
        for suffix in (
            "_content_list_merged",
            "_content_list_v2",
            "_content_list",
        ):
            if stem.endswith(suffix):
                return stem.removesuffix(suffix)
        return stem

    def run_parse(
        self,
        pdf_path: str,
        method: str,
        lang: str,
        formula: bool,
        table: bool,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> ParseResultMessage:
        start_time = time.time()

        process_result = self._mineru_wrapper.process(
            pdf_path=pdf_path,
            method=method,
            lang=lang,
            formula=formula,
            table=table,
            on_progress=on_progress,
        )

        if not process_result.success:
            error_code, error_category, retryable = classify_error_message(
                "parse",
                process_result.error,
            )
            return ParseResultMessage(
                success=False,
                processing_time=time.time() - start_time,
                error=process_result.error,
                error_code=error_code,
                error_category=error_category,
                retryable=retryable,
            )

        try:
            output_paths = process_result.output_file_paths
            if output_paths.json_v1_path is None or output_paths.json_v2_path is None:
                missing_versions: list[str] = []
                if output_paths.json_v1_path is None:
                    missing_versions.append("v1")
                if output_paths.json_v2_path is None:
                    missing_versions.append("v2")
                return ParseResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error=(
                        "MinerU output json path is missing: "
                        + ", ".join(missing_versions)
                    ),
                    error_code="PIPE_PARSE_OUTPUT_MISSING",
                    error_category=ErrorCategory.PIPELINE,
                    retryable=False,
                )

            v1_path = output_paths.json_v1_path
            v2_path = output_paths.json_v2_path
            stem = self._derive_collection_stem(v2_path)
            merged_json_path = str(Path(v2_path).with_name(f"{stem}_content_list_merged.json"))
            merged_items = content_merger.load_and_merge(v1_path, v2_path)

            with open(merged_json_path, "w", encoding="utf-8") as merged_file:
                json.dump(
                    [asdict(item) for item in merged_items],
                    merged_file,
                    ensure_ascii=False,
                    indent=2,
                )

            # TODO: call md_reconstructor.reconstruct(merged_json_path, mode="origin").
            # Expected input: merged_json_path and "origin" mode.
            # Expected output: absolute path to original markdown file.

            image_dir: str | None = None
            if process_result.output_file_paths.image_path:
                image_dir = str(
                    Path(process_result.output_file_paths.image_path[0]).resolve().parent
                )

            return ParseResultMessage(
                success=True,
                markdown_path=None,
                json_path=merged_json_path,
                image_dir=image_dir,
                processing_time=time.time() - start_time,
                error="",
                error_code=None,
                error_category=None,
                retryable=False,
            )
        except Exception as error:
            error_message = str(error)
            error_code, error_category, retryable = classify_error_message(
                "parse",
                error_message,
            )
            return ParseResultMessage(
                success=False,
                processing_time=time.time() - start_time,
                error=error_message,
                error_code=error_code,
                error_category=error_category,
                retryable=retryable,
            )

    def run_translate(
        self,
        json_path: str,
        src_lang: str,
        tgt_lang: str,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> TranslateResultMessage:
        start_time = time.time()
        try:
            if not os.path.isabs(json_path):
                return TranslateResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error="json_path must be an absolute path",
                    error_code="INP_TRANSLATE_ABSOLUTE_PATH_REQUIRED",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )

            source_path = Path(json_path)
            if not source_path.exists():
                return TranslateResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error=f"Input json file not found: {json_path}",
                    error_code="INP_TRANSLATE_FILE_NOT_FOUND",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )

            with source_path.open("r", encoding="utf-8") as source_file:
                source_data = json.load(source_file)

            if not isinstance(source_data, list):
                return TranslateResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error="Input json must be a list of content items",
                    error_code="INP_TRANSLATE_INVALID_JSON_STRUCTURE",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )

            translated_items: list[object] = []
            translated_count = 0
            skipped_count = 0
            total_items = len(source_data)
            translation_history: deque[dict[str, str]] = deque(maxlen=5)

            with self._translate_service as translator:
                for index, item in enumerate(source_data):
                    if not isinstance(item, dict):
                        skipped_count += 1
                        translated_items.append(item)
                    else:
                        translated_item = dict(item)
                        text = str(translated_item.get("text", "") or "")
                        if text.strip() == "":
                            skipped_count += 1
                            translated_item["translated_text"] = ""
                        else:
                            translated_text = translator.translate_paragraph(
                                text,
                                src_lang,
                                tgt_lang,
                                history=list(translation_history),
                            )
                            translated_item["translated_text"] = translated_text
                            if translated_text.strip() == "":
                                skipped_count += 1
                            else:
                                translated_count += 1
                                translation_history.append(
                                    {
                                        "source_text": text,
                                        "translated_text": translated_text,
                                    }
                                )
                        translated_items.append(translated_item)

                    if on_progress is not None and total_items > 0:
                        progress = round(((index + 1) / total_items) * 100.0, 2)
                        on_progress(progress, "翻譯中")

            if on_progress is not None and total_items == 0:
                on_progress(100.0, "翻譯完成")

            collection_stem = self._derive_collection_stem(json_path)
            translated_json_path = (
                Path(self._translated_dir) / f"{collection_stem}_translated.json"
            )
            with translated_json_path.open("w", encoding="utf-8") as output_file:
                json.dump(
                    translated_items,
                    output_file,
                    ensure_ascii=False,
                    indent=2,
                )

            # TODO: call md_reconstructor.reconstruct(translated_json_path, mode="translated").
            # Expected input: translated JSON path and "translated" mode.
            # Expected output: absolute path to translated markdown file.

            translated_path = str(translated_json_path.resolve())

            return TranslateResultMessage(
                success=True,
                translated_path=translated_path,
                translated_count=translated_count,
                skipped_count=skipped_count,
                processing_time=time.time() - start_time,
                error="",
                error_code=None,
                error_category=None,
                retryable=False,
            )
        except Exception as error:
            error_message = str(error)
            error_code, error_category, retryable = classify_error_message(
                "translate",
                error_message,
            )
            return TranslateResultMessage(
                success=False,
                processing_time=time.time() - start_time,
                error=error_message,
                error_code=error_code,
                error_category=error_category,
                retryable=retryable,
            )

    def run_index(
        self,
        json_path: str,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> IndexResultMessage:
        start_time = time.time()
        try:
            # TODO: call chunker with structure-aware token chunking.
            # Expected input: json_path, on_progress.
            # Expected output: chunk list.

            # TODO: call ChromaDB indexer with BAAI/bge-m3 embeddings.
            # Expected input: chunk list.
            # Expected output: collection_name and chunk_count.

            if on_progress is not None:
                on_progress(100.0, "索引流程尚未實作")

            return IndexResultMessage(
                success=False,
                collection_name=None,
                chunk_count=0,
                processing_time=time.time() - start_time,
                error="Index pipeline is not implemented yet",
                error_code="NIM_INDEX_NOT_IMPLEMENTED",
                error_category=ErrorCategory.NOT_IMPLEMENTED,
                retryable=False,
            )
        except Exception as error:
            error_message = str(error)
            error_code, error_category, retryable = classify_error_message(
                "index",
                error_message,
            )
            return IndexResultMessage(
                success=False,
                processing_time=time.time() - start_time,
                error=error_message,
                error_code=error_code,
                error_category=error_category,
                retryable=retryable,
            )

    def run_query(self, question: str, collection_name: str, top_k: int = 10) -> QueryResponse:
        # TODO: call ChromaDB retrieval.query(collection_name, question, top_k).
        # Expected output: list[QuerySource].

        # TODO: call LLM with retrieved chunks and question.
        # Expected output: answer string.
        return QueryResponse(answer="", sources=[])

    def get_file_status(self, collection_name: str, method: str = "auto") -> FileStatusResponse:
        parsed_dir = Path(self._mineru_output_dir) / collection_name / method
        parsed_indicators = [
            parsed_dir / f"{collection_name}_content_list_merged.json",
            parsed_dir / f"{collection_name}_content_list_v2.json",
            parsed_dir / f"{collection_name}_content_list.json",
        ]

        translated_candidates = [
            Path(self._translated_dir) / f"{collection_name}_translated.md",
            Path(self._translated_dir) / f"{collection_name}_translated.json",
            Path(self._translated_dir) / f"{collection_name}.md",
            Path(self._translated_dir) / f"{collection_name}.json",
        ]

        translated_path: str | None = None
        for path in translated_candidates:
            if path.exists():
                translated_path = str(path.resolve())
                break

        collection_dir = Path(self._chroma_dir) / collection_name
        has_indexed = collection_dir.exists() and any(collection_dir.iterdir())
        has_parsed = any(path.exists() for path in parsed_indicators)

        if has_indexed:
            return FileStatusResponse(
                stage="indexed",
                translated_path=translated_path,
                collection_name=collection_name,
            )

        if translated_path is not None:
            return FileStatusResponse(
                stage="translated",
                translated_path=translated_path,
                collection_name=None,
            )

        if has_parsed:
            return FileStatusResponse(
                stage="parsed",
                translated_path=None,
                collection_name=None,
            )

        return FileStatusResponse(stage="none", translated_path=None, collection_name=None)

    def delete_file(self, collection_name: str) -> DeleteResponse:
        target_paths = [
            Path(self._pdf_dir) / f"{collection_name}.pdf",
            Path(self._mineru_output_dir) / collection_name,
            Path(self._translated_dir) / f"{collection_name}_translated.md",
            Path(self._translated_dir) / f"{collection_name}_translated.json",
            Path(self._translated_dir) / f"{collection_name}.md",
            Path(self._translated_dir) / f"{collection_name}.json",
            Path(self._translated_dir) / collection_name,
        ]

        deleted_any = False
        errors: list[str] = []

        for path in target_paths:
            if not path.exists():
                continue

            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted_any = True
            except OSError as error:
                errors.append(f"{path}: {error}")

        # TODO: call ChromaDB delete_collection(collection_name).

        if errors:
            return DeleteResponse(success=False, message="; ".join(errors))

        if deleted_any:
            return DeleteResponse(
                success=True,
                message=f"Deleted artifacts for collection: {collection_name}",
            )

        return DeleteResponse(
            success=True,
            message=f"No artifacts found for collection: {collection_name}",
        )


def create_orchestrator(data_dir: str) -> PipelineOrchestrator:
    return PipelineOrchestrator(data_dir=data_dir)
