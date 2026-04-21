from __future__ import annotations

import gc
import logging
from typing import Any

from services.indexer import indexer_config as cfg

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None


logger = logging.getLogger(__name__)


class BgeM3Embedder:
    def __init__(self, batch_size: int = cfg.EMBEDDING_BATCH_SIZE) -> None:
        self.batch_size = batch_size
        self._model: Any | None = None
        self._using_cuda = False

    def load(self) -> None:
        if self._model is not None:
            return

        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers is not installed; cannot load bge-m3"
            )

        device = cfg.EMBEDDING_DEVICE
        if device not in {"cpu", "cuda"}:
            raise ValueError(f"Unsupported embedding device: {device}")

        if device == "cuda" and (torch is None or not torch.cuda.is_available()):
            device = "cpu"
            logger.warning(
                "CUDA is unavailable; BgeM3Embedder falling back to CPU"
            )

        logger.info("BgeM3Embedder loading on device=%s", device)

        self._using_cuda = device == "cuda"
        self._model = SentenceTransformer(cfg.HF_REPO_ID, device=device)

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None

        gc.collect()
        if self._using_cuda and torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

        self._using_cuda = False
        logger.info("BgeM3Embedder unloaded")

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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError(
                "BgeM3Embedder is not loaded; use it inside a with block"
            )

        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        if hasattr(embeddings, "tolist"):
            raw_vectors = embeddings.tolist()
        else:
            raw_vectors = embeddings

        vectors: list[list[float]] = []
        for vector in raw_vectors:
            vectors.append([float(value) for value in vector])

        return vectors