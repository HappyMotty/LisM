"""UF2ブートローダーのドライブを検出してファームウェアを書き込むモジュール。
(roBaリポジトリのflash.pyと同一実装)
"""
from __future__ import annotations

import shutil
import string
from pathlib import Path


def find_uf2_drive() -> Path | None:
    """INFO_UF2.TXT が存在するドライブ(=UF2ブートローダーモード中のボード)を探す。"""
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:/")
        marker = drive / "INFO_UF2.TXT"
        try:
            if marker.exists():
                return drive
        except OSError:
            continue
    return None


def flash(uf2_path: Path, drive: Path) -> None:
    dest = drive / uf2_path.name
    shutil.copy2(uf2_path, dest)
