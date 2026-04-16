import os
import shutil
import sys
from pathlib import Path


APP_NAME = "AutoClicker"
IS_FROZEN = getattr(sys, "frozen", False)
BUNDLED_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA") or APP_DIR) / APP_NAME
    if IS_FROZEN
    else APP_DIR
)


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def bundled_path(*parts: str) -> Path:
    return BUNDLED_DIR.joinpath(*parts)


def data_path(*parts: str) -> Path:
    ensure_data_dir()
    return DATA_DIR.joinpath(*parts)


def ensure_seed_file(filename: str) -> Path:
    destination = data_path(filename)
    if destination.exists():
        return destination

    source = bundled_path(filename)
    if source.exists():
        shutil.copyfile(source, destination)
    return destination
