import logging
import time

logger = logging.getLogger(__name__)


def _prewarm_one(name: str, fn) -> None:
    t0 = time.perf_counter()
    logger.info("[prewarm] 開始 import %s", name)
    fn()
    logger.info("[prewarm] 完成 import %s (%.2fs)", name, time.perf_counter() - t0)


def prewarm_imports() -> None:
    """在背景執行緒 import 重型套件，暖機 sys.modules 快取。"""
    t_total = time.perf_counter()
    logger.info("[prewarm] 背景套件預熱開始")

    def _torch():
        import torch  # noqa: F401

    def _st():
        from sentence_transformers import SentenceTransformer  # noqa: F401

    def _llama():
        from llama_cpp import Llama  # noqa: F401

    def _hf():
        from huggingface_hub import hf_hub_download  # noqa: F401

    for name, fn in [("torch", _torch), ("sentence-transformers", _st), ("llama-cpp", _llama), ("huggingface-hub", _hf)]:
        try:
            _prewarm_one(name, fn)
        except ImportError:
            logger.warning("[prewarm] %s 未安裝，跳過", name)

    logger.info("[prewarm] 背景套件預熱完成，總耗時 %.2fs", time.perf_counter() - t_total)
