from git import (
    Repo as GitRepo,
    GitCommandError,
    InvalidGitRepositoryError,
    NoSuchPathError,
)

from pathlib import Path
from typing import List
from core.config import BASE_TEMP_DIR

from .models import LocalRepo
from .utils import ensure_base_temp_dir, PathLike
from .exceptions import GitCloneError, GitArchiveError, GitLocalPathError

import shutil
import tempfile
import zipfile
import tarfile

class GitRepo2Pipe:
    """
    Высокоуровневый фасад для работы с репозиторием в трёх режимах:

    - clone(repo, branch)                 — клонирование по URL (GitPython);
    - install_from_archive(archive_path)  — подготовка из локального архива;
    - from_existing_path(path)            — использование уже существующей директории.

    Все методы возвращают LocalRepo, внутри которого есть:
    - root_dir      — корень (временный или реальный);
    - repo_path     — путь к проекту для анализа;
    - logs          — логи шагов;
    - is_temporary  — флаг временности root_dir.
    """

    def __init__(self, default_branch: str = "main") -> None:
        self.default_branch = default_branch

    async def clone(self, repo: str, branch: str | None = None) -> LocalRepo:
        """
        Клонирует указанный git-репозиторий во временную папку (через GitPython)
        и возвращает информацию о нём.

        :param repo: URL репозитория (https/ssh или путь до локального bare/обычного репо).
        :param branch:   Ветка, которую нужно клонировать.
        :raises GitCloneError: при любых ошибках клонирования.
        """

        if branch is None:
            branch = self.default_branch

        logs: List[str] = []

        base_temp = ensure_base_temp_dir(BASE_TEMP_DIR)
        temp_root = Path(
            tempfile.mkdtemp(prefix="repo_", dir=base_temp)
        )
        repo_dir = temp_root / "repo"

        logs.append(f"Создаём временную папку: {temp_root}")
        logs.append(f"Клонируем репозиторий {repo!r} (ветка {branch}) в {repo_dir}")

        repo_obj: GitRepo | None = None
        try:
            repo_obj = GitRepo.clone_from(
                repo,
                repo_dir,
                branch=branch,
                depth=1,
            )
            logs.append(f"Репозиторий успешно клонирован в {repo_dir}")
        except GitCommandError as e:
            logs.append("GitPython: ошибка при выполнении clone_from.")
            logs.append(str(e))
            shutil.rmtree(temp_root, ignore_errors=True)
            raise GitCloneError(repository=repo, branch=branch, logs=logs)
        except Exception as e:  # на всякий случай ловим всё, чтобы не оставлять мусор
            logs.append("Непредвиденная ошибка при клонировании репозитория.")
            logs.append(repr(e))
            shutil.rmtree(temp_root, ignore_errors=True)
            raise GitCloneError(repository=repo, branch=branch, logs=logs)
        finally:
            # Явно закрываем repo_obj, чтобы на Windows не оставались залоченные файлы
            if repo_obj is not None:
                repo_obj.close()

        return LocalRepo(
            root_dir=temp_root,
            repo_path=repo_dir,
            logs=logs,
            is_temporary=True,
        )

    async def install_from_archive(self, archive_path: PathLike) -> LocalRepo:
        """
        Готовит репозиторий из локального архива (zip или tar-подобные форматы).

        Поддерживаемые форматы: .zip, .tar, .tar.gz, .tgz, .tar.bz2

        :param archive_path: Путь до архива (str или Path).
        :raises GitArchiveError: если архив не найден, формат не поддерживается
                                или распаковка завершилась ошибкой.
        """
        logs: List[str] = []

        archive = Path(archive_path)
        logs.append(f"Используем архив: {archive}")

        if not archive.exists():
            logs.append("Ошибка: архив не найден.")
            raise GitArchiveError(archive_path=str(archive), logs=logs)
        if not archive.is_file():
            logs.append("Ошибка: указанный путь не является файлом архива.")
            raise GitArchiveError(archive_path=str(archive), logs=logs)

        base_temp = ensure_base_temp_dir(BASE_TEMP_DIR)
        temp_root = Path(
            tempfile.mkdtemp(prefix="archive_", dir=base_temp)
        )
        repo_dir = temp_root / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        logs.append(f"Создаём временную папку для архива: {temp_root}")
        logs.append(f"Распаковываем архив в {repo_dir}")

        name_lower = archive.name.lower()

        try:
            if name_lower.endswith(".zip"):
                logs.append("Определён формат архива: zip")
                with zipfile.ZipFile(archive, "r") as zf:
                    zf.extractall(repo_dir)
            elif (
                name_lower.endswith(".tar")
                or name_lower.endswith(".tar.gz")
                or name_lower.endswith(".tgz")
                or name_lower.endswith(".tar.bz2")
            ):
                logs.append("Определён формат архива: tar")
                with tarfile.open(archive, "r:*") as tf:
                    tf.extractall(repo_dir)
            else:
                logs.append(
                    "Неизвестный формат архива. Поддерживаются: "
                    ".zip, .tar, .tar.gz, .tgz, .tar.bz2"
                )
                shutil.rmtree(temp_root, ignore_errors=True)
                raise GitArchiveError(archive_path=str(archive), logs=logs)
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            logs.append(f"Ошибка при распаковке архива: {e}")
            shutil.rmtree(temp_root, ignore_errors=True)
            raise GitArchiveError(archive_path=str(archive), logs=logs)
        except Exception as e:
            logs.append(f"Непредвиденная ошибка при работе с архивом: {e!r}")
            shutil.rmtree(temp_root, ignore_errors=True)
            raise GitArchiveError(archive_path=str(archive), logs=logs)

        logs.append(f"Архив успешно распакован в {repo_dir}")

        return LocalRepo(
            root_dir=temp_root,
            repo_path=repo_dir,
            logs=logs,
            is_temporary=True,
        )

    async def from_existing_path(self, path: PathLike) -> LocalRepo:
        """
        Использует уже существующую директорию как корень репозитория/проекта.
        Ничего не копирует и не клонирует, просто валидирует путь и собирает логи.

        :param path: Путь до уже распакованного репозитория/проекта.
        :raises GitLocalPathError: если путь не существует или не является директорией.
        """
        logs: List[str] = []

        repo_path = Path(path)
        logs.append(f"Используем существующий путь как репозиторий: {repo_path}")

        if not repo_path.exists():
            logs.append("Ошибка: указанный путь не существует.")
            raise GitLocalPathError(path=str(repo_path), logs=logs)
        if not repo_path.is_dir():
            logs.append("Ошибка: указанный путь не является директорией.")
            raise GitLocalPathError(path=str(repo_path), logs=logs)

        git_dir = repo_path / ".git"
        if git_dir.exists():
            # Есть .git — попробуем аккуратно открыть как git-репозиторий
            try:
                repo_obj = GitRepo(repo_path)
                logs.append("Обнаружена директория .git — путь является git-репозиторием.")
                repo_obj.close()
            except (InvalidGitRepositoryError, NoSuchPathError):
                logs.append(
                    "Найдена директория .git, но GitPython считает репозиторий некорректным. "
                    "Используем как обычную папку проекта."
                )
            except Exception as e:
                logs.append(
                    f"Непредвиденная ошибка при проверке git-репозитория: {e!r}. "
                    "Продолжаем как с обычной директорией."
                )
        else:
            # Это как раз твой кейс: распакованный архив с кодом без .git
            logs.append(
                "В директории нет .git — используем её как обычную папку проекта "
                "(это нормально для архивов и экспортированных исходников)."
            )

        # Важно: is_temporary = False — cleanup() не будет удалять реальный проект.
        return LocalRepo(
            root_dir=repo_path,
            repo_path=repo_path,
            logs=logs,
            is_temporary=False,
        )
