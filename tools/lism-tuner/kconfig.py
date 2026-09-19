"""lism_right.conf (Kconfig) の読み書きを行うモジュール。

既知のキー以外の行はそのまま保持し、対象キーの行だけを書き換える。
(roBaリポジトリのkconfig.pyと同じ実装)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_LINE_RE = re.compile(r"^(?P<comment>#\s*)?(?P<key>CONFIG_[A-Z0-9_]+)=(?P<value>.+?)\s*$")


@dataclass
class TunableSpec:
    key: str
    label: str
    kind: str  # "bool" or "int"
    default: int = 0
    min_value: int = 0
    max_value: int = 65535
    help: str = ""


TUNABLES: list[TunableSpec] = [
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_MIN_FACTOR", "ポインタ加速: 低速時倍率(%)", "int",
                default=100, min_value=10, max_value=1000,
                help="ゆっくり動かした時の倍率。100=等倍"),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_MAX_FACTOR", "ポインタ加速: 高速時倍率(%)", "int",
                default=100, min_value=10, max_value=1000,
                help="素早く動かした時の倍率。低速時倍率と同じにすると加速なし"),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MIN", "ポインタ加速: 開始しきい値(count/report)", "int",
                default=3, min_value=0, max_value=200,
                help="この移動量以下では低速時倍率が適用される"),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MAX", "ポインタ加速: 最大到達しきい値(count/report)", "int",
                default=18, min_value=1, max_value=200,
                help="この移動量以上では高速時倍率が適用される(間は線形補間)"),
]


class KconfigFile:
    def __init__(self, path: Path):
        self.path = path
        self.lines: list[str] = path.read_text(encoding="utf-8").splitlines()

    def _find(self, key: str) -> tuple[int, bool, str] | None:
        for i, line in enumerate(self.lines):
            m = _LINE_RE.match(line)
            if m and m.group("key") == key:
                return i, m.group("comment") is not None, m.group("value")
        return None

    def get_bool(self, key: str) -> bool:
        found = self._find(key)
        if not found:
            return False
        _, commented, value = found
        return (not commented) and value == "y"

    def get_int(self, key: str, default: int) -> tuple[int, bool]:
        found = self._find(key)
        if not found:
            return default, False
        _, commented, value = found
        try:
            return int(value), not commented
        except ValueError:
            return default, not commented

    def set_bool(self, key: str, value: bool) -> None:
        found = self._find(key)
        new_line = f"{key}={'y' if value else 'n'}"
        if found:
            i, _, _ = found
            self.lines[i] = new_line
        elif value:
            self.lines.append(new_line)

    def set_int(self, key: str, value: int, enabled: bool = True) -> None:
        found = self._find(key)
        new_line = f"{key}={value}"
        if not enabled:
            new_line = f"# {new_line}"
        if found:
            i, _, _ = found
            self.lines[i] = new_line
        else:
            self.lines.append(new_line)

    def save(self) -> None:
        text = "\n".join(self.lines) + "\n"
        self.path.write_text(text, encoding="utf-8")
