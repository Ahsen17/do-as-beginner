from pathlib import Path
from typing import Final

APP_NAME: Final[str] = "do_as_beginner"
# src/do_as_beginner/base/constants.py -> parents: [base, do_as_beginner, src, repo root]
BASE_DIR: Final[Path] = Path(__file__).resolve().parents[3]
