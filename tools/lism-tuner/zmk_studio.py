"""ZMK Studio を起動するヘルパー。
(roBaリポジトリのzmk_studio.pyと同一実装)

インストール済みならネイティブアプリを、見つからなければWeb版をブラウザで開く。
"""
from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

WEB_URL = "https://zmk.studio/"

_CANDIDATE_PATHS = [
    r"%PROGRAMFILES%\ZMK Studio\zmk-studio.exe",
    r"%PROGRAMFILES%\ZMK Studio\ZMK Studio.exe",
    r"%PROGRAMFILES(X86)%\ZMK Studio\zmk-studio.exe",
    r"%PROGRAMFILES(X86)%\ZMK Studio\ZMK Studio.exe",
    r"%LOCALAPPDATA%\Programs\zmk-studio\zmk-studio.exe",
    r"%LOCALAPPDATA%\Programs\ZMK Studio\zmk-studio.exe",
    r"%LOCALAPPDATA%\Programs\ZMK Studio\ZMK Studio.exe",
    r"%LOCALAPPDATA%\zmk-studio\zmk-studio.exe",
]

_SEARCH_DIRS = [
    r"%PROGRAMFILES%",
    r"%PROGRAMFILES(X86)%",
    r"%LOCALAPPDATA%\Programs",
]


def find_installed_app() -> Path | None:
    for template in _CANDIDATE_PATHS:
        path = Path(os.path.expandvars(template))
        if path.is_file():
            return path

    # 固定パスで見つからない場合、インストールフォルダ名の揺れを許容して探す
    for dir_template in _SEARCH_DIRS:
        base = Path(os.path.expandvars(dir_template))
        if not base.is_dir():
            continue
        for exe in base.glob("*[Zz][Mm][Kk]*[Ss]tudio*/*.exe"):
            if "studio" in exe.name.lower():
                return exe
    return None


def open_zmk_studio(log) -> None:
    app_path = find_installed_app()
    if app_path:
        log(f"ZMK Studio を起動します: {app_path}")
        subprocess.Popen([str(app_path)])
    else:
        log(f"インストール済みのZMK Studioが見つからないため、Web版を開きます: {WEB_URL}")
        webbrowser.open(WEB_URL)
