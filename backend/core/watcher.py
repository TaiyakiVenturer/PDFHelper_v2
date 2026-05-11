import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


def _watch_parent(parent_pid: int) -> None:
    try:
        import psutil
    except ImportError:
        logger.warning("[watcher] psutil 未安裝，parent 監控停用")
        return
    while True:
        if not psutil.pid_exists(parent_pid):
            logger.info("[watcher] parent PID %d 已消失，後端自動結束", parent_pid)
            os._exit(0)
        time.sleep(2)


def start_parent_watcher() -> None:
    try:
        import psutil
        parent = psutil.Process(os.getppid())
        if parent.name() == "PDFHelper.exe":
            logger.info("[watcher] 由 PDFHelper.exe 啟動，開啟 parent 監控 (PID %d)", parent.pid)
            threading.Thread(target=_watch_parent, args=(parent.pid,), daemon=True).start()
        else:
            logger.info("[watcher] parent 為 %s，跳過監控", parent.name())
    except Exception as e:
        logger.warning("[watcher] 初始化失敗: %s", e)
