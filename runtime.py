from __future__ import annotations

import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import psutil


class SingleInstance:
    """Не даёт запустить два процесса бота с одной базой."""

    def __init__(self, lock_path: Path) -> None:
        self.path = lock_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._held = False

    def acquire(self) -> None:
        if self.path.exists():
            try:
                pid = int(self.path.read_text(encoding="utf-8").strip())
                if pid != os.getpid() and psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if "python" in proc.name().lower():
                        raise SystemExit(
                            f"Бот уже запущен (PID {pid}). "
                            "Остановите второй процесс — иначе будут дубли постов."
                        )
            except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        self._held = True

    def release(self) -> None:
        if not self._held or not self.path.exists():
            return
        try:
            if int(self.path.read_text(encoding="utf-8").strip()) == os.getpid():
                self.path.unlink(missing_ok=True)
        except (ValueError, OSError):
            pass
        self._held = False


def backup_database(db_path: Path, keep_days: int = 14) -> str | None:
    if not db_path.exists():
        return None
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"bot-{date.today().isoformat()}.db"
    shutil.copy2(db_path, dest)
    cutoff = datetime.now() - timedelta(days=keep_days)
    for old in backup_dir.glob("bot-*.db"):
        try:
            day = date.fromisoformat(old.stem.removeprefix("bot-"))
            if datetime.combine(day, datetime.min.time()) < cutoff:
                old.unlink(missing_ok=True)
        except ValueError:
            pass
    return dest.name
