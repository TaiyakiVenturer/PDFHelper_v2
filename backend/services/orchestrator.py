from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from datetime import timezone
import json
import logging
import os
from pathlib import Path
import shutil
import time
import hashlib
import re
from typing import Callable
from typing import Generator

from schemas.response import ErrorCategory
from schemas.response import ErrorMessage
from schemas.response import DeleteResponse
from schemas.response import FileStatusResponse
from schemas.response import IndexResultMessage
from schemas.response import ParseResultMessage
from schemas.response import QueryDeltaMessage
from schemas.response import QueryDoneMessage
from schemas.response import QuerySourceItem
from schemas.response import QuerySourcesMessage
from schemas.response import TranslateResultMessage
from services.error_utils import build_error_message
from services.error_utils import classify_error_message
from services.parser import content_merger
from services.parser.mineru import MinerUCLIWrapper
from services.reconstructor.md_reconstructor import MarkdownReconstructor
from services.translator.model_translator import ModelTranslator
from services.llm.llama_factory import LlamaFactory
from services.llm.llama_factory import build_query_messages
from services.indexer.chroma_service import ChromaService
from services.indexer.chunker import StructureAwareChunker
from services.indexer.embedder import BgeM3Embedder


logger = logging.getLogger(__name__)




class PipelineOrchestrator:
    def __init__(self, data_dir: str) -> None:
        if not os.path.isabs(data_dir):
            raise ValueError("data_dir must be an absolute path")

        data_dir_abs = os.path.abspath(data_dir)

        self._data_dir = data_dir_abs
        self._pdf_dir = os.path.join(self._data_dir, "pdfs")
        self._artifacts_dir = os.path.join(self._data_dir, "artifacts")
        self._chroma_dir = os.path.join(self._data_dir, "chroma")

        os.makedirs(self._pdf_dir, exist_ok=True)
        os.makedirs(self._artifacts_dir, exist_ok=True)
        os.makedirs(self._chroma_dir, exist_ok=True)

        self._mineru_wrapper = MinerUCLIWrapper(output_dir=self._artifacts_dir)
        self._llm_factory = LlamaFactory()
        self._translate_service = ModelTranslator(llm_factory=self._llm_factory)
        self._md_reconstructor = MarkdownReconstructor()
        self._embedder = BgeM3Embedder()
        self._chroma_service = ChromaService(persist_dir=self._chroma_dir)
        
        self._busy_stage: str | None = None

    @staticmethod
    def _resolve_collection_name(stem: str, artifacts_dir: str) -> str:
        projected_output = os.path.join(
            os.path.abspath(artifacts_dir),
            stem,
            "auto",
            f"{stem}_content_list.json",
        )
        has_illegal_chars = re.match(r"^[a-zA-Z0-9.-]+$", stem) is None
        name_too_short = len(stem) < 3
        name_too_long = len(stem) > 50
        path_too_long = len(projected_output) > 250
        if not any([has_illegal_chars, name_too_short, name_too_long, path_too_long]):
            return stem
        hash_part = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
        return f"doc_{hash_part}"

    def _find_pdf_by_collection_name(self, collection_name: str) -> Path:
        for entry in Path(self._pdf_dir).iterdir():
            if entry.is_file() and entry.suffix.lower() == ".pdf":
                if self._resolve_collection_name(entry.stem, self._artifacts_dir) == collection_name:
                    return entry
        raise FileNotFoundError(f"No PDF found for collection: {collection_name}")

    @staticmethod
    def _derive_collection_stem(json_path: str) -> str:
        stem = Path(json_path).stem
        for suffix in (
            "_translated",
            "_content_list_merged",
            "_content_list_v2",
            "_content_list",
        ):
            if stem.endswith(suffix):
                return stem.removesuffix(suffix)
        return stem

    @staticmethod
    def _save_translate_checkpoint(
        progress_path: Path,
        output_path: Path,
        translated_items: list[content_merger.MinerUItem],
        source_data: list,
        next_index: int,
        history_slots: list[dict[str, str] | None],
        history_cursor: int,
        src_lang: str,
        tgt_lang: str,
        source_file: str,
        created_at: str,
        translated_count: int,
        skipped_count: int,
    ) -> None:
        partial_output = [asdict(item) for item in translated_items]
        partial_output.extend(source_data[next_index:])
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(partial_output, f, ensure_ascii=False, indent=2)

        progress_data = {
            "source_file": source_file,
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "total_items": len(source_data),
            "next_index": next_index,
            "translated_item_count": len(translated_items),
            "history_slots": history_slots,
            "history_cursor": history_cursor,
            "translated_count": translated_count,
            "skipped_count": skipped_count,
            "created_at": created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with progress_path.open("w", encoding="utf-8") as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _noop_progress(_percent: float, _message: str) -> None:
        return None

    @classmethod
    def _resolve_progress_callback(
        cls,
        on_progress: Callable[[float, str], None] | None,
    ) -> Callable[[float, str], None]:
        if on_progress is not None:
            return on_progress
        return cls._noop_progress

    @staticmethod
    def _normalize_int(raw: object, default: int = 0) -> int:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _acquire_stage(self, stage_name: str) -> str | None:
        if self._busy_stage is not None:
            return f"Another stage is busy: {self._busy_stage}"
        self._busy_stage = stage_name
        return None

    def _release_stage(self) -> None:
        self._busy_stage = None

    def run_parse(
        self,
        collection_name: str,
        method: str,
        lang: str,
        formula: bool,
        table: bool,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> ParseResultMessage:
        progress_callback = self._resolve_progress_callback(on_progress)
        start_time = time.time()
        busy_msg = self._acquire_stage("parse")
        if busy_msg is not None:
            return ParseResultMessage(
                success=False,
                processing_time=0.0,
                error=busy_msg,
                error_code="REQ_PARSE_STAGE_BUSY",
                error_category=ErrorCategory.REQUEST,
                retryable=True,
            )

        try:
            try:
                pdf_path_obj = self._find_pdf_by_collection_name(collection_name)
            except FileNotFoundError as not_found:
                return ParseResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error=str(not_found),
                    error_code="INP_PARSE_PDF_NOT_FOUND",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )
            pdf_path = str(pdf_path_obj)

            process_result = self._mineru_wrapper.process(
                pdf_path=pdf_path,
                method=method,
                lang=lang,
                formula=formula,
                table=table,
                on_progress=progress_callback,
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

            try:
                self._md_reconstructor.reconstruct(
                    merged_json_path,
                    use_translated=False,
                )
            except Exception as reconstruct_error:
                logger.warning(
                    "Markdown reconstruction failed for merged json %s: %s",
                    merged_json_path,
                    reconstruct_error,
                )

            return ParseResultMessage(
                success=True,
                collection_name=collection_name,
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
        finally:
            self._release_stage()

    def run_translate(
        self,
        collection_name: str,
        method: str,
        src_lang: str,
        tgt_lang: str,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> TranslateResultMessage:
        progress_callback = self._resolve_progress_callback(on_progress)
        start_time = time.time()
        busy_msg = self._acquire_stage("translate")
        if busy_msg is not None:
            return TranslateResultMessage(
                success=False,
                processing_time=0.0,
                error=busy_msg,
                error_code="REQ_TRANSLATE_STAGE_BUSY",
                error_category=ErrorCategory.REQUEST,
                retryable=True,
            )

        try:
            source_path = (
                Path(self._artifacts_dir)
                / collection_name
                / method
                / f"{collection_name}_content_list_merged.json"
            )
            if not source_path.exists():
                return TranslateResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error=f"Merged JSON not found for {collection_name}/{method}. Has parsing been run?",
                    error_code="INP_TRANSLATE_FILE_NOT_FOUND",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )
            json_path = str(source_path)

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

            if len(source_data) == 0:
                return TranslateResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error="Input json contains no content items",
                    error_code="INP_TRANSLATE_EMPTY_CONTENT",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )

            translated_json_path = source_path.with_name(f"{collection_name}_translated.json")
            progress_path = translated_json_path.with_name(
                f"{collection_name}_translate_progress.json"
            )

            translated_items: list[content_merger.MinerUItem] = []
            translated_count = 0
            skipped_count = 0
            history_slots: list[dict[str, str] | None] = [None] * 5
            history_cursor = 0
            start_index = 0
            created_at = datetime.now(timezone.utc).isoformat()

            if progress_path.exists():
                try:
                    prog = json.loads(progress_path.read_text(encoding="utf-8"))
                    params_match = (
                        prog.get("src_lang") == src_lang
                        and prog.get("tgt_lang") == tgt_lang
                        and prog.get("total_items") == len(source_data)
                        and prog.get("source_file") == json_path
                    )
                    if params_match and translated_json_path.exists():
                        start_index = prog["next_index"]
                        history_slots = prog["history_slots"]
                        history_cursor = prog["history_cursor"]
                        translated_count = prog.get("translated_count", 0)
                        skipped_count = prog.get("skipped_count", 0)
                        created_at = prog.get("created_at", created_at)
                        translated_item_count = prog.get("translated_item_count", start_index)
                        partial_data = json.loads(
                            translated_json_path.read_text(encoding="utf-8")
                        )
                        translated_items = [
                            content_merger.MinerUItem.from_dict(d)
                            for d in partial_data[:translated_item_count]
                            if isinstance(d, dict)
                        ]
                        progress_callback(
                            round(start_index / len(source_data) * 100, 2),
                            "從斷點繼續翻譯",
                        )
                    else:
                        progress_path.unlink(missing_ok=True)
                except Exception as checkpoint_error:
                    logger.warning(
                        "Failed to load translation checkpoint: %s", checkpoint_error
                    )
                    progress_path.unlink(missing_ok=True)

            _CHECKPOINT_EVERY = 5

            with self._translate_service as translator:
                for index in range(start_index, len(source_data)):
                    raw_item = source_data[index]
                    if not isinstance(raw_item, dict):
                        skipped_count += 1
                        continue

                    item = content_merger.MinerUItem.from_dict(raw_item)
                    if item.text.strip() == "":
                        skipped_count += 1
                        item.translated_text = ""
                    else:
                        history_snapshot = [
                            entry for entry in history_slots if entry is not None
                        ]
                        translated_text = translator.translate_paragraph(
                            item.text,
                            src_lang,
                            tgt_lang,
                            history=history_snapshot,
                        )
                        item.translated_text = translated_text
                        if translated_text.strip() == "":
                            skipped_count += 1
                        else:
                            translated_count += 1
                            history_slots[history_cursor] = {
                                "source_text": item.text,
                                "translated_text": translated_text,
                            }
                            history_cursor = (history_cursor + 1) % len(history_slots)
                    translated_items.append(item)

                    progress = round(((index + 1) / len(source_data)) * 100.0, 2)
                    progress_callback(progress, "翻譯中")

                    if (index + 1) % _CHECKPOINT_EVERY == 0:
                        self._save_translate_checkpoint(
                            progress_path=progress_path,
                            output_path=translated_json_path,
                            translated_items=translated_items,
                            source_data=source_data,
                            next_index=index + 1,
                            history_slots=history_slots,
                            history_cursor=history_cursor,
                            src_lang=src_lang,
                            tgt_lang=tgt_lang,
                            source_file=json_path,
                            created_at=created_at,
                            translated_count=translated_count,
                            skipped_count=skipped_count,
                        )

            with translated_json_path.open("w", encoding="utf-8") as output_file:
                json.dump(
                    [asdict(item) for item in translated_items],
                    output_file,
                    ensure_ascii=False,
                    indent=2,
                )
            progress_path.unlink(missing_ok=True)

            try:
                self._md_reconstructor.reconstruct(
                    str(translated_json_path.resolve()),
                    use_translated=True,
                )
            except Exception as reconstruct_error:
                logger.warning(
                    "Markdown reconstruction failed for translated json %s: %s",
                    translated_json_path,
                    reconstruct_error,
                )

            return TranslateResultMessage(
                success=True,
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
        finally:
            self._release_stage()

    def run_index(
        self,
        collection_name: str,
        method: str,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> IndexResultMessage:
        progress_callback = self._resolve_progress_callback(on_progress)
        start_time = time.time()
        busy_msg = self._acquire_stage("index")
        if busy_msg is not None:
            return IndexResultMessage(
                success=False,
                processing_time=0.0,
                error=busy_msg,
                error_code="REQ_INDEX_STAGE_BUSY",
                error_category=ErrorCategory.REQUEST,
                retryable=True,
            )

        try:
            source_path = (
                Path(self._artifacts_dir)
                / collection_name
                / method
                / f"{collection_name}_content_list_merged.json"
            )
            if not source_path.exists():
                return IndexResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error=f"Merged JSON not found for {collection_name}/{method}. Has parsing been run?",
                    error_code="INP_INDEX_FILE_NOT_FOUND",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )

            with source_path.open("r", encoding="utf-8") as source_file:
                source_data = json.load(source_file)

            if not isinstance(source_data, list):
                return IndexResultMessage(
                    success=False,
                    processing_time=time.time() - start_time,
                    error="Input json must be a list of content items",
                    error_code="INP_INDEX_INVALID_JSON_STRUCTURE",
                    error_category=ErrorCategory.INPUT,
                    retryable=False,
                )

            items: list[content_merger.MinerUItem] = []
            for raw_item in source_data:
                if not isinstance(raw_item, dict):
                    continue
                items.append(content_merger.MinerUItem.from_dict(raw_item))

            progress_callback(5.0, "切分 chunk 中")

            chunker = StructureAwareChunker()
            chunks = chunker.chunk(items)

            if len(chunks) == 0:
                return IndexResultMessage(
                    success=False,
                    chunk_count=0,
                    processing_time=time.time() - start_time,
                    error="No chunks generated from input content",
                    error_code="PIPE_INDEX_NO_CHUNKS",
                    error_category=ErrorCategory.PIPELINE,
                    retryable=False,
                )

            progress_callback(15.0, "載入 embedding 模型")

            self._embedder.load()

            progress_callback(25.0, "計算 embedding")
            texts_to_embed = [chunk.embedding_text for chunk in chunks]

            def _on_embed_batch(done: int, total: int) -> None:
                pct = 25.0 + (done / total) * 58.0
                progress_callback(round(pct, 1), f"計算 embedding ({done}/{total} 批次)")

            embeddings = self._embedder.embed_texts(texts_to_embed, on_batch=_on_embed_batch)

            progress_callback(85.0, "寫入 ChromaDB")

            collection = self._chroma_service.create_collection(collection_name)
            self._chroma_service.add_chunks(collection, chunks, embeddings)

            progress_callback(100.0, "索引完成")

            return IndexResultMessage(
                success=True,
                chunk_count=len(chunks),
                processing_time=time.time() - start_time,
                error="",
                error_code=None,
                error_category=None,
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
        finally:
            self._release_stage()

    def run_query(
        self,
        question: str,
        collection_name: str,
        top_k: int = 5,
        history: list[dict[str, str]] | None = None,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> Generator[
        QuerySourcesMessage | QueryDeltaMessage | QueryDoneMessage | ErrorMessage,
        None,
        None,
    ]:
        progress_callback = self._resolve_progress_callback(on_progress)
        start_time = time.time()
        busy_msg = self._acquire_stage("query")
        if busy_msg is not None:
            yield build_error_message(
                stage="query",
                code="REQ_QUERY_STAGE_BUSY",
                category="request",
                message=busy_msg,
                retryable=True,
            )
            return

        try:
            if question.strip() == "":
                yield build_error_message(
                    stage="query",
                    code="INP_QUERY_EMPTY_QUESTION",
                    category="input",
                    message="question must not be empty",
                    retryable=False,
                )
                return

            if not self._chroma_service.collection_exists(collection_name):
                yield build_error_message(
                    stage="query",
                    message=f"collection not found: {collection_name}",
                )
                return

            progress_callback(10.0, "問題向量化中")
            self._embedder.load()
            query_vectors = self._embedder.embed_texts([question])
            if len(query_vectors) == 0:
                raise RuntimeError("query embedding result is empty")

            query_vector = query_vectors[0]
            collection = self._chroma_service.get_collection(collection_name)

            progress_callback(20.0, "檢索相關段落中")
            query_result = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            meta_rows = query_result.get("metadatas") or [[]]
            doc_rows = query_result.get("documents") or [[]]
            metadatas = meta_rows[0] if meta_rows else []
            documents = doc_rows[0] if doc_rows else []

            source_items: list[QuerySourceItem] = []
            for index, metadata in enumerate(metadatas):
                current_metadata = metadata if isinstance(metadata, dict) else {}
                fallback_doc = ""
                if index < len(documents):
                    fallback_doc = str(documents[index] or "")

                source_items.append(
                    QuerySourceItem(
                        page_idx=self._normalize_int(current_metadata.get("page_idx"), default=0),
                        type_v2=str(current_metadata.get("type_v2", "") or ""),
                        text=str(current_metadata.get("text", "") or fallback_doc),
                        section_title=str(current_metadata.get("section_title", "") or ""),
                        chunk_id=str(current_metadata.get("chunk_id", "") or ""),
                    )
                )

            yield QuerySourcesMessage(sources=source_items)

            progress_callback(35.0, "組裝提示詞")
            messages = build_query_messages(
                question=question,
                sources=source_items,
                history=history,
            )

            progress_callback(45.0, "生成回答中")
            answer_parts: list[str] = []
            with self._llm_factory as llm:
                stream = llm.create_chat_completion_stream(
                    messages=messages,
                    max_tokens=800,
                    temperature=0.3,
                )
                for chunk in stream:
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    first_choice = choices[0] if isinstance(choices[0], dict) else {}
                    delta = first_choice.get("delta")
                    if not isinstance(delta, dict):
                        continue
                    delta_text = str(delta.get("content", "") or "")
                    if delta_text == "":
                        continue

                    answer_parts.append(delta_text)
                    yield QueryDeltaMessage(delta=delta_text)

            full_answer = "".join(answer_parts)
            progress_callback(100.0, "回答完成")
            yield QueryDoneMessage(
                answer=full_answer,
                processing_time=time.time() - start_time,
            )
        except Exception as error:
            yield build_error_message(
                stage="query",
                message=str(error),
            )
        finally:
            self._release_stage()

    def list_files(self) -> list[dict[str, str]]:
        pdf_dir = Path(self._pdf_dir)
        allowed_suffixes = {".pdf"}

        files = [
            {
                "pdf_name": entry.name,
                "collection_name": self._resolve_collection_name(entry.stem, self._artifacts_dir),
            }
            for entry in pdf_dir.iterdir()
            if entry.is_file() and entry.suffix.lower() in allowed_suffixes
        ]

        return sorted(files, key=lambda item: item["pdf_name"].lower())

    def upload_file(self, source_path: str) -> dict[str, str]:
        source = Path(source_path)
        if not source.is_absolute():
            raise ValueError("source_path must be an absolute path")

        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        allowed_suffixes = {".pdf"}
        if source.suffix.lower() not in allowed_suffixes:
            raise ValueError("Only PDF files are supported")

        destination = Path(self._pdf_dir) / source.name
        if destination.exists():
            raise FileExistsError(f"Target file already exists: {source.name}")

        shutil.copy2(source, destination)

        return {
            "pdf_name": destination.name,
            "collection_name": self._resolve_collection_name(destination.stem, self._artifacts_dir),
        }

    def delete_file(self, filename: str) -> DeleteResponse:
        if "/" in filename or "\\" in filename:
            raise ValueError("filename must not contain path separators")

        target_path = Path(self._pdf_dir) / filename
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"Original file not found: {filename}")

        target_path.unlink()
        return DeleteResponse(success=True, message=f"Deleted {filename}")

    def get_file_status(self, collection_name: str) -> FileStatusResponse:
        artifacts_base = Path(self._artifacts_dir) / collection_name

        parse_method: str | None = None
        if artifacts_base.exists():
            for method_dir in artifacts_base.iterdir():
                if method_dir.is_dir() and (
                    method_dir / f"{collection_name}_content_list_merged.json"
                ).exists():
                    parse_method = method_dir.name
                    break

        is_parsed = parse_method is not None

        is_translated = False
        if parse_method is not None:
            is_translated = (
                artifacts_base / parse_method / f"{collection_name}_translated.json"
            ).exists()

        is_indexed = False
        try:
            is_indexed = self._chroma_service.collection_exists(collection_name)
        except Exception as error:
            logger.warning("Failed to check collection status for %s: %s", collection_name, error)

        return FileStatusResponse(
            is_parsed=is_parsed,
            parse_method=parse_method,
            is_translated=is_translated,
            is_indexed=is_indexed,
        )

    def delete_artifacts(self, collection_name: str) -> DeleteResponse:
        target_paths = [
            Path(self._artifacts_dir) / collection_name,
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

        try:
            deleted_collection = self._chroma_service.delete_collection(collection_name)
            if deleted_collection:
                deleted_any = True
        except Exception as error:
            errors.append(f"chroma collection {collection_name}: {error}")

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
