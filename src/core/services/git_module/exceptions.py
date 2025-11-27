from typing import List, Optional

from exception import CLIException


class GitExceptions(CLIException):
    """
    Базовое исключение для работы с Git/репозиториями.

    Дополнительно хранит логи (steps), накопленные во время операции.
    """

    def __init__(
        self,
        *args,
        description: str = "Something happend when work with Git",
        logs: Optional[List[str]] = None,
    ) -> None:
        super().__init__(*args, description=description)
        self.logs: List[str] = logs or []


class GitCloneError(GitExceptions):
    """
    Ошибка при клонировании удалённого репозитория.
    """

    def __init__(
        self,
        repository: str,
        branch: str,
        logs: Optional[List[str]] = None,
        *args,
    ) -> None:
        description = f"Error to clone repository {repository} in branch {branch}"
        super().__init__(*args, description=description, logs=logs)
        self.repository = repository
        self.branch = branch


class GitArchiveError(GitExceptions):
    """
    Ошибка при работе с архивом (zip/tar) репозитория.
    """

    def __init__(
        self,
        archive_path: str,
        logs: Optional[List[str]] = None,
        *args,
    ) -> None:
        description = f"Error to extract or use archive {archive_path}"
        super().__init__(*args, description=description, logs=logs)
        self.archive_path = archive_path


class GitLocalPathError(GitExceptions):
    """
    Ошибка при использовании локального пути до репозитория/проекта.
    """

    def __init__(
        self,
        path: str,
        logs: Optional[List[str]] = None,
        *args,
    ) -> None:
        description = f"Error to use local repository path {path}"
        super().__init__(*args, description=description, logs=logs)
        self.path = path
