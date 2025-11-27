import os
import stat
from pathlib import Path
from typing import Union


PathLike = Union[str, Path]

def on_rm_error(func, path, exc_info):
    """
    Обработчик ошибок для shutil.rmtree:
    - снимает флаг read-only (частый кейс для .git/objects/pack на Windows),
    - повторно вызывает функцию удаления,
    - если снова не получилось — просто проглатывает (cleanup — best-effort).
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        # Тут можно было бы залогировать, но в тестовом/CLI-режиме достаточно молча игнорировать.
        pass

def ensure_base_temp_dir(path:str) -> Path:
    """
    Гарантирует, что BASE_TEMP_DIR существует, и возвращает его как Path.
    """
    base = Path(path)
    base.mkdir(parents=True, exist_ok=True)
    return base
