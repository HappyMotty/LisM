"""LisM トラックボール設定ツール

トラックボール(PAW3222)の設定をGUIで編集し、
GitHubへpush -> GitHub Actionsでビルド -> UF2をダウンロード -> 書き込み、
までを行う。LisM/ZMK設定リポジトリ専用の個人用ツール
(roBaリポジトリのroba-tunerと同じ設計)。

roBaと異なり、CPIなどはKconfigではなくdevicetreeのプロパティ
(snippets/trackball-central/trackball.overlay)で設定されるため、
overlay_props.OverlayStore で編集する。ポインタ加速(roBaから移植した
自作Input Processor)の設定のみKconfig(config/lism_right.conf)。
"""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import flash
import github_build
import zmk_studio
from kconfig import TUNABLES, KconfigFile
from overlay_props import OverlayStore

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF_RELATIVE = "config/lism_right.conf"
OVERLAY_RELATIVE = "snippets/trackball-central/trackball.overlay"
TARGET_RELATIVES = [CONF_RELATIVE, OVERLAY_RELATIVE]

# ZMK Studio対応版(キーマップ編集も可能)を書き込み対象にする
UF2_MATCH = "lism_right_central_trackball_studio"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LisM トラックボール設定ツール")
        self.geometry("640x820")

        self.cpi_var = tk.StringVar()
        self.force_awake_var = tk.BooleanVar()
        self.invert_x_var = tk.BooleanVar()
        self.invert_y_var = tk.BooleanVar()
        self.scroll_divisor_var = tk.StringVar()
        self.accel_bool_vars: dict[str, tk.BooleanVar] = {}
        self.accel_int_vars: dict[str, tk.StringVar] = {}
        self.last_download_dir: Path | None = None

        self._build_widgets()
        self.load_from_file()

    # ---------- UI構築 ----------
    def _build_widgets(self) -> None:
        header = ttk.Label(
            self, text=f"編集対象: {CONF_RELATIVE} / {OVERLAY_RELATIVE}", font=("", 9)
        )
        header.pack(fill="x", padx=10, pady=(10, 0))

        canvas = tk.Canvas(self, borderwidth=0)
        frame = ttk.Frame(canvas)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(frame, text="■ トラックボール(PAW3222)", font=("", 10, "bold")).pack(
            fill="x", pady=(0, 4)
        )

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="CPI (感度)", width=28).pack(side="left")
        ttk.Entry(row, textvariable=self.cpi_var, width=10).pack(side="left")
        ttk.Label(row, text="(608〜4826, 38刻み推奨)", foreground="#888").pack(side="left")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Checkbutton(row, text="Force Awakeモード(常時フル稼働・低消費電力機能を無効化)",
                         variable=self.force_awake_var).pack(side="left")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Checkbutton(row, text="X軸反転", variable=self.invert_x_var).pack(side="left")
        ttk.Checkbutton(row, text="Y軸反転", variable=self.invert_y_var).pack(side="left", padx=10)

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="スクロール分周比", width=28).pack(side="left")
        ttk.Entry(row, textvariable=self.scroll_divisor_var, width=10).pack(side="left")
        ttk.Label(row, text="大きいほどスクロールが遅い", foreground="#888").pack(side="left")

        ttk.Separator(frame).pack(fill="x", pady=10)
        ttk.Label(frame, text="■ ポインタ加速", font=("", 10, "bold")).pack(fill="x", pady=(0, 4))

        for spec in TUNABLES:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=4)
            if spec.kind == "bool":
                var = tk.BooleanVar()
                self.accel_bool_vars[spec.key] = var
                ttk.Checkbutton(row, text=spec.label, variable=var).pack(side="left")
            else:
                ttk.Label(row, text=spec.label, width=28).pack(side="left")
                var = tk.StringVar()
                self.accel_int_vars[spec.key] = var
                ttk.Entry(row, textvariable=var, width=10).pack(side="left")
                ttk.Label(row, text=f"({spec.min_value}〜{spec.max_value})", foreground="#888").pack(side="left")
            if spec.help:
                ttk.Label(frame, text="  " + spec.help, foreground="#666", font=("", 8)).pack(
                    fill="x", pady=(0, 2)
                )

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(btn_row, text="ファイルから読み込み直す", command=self.load_from_file).pack(side="left")
        ttk.Button(btn_row, text="保存してビルド", command=self.save_and_build).pack(side="left", padx=5)
        ttk.Button(btn_row, text="ボードに書き込み", command=self.flash_board).pack(side="left")
        ttk.Button(btn_row, text="ZMK Studioを開く（キーマップ編集）", command=self.open_zmk_studio).pack(
            side="left", padx=5
        )

        self.log_box = scrolledtext.ScrolledText(self, height=12, state="disabled")
        self.log_box.pack(fill="both", expand=False, padx=10, pady=(0, 10))

    def log(self, message: str) -> None:
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _append)

    # ---------- ファイル読み書き ----------
    def load_from_file(self) -> None:
        overlay = OverlayStore(REPO_ROOT / OVERLAY_RELATIVE)
        self.cpi_var.set(str(overlay.get_cpi()))
        self.force_awake_var.set(overlay.get_force_awake())
        invert_x, invert_y = overlay.get_invert()
        self.invert_x_var.set(invert_x)
        self.invert_y_var.set(invert_y)
        self.scroll_divisor_var.set(str(overlay.get_scroll_divisor()))

        kconfig = KconfigFile(REPO_ROOT / CONF_RELATIVE)
        for spec in TUNABLES:
            if spec.kind == "bool":
                self.accel_bool_vars[spec.key].set(kconfig.get_bool(spec.key))
            else:
                value, _ = kconfig.get_int(spec.key, spec.default)
                self.accel_int_vars[spec.key].set(str(value))

        self.log("設定を読み込みました")

    def _read_int(self, var: tk.StringVar, label: str, min_value: int, max_value: int) -> int:
        raw = var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            raise ValueError(f"{label} は整数で入力してください (入力値: {raw!r})")
        if not (min_value <= value <= max_value):
            raise ValueError(f"{label} は {min_value}〜{max_value} の範囲で入力してください")
        return value

    def _apply_all(self, overlay: OverlayStore, kconfig: KconfigFile) -> None:
        cpi = self._read_int(self.cpi_var, "CPI", 608, 4826)
        overlay.set_cpi(cpi)
        overlay.set_force_awake(self.force_awake_var.get())
        overlay.set_invert(self.invert_x_var.get(), self.invert_y_var.get())
        scroll_divisor = self._read_int(self.scroll_divisor_var, "スクロール分周比", 1, 200)
        overlay.set_scroll_divisor(scroll_divisor)

        for spec in TUNABLES:
            if spec.kind == "bool":
                kconfig.set_bool(spec.key, self.accel_bool_vars[spec.key].get())
            else:
                value = self._read_int(self.accel_int_vars[spec.key], spec.label, spec.min_value, spec.max_value)
                kconfig.set_int(spec.key, value)

    # ---------- ボタン動作 ----------
    def save_and_build(self) -> None:
        overlay = OverlayStore(REPO_ROOT / OVERLAY_RELATIVE)
        kconfig = KconfigFile(REPO_ROOT / CONF_RELATIVE)

        try:
            self._apply_all(overlay, kconfig)
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        overlay.save()
        kconfig.save()
        self.log("設定を保存しました")

        if not github_build.has_changes(REPO_ROOT, TARGET_RELATIVES):
            self.log("変更がないため、ビルドはスキップします")
            return

        threading.Thread(target=self._build_worker, daemon=True).start()

    def _build_worker(self) -> None:
        try:
            sha = github_build.commit_and_push(
                REPO_ROOT, TARGET_RELATIVES, "lism-tuner: トラックボール設定を更新", self.log
            )
            run = github_build.wait_for_run(REPO_ROOT, sha, self.log)
            dest = REPO_ROOT / "tools" / "lism-tuner" / "_downloads" / str(run["databaseId"])
            github_build.download_artifacts(REPO_ROOT, run["databaseId"], dest, self.log)
            self.last_download_dir = dest
            uf2_files = github_build.find_uf2_files(dest)
            self.log(f"ビルド完了。取得したファーム: {[p.name for p in uf2_files]}")
            self.log("「ボードに書き込み」ボタンで書き込みができます")
        except Exception as e:  # noqa: BLE001
            self.log(f"エラー: {e}")
            messagebox.showerror("ビルドエラー", str(e))

    def open_zmk_studio(self) -> None:
        zmk_studio.open_zmk_studio(self.log)

    def flash_board(self) -> None:
        if not self.last_download_dir:
            messagebox.showinfo("書き込み", "先に「保存してビルド」を実行してください")
            return

        uf2_files = [p for p in github_build.find_uf2_files(self.last_download_dir) if UF2_MATCH in p.name]
        if not uf2_files:
            messagebox.showerror("書き込み", f"{UF2_MATCH} のファームウェアが見つかりません")
            return

        uf2_path = uf2_files[0]
        self.log(f"書き込み対象: {uf2_path.name}")
        self.log("右側(セントラル/トラックボール側)のリセットボタンを2回押してブートローダーモードにしてください")
        threading.Thread(target=self._flash_worker, args=(uf2_path,), daemon=True).start()

    def _flash_worker(self, uf2_path: Path) -> None:
        import time

        self.log("UF2ドライブの出現を待っています... (最大60秒)")
        drive = None
        for _ in range(60):
            drive = flash.find_uf2_drive()
            if drive:
                break
            time.sleep(1)

        if not drive:
            self.log("ブートローダードライブが見つかりませんでした")
            messagebox.showerror("書き込み", "ブートローダードライブが見つかりませんでした")
            return

        self.log(f"ドライブを検出: {drive}")
        flash.flash(uf2_path, drive)
        self.log("書き込み完了。ボードが自動的に再起動します")


if __name__ == "__main__":
    App().mainloop()
