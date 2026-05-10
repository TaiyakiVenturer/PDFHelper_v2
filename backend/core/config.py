from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from schemas.config import AppConfig

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = "config.json"


class ConfigService:
    def __init__(self) -> None:
        self._config_path: Path | None = None
        self._cached: AppConfig | None = None
        self._lock = Lock()

    def init(self, data_dir: str) -> None:
        self._config_path = Path(data_dir) / _CONFIG_FILENAME
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._config_path.exists():
            self._write(AppConfig())

    def get_config(self) -> AppConfig:
        with self._lock:
            if self._cached is None:
                self._cached = self._read()
            return self._cached

    def save_config(self, cfg: AppConfig) -> None:
        with self._lock:
            self._write(cfg)
            self._cached = cfg

    def _read(self) -> AppConfig:
        if self._config_path is None or not self._config_path.exists():
            return AppConfig()
        try:
            return AppConfig.model_validate_json(
                self._config_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning("config.json 讀取失敗，使用預設值: %s", exc)
            return AppConfig()

    def _write(self, cfg: AppConfig) -> None:
        if self._config_path is None:
            return
        self._config_path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")


config = ConfigService()
