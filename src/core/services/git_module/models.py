import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List
from .utils import on_rm_error

@dataclass
class LocalRepo:
    """
    Унифицированный результат подготовки репозитория/проекта.

    root_dir     — корневая папка, в которой лежит репозиторий.
                   Для временных операций — это временная директория.
    repo_path    — путь к самому репозиторию (корень проекта для анализа).
    logs         — текстовые логи шагов подготовки.
    is_temporary — если True, cleanup() удалит root_dir; если False — нет.
    """
    
    root_dir: Path
    repo_path: Path
    logs: List[str]
    is_temporary: bool = True

    def cleanup(self) -> None:
        """
        Удаляет временную папку с репозиторием, если is_temporary = True.
        Для существующих локальных путей (is_temporary = False) ничего не делает.

        На Windows дополнительно обрабатывает read-only файлы (например, .git/objects/pack),
        чтобы rmtree реально удалял всё.
        """
        if self.is_temporary and self.root_dir.exists():
            shutil.rmtree(self.root_dir, onerror=on_rm_error)
