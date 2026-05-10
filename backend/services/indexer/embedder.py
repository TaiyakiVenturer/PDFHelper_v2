from __future__ import annotations

import gc
import logging
import math
import time
from typing import Any
from typing import Callable


logger = logging.getLogger(__name__)


EMBEDDING_BATCH_SIZE = 4
HF_REPO_ID = "BAAI/bge-m3"


class BgeM3Embedder:
    def __init__(self, batch_size: int = EMBEDDING_BATCH_SIZE) -> None:
        self.batch_size = batch_size
        self._model: Any | None = None

    def load(self) -> None:
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed; cannot load bge-m3"
            )

        logger.info("[embedder] 開始載入 bge-m3 (device=cpu)")
        t0 = time.perf_counter()
        self._model = SentenceTransformer(HF_REPO_ID, device="cpu")
        logger.info("[embedder] bge-m3 載入完成 (%.2fs)", time.perf_counter() - t0)

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None

        gc.collect()
        logger.info("[embedder] bge-m3 已卸載")

    def __enter__(self) -> "BgeM3Embedder":
        self.load()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self.unload()
        return False

    def embed_texts(
        self,
        texts: list[str],
        on_batch: Callable[[int, int], None] | None = None,
    ) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError(
                "BgeM3Embedder is not loaded; use it inside a with block"
            )

        if not texts:
            return []

        if on_batch is None:
            embeddings = self._model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            raw_vectors = embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
            return [[float(v) for v in vec] for vec in raw_vectors]

        total_batches = math.ceil(len(texts) / self.batch_size)
        vectors: list[list[float]] = []
        for batch_idx in range(total_batches):
            start = batch_idx * self.batch_size
            batch = texts[start : start + self.batch_size]
            batch_embeddings = self._model.encode(
                batch,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            raw = batch_embeddings.tolist() if hasattr(batch_embeddings, "tolist") else batch_embeddings
            for vec in raw:
                vectors.append([float(v) for v in vec])
            on_batch(batch_idx + 1, total_batches)

        return vectors