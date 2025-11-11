# updater.py
import io
import os
import sys
import shutil
import zipfile
import tempfile
import subprocess
from pathlib import Path
import urllib.request
import json

GITHUB_USER = "dmiittry"
GITHUB_REPO = "post_app"
GITHUB_BRANCH = "main"

RAW_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.txt"
ZIP_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

APP_DIR = Path(getattr(sys, "_MEIPASS", Path.cwd())).resolve()  # поддержка PyInstaller
EXE_DIR = Path.cwd().resolve()  # где лежит exe/скрипт
LOCAL_VERSION_FILE = EXE_DIR / "version.txt"

# какие папки/файлы не трогаем при обновлении
EXCLUDE_NAMES = {
    ".git", "__pycache__", "venv", ".venv",
    "data_cache", "cache", "excel" , # если кэш в папке проекта
}
EXCLUDE_FILES = {
    "settings.json",
}

def _read_text_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return resp.read().decode("utf-8").strip()

def get_local_version() -> str:
    if LOCAL_VERSION_FILE.exists():
        return LOCAL_VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"

def is_newer(v_remote: str, v_local: str) -> bool:
    def parse(v): return [int(x) for x in v.strip().split(".")]
    try:
        return parse(v_remote) > parse(v_local)
    except:
        return v_remote != v_local

def download_zip(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()

def copy_tree(src: Path, dst: Path):
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        # пропускаем исключенные каталоги
        if any(part in EXCLUDE_NAMES for part in rel.parts):
            continue
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f in EXCLUDE_FILES:
                continue
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)

def perform_update(progress_cb=None) -> tuple[bool, str]:
    try:
        if progress_cb: progress_cb("Проверка версии...")
        remote_version = _read_text_url(RAW_VERSION_URL)
        local_version = get_local_version()
        if progress_cb: progress_cb(f"Локальная: {local_version}, удаленная: {remote_version}")

        if not is_newer(remote_version, local_version):
            return False, "Обновлений нет"

        if progress_cb: progress_cb("Скачивание архива...")
        blob = download_zip(ZIP_URL)

        if progress_cb: progress_cb("Распаковка...")
        tmpdir = Path(tempfile.mkdtemp(prefix="update_"))
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            zf.extractall(tmpdir)

        # В архиве верхняя папка формата repo-branch
        root_candidates = list(tmpdir.iterdir())
        if not root_candidates:
            return False, "Архив пустой"
        unpack_root = root_candidates[0]

        if progress_cb: progress_cb("Копирование файлов...")
        copy_tree(unpack_root, EXE_DIR)

        # Обновляем локальную версию
        (EXE_DIR / "version.txt").write_text(remote_version, encoding="utf-8")

        if progress_cb: progress_cb("Готово. Перезапуск...")
        # Перезапустим приложение
        try:
            if getattr(sys, "frozen", False):
                exe_path = Path(sys.executable)
                subprocess.Popen([str(exe_path)], cwd=str(EXE_DIR))
            else:
                # запущено из python
                py = shutil.which("python") or shutil.which("python3") or sys.executable
                subprocess.Popen([py, str(EXE_DIR / "main.py")], cwd=str(EXE_DIR))
        except Exception as e:
            pass
        return True, "Обновление установлено"
    except Exception as e:
        return False, f"Ошибка обновления: {e}"
