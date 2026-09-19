"""snippets/trackball-central/trackball.overlay 内の
特定プロパティ(res-cpi, force-awake, 軸反転, スクロール分周比)を
読み書きするモジュール。devicetreeの汎用パーサーではなく、
このファイルの既知の行パターンだけを対象にした専用パーサー。
"""
from __future__ import annotations

import re
from pathlib import Path


class OverlayStore:
    def __init__(self, path: Path):
        self.path = path
        self.lines: list[str] = path.read_text(encoding="utf-8").splitlines()

    # ---------- CPI ----------
    def get_cpi(self, default: int = 800) -> int:
        for line in self.lines:
            m = re.search(r"res-cpi\s*=\s*<(\d+)>", line)
            if m:
                return int(m.group(1))
        return default

    def set_cpi(self, value: int) -> None:
        for i, line in enumerate(self.lines):
            if re.search(r"res-cpi\s*=\s*<\d+>", line):
                indent = re.match(r"^(\s*)", line).group(1)
                self.lines[i] = f"{indent}res-cpi = <{value}>;"
                return
        raise ValueError("res-cpi の行が見つかりません")

    # ---------- force-awake ----------
    def get_force_awake(self) -> bool:
        for line in self.lines:
            stripped = line.strip()
            if stripped == "force-awake;":
                return True
            if stripped in ("// force-awake;", "//force-awake;"):
                return False
        return False

    def set_force_awake(self, value: bool) -> None:
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped in ("force-awake;", "// force-awake;", "//force-awake;"):
                indent = re.match(r"^(\s*)", line).group(1)
                self.lines[i] = f"{indent}{'force-awake;' if value else '// force-awake;'}"
                return
        raise ValueError("force-awake の行が見つかりません")

    # ---------- X/Y軸反転 (zip_xy_transform) ----------
    def get_invert(self) -> tuple[bool, bool]:
        for line in self.lines:
            if "zip_xy_transform" in line:
                return "INPUT_TRANSFORM_X_INVERT" in line, "INPUT_TRANSFORM_Y_INVERT" in line
        return False, False

    def set_invert(self, invert_x: bool, invert_y: bool) -> None:
        for i, line in enumerate(self.lines):
            if "zip_xy_transform" in line:
                indent = re.match(r"^(\s*)", line).group(1)
                flags = []
                if invert_x:
                    flags.append("INPUT_TRANSFORM_X_INVERT")
                if invert_y:
                    flags.append("INPUT_TRANSFORM_Y_INVERT")
                if not flags:
                    expr = "0"
                elif len(flags) == 1:
                    expr = flags[0]
                else:
                    expr = f"({' | '.join(flags)})"
                suffix = "," if line.rstrip().endswith(",") else ""
                self.lines[i] = f"{indent}<&zip_xy_transform {expr}>{suffix}"
                return
        raise ValueError("zip_xy_transform の行が見つかりません")

    # ---------- スクロール分周比 (zip_scroll_scaler MUL DIV) ----------
    def get_scroll_divisor(self, default: int = 16) -> int:
        for line in self.lines:
            m = re.search(r"zip_scroll_scaler\s+(\d+)\s+(\d+)", line)
            if m:
                return int(m.group(2))
        return default

    def set_scroll_divisor(self, value: int) -> None:
        for i, line in enumerate(self.lines):
            m = re.search(r"(zip_scroll_scaler\s+\d+\s+)(\d+)", line)
            if m:
                self.lines[i] = line[: m.start(2)] + str(value) + line[m.end(2):]
                return
        raise ValueError("zip_scroll_scaler の行が見つかりません")

    def save(self) -> None:
        text = "\n".join(self.lines) + "\n"
        self.path.write_text(text, encoding="utf-8")
