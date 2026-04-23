from __future__ import annotations

import os
from typing import Any
from typing import TYPE_CHECKING

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None

if TYPE_CHECKING:  # pragma: no cover
    from services.indexer.chunker import IndexChunk


class ChromaService:
    def __init__(self, persist_dir: str) -> None:
        if not os.path.isabs(persist_dir):
            raise ValueError("persist_dir must be an absolute path")

        self._persist_dir = os.path.abspath(persist_dir)
        os.makedirs(self._persist_dir, exist_ok=True)
        self._client = None
        if chromadb is not None:
            self._client = chromadb.PersistentClient(path=self._persist_dir)

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("chromadb is not installed")
        return self._client

    def create_collection(self, name: str) -> Any:
        client = self._require_client()
        if self.collection_exists(name):
            self.delete_collection(name)

        return client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def get_collection(self, name: str) -> Any:
        client = self._require_client()
        return client.get_collection(name)

    def add_chunks(
        self,
        collection: Any,
        chunks: list["IndexChunk"],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [str(chunk.metadata.get("text", "")) for chunk in chunks]
        metadatas = [self._sanitize_metadata(chunk.metadata) for chunk in chunks]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def delete_collection(self, name: str) -> bool:
        if self._client is None:
            return False

        try:
            self._client.delete_collection(name)
            return True
        except Exception as error:
            if self._is_not_found_error(error):
                return False
            raise

    def collection_exists(self, name: str) -> bool:
        if self._client is None:
            return False
        try:
            self._client.get_collection(name)
            return True
        except Exception as error:
            if self._is_not_found_error(error):
                return False
            raise

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
        sanitized: dict[str, str | int | float | bool] = {}
        for key, value in metadata.items():
            if value is None:
                continue

            if isinstance(value, bool):
                sanitized[key] = value
            elif isinstance(value, (str, int, float)):
                sanitized[key] = value
            else:
                sanitized[key] = str(value)

        return sanitized

    @staticmethod
    def _is_not_found_error(error: Exception) -> bool:
        normalized = str(error).lower()
        return "not found" in normalized or "does not exist" in normalized