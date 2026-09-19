"""git commit/push と GitHub Actions (gh CLI) 経由のビルド取得を行うモジュール。
(roBaリポジトリのgithub_build.pyをベースに、複数ファイルのcommitに対応させたもの)
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


class BuildError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise BuildError(f"コマンド失敗: {' '.join(args)}\n{result.stderr}")
    return result.stdout.strip()


def has_changes(repo_root: Path, relative_paths: list[str]) -> bool:
    out = _run(["git", "status", "--porcelain", "--"] + relative_paths, repo_root)
    return bool(out.strip())


def commit_and_push(repo_root: Path, relative_paths: list[str], message: str, log) -> str:
    """変更をコミットしてpushし、コミットSHAを返す。"""
    log(f"git add {' '.join(relative_paths)}")
    _run(["git", "add"] + relative_paths, repo_root)

    log(f"git commit -m \"{message}\"")
    _run(["git", "commit", "-m", message], repo_root)

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    log(f"git push origin {branch}")
    _run(["git", "push", "origin", branch], repo_root)

    sha = _run(["git", "rev-parse", "HEAD"], repo_root)
    log(f"pushしました (commit {sha[:8]})")
    return sha


def wait_for_run(repo_root: Path, commit_sha: str, log, timeout_sec: int = 900, poll_interval: int = 10):
    """指定コミットに対応するActionsの実行が完了するまで待ち、run情報を返す。"""
    deadline = time.time() + timeout_sec
    log("GitHub Actionsの実行を確認中...")

    while time.time() < deadline:
        out = _run(
            ["gh", "run", "list", "--limit", "20",
             "--json", "databaseId,headSha,status,conclusion,displayTitle,url"],
            repo_root,
        )
        runs = json.loads(out)
        match = next((r for r in runs if r.get("headSha") == commit_sha), None)
        if match:
            run_id = match["databaseId"]
            status = match["status"]
            log(f"run #{run_id} status={status}")
            if status == "completed":
                if match.get("conclusion") != "success":
                    raise BuildError(
                        f"ビルド失敗 (conclusion={match.get('conclusion')}): {match.get('url')}"
                    )
                return match
        else:
            log("該当のrunがまだ見つかりません。待機します...")
        time.sleep(poll_interval)

    raise BuildError("タイムアウト: GitHub Actionsの完了を確認できませんでした")


def download_artifacts(repo_root: Path, run_id: int, dest_dir: Path, log) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    log(f"gh run download {run_id} -D {dest_dir}")
    _run(["gh", "run", "download", str(run_id), "-D", str(dest_dir)], repo_root)
    return dest_dir


def find_uf2_files(download_dir: Path) -> list[Path]:
    return sorted(download_dir.rglob("*.uf2")) + sorted(download_dir.rglob("*.bin"))
