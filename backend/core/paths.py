import os
from pathlib import Path

_APP_NAME = "PDFHelper"


def _resolve_data_dir() -> Path:
    override = os.environ.get("PDFHELPER_DATA_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / _APP_NAME
    # fallback: non-Windows or dev environment
    return Path.home() / ".local" / "share" / _APP_NAME


DATA_DIR: Path = _resolve_data_dir()
MODELS_DIR: Path = DATA_DIR / "models"
