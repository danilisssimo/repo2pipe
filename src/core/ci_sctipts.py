# core/ci_scripts.py
from __future__ import annotations

from typing import List, Literal


NodeKind = Literal["lint", "tests", "build", "sonar"]
JavaKind = Literal["tests", "build", "sonar"]
PythonKind = Literal["lint", "tests", "build"]
PythonManager = Literal["pip", "poetry", "pipenv"]
GoKind = Literal["lint", "tests", "build"]


def _normalize_kind(kind: str) -> str:
    """
    Нормализуем суффикс job'а:
    'tests' -> 'test', остальные без изменений.
    """
    if kind == "tests":
        return "test"
    return kind


# =========================
# Node / JavaScript / pnpm
# =========================

def make_node_script(kind: NodeKind) -> List[str]:
    """
    Генерирует script для Node-проектов (pnpm).
    kind:
      - 'lint'  -> pnpm lint
      - 'tests' -> pnpm test
      - 'build' -> pnpm build
      - 'sonar' -> placeholder под запуск sonar-scanner
    """
    normalized = _normalize_kind(kind)
    job_name = f"node_{kind}"

    cmds: List[str] = [
        f"echo 'Job: {job_name}'",
        # pnpm в node:20-alpine нет из коробки -> ставим через corepack или npm
        "corepack enable || npm i -g pnpm",
        "pnpm install",
    ]

    if normalized == "lint":
        cmds.append("pnpm lint || echo 'pnpm lint не настроен — отредактируйте команду'")
    elif normalized == "test":
        cmds.append("pnpm test || echo 'pnpm test не настроен — отредактируйте команду'")
    elif normalized == "build":
        cmds.append("pnpm build || echo 'pnpm build не настроен — отредактируйте команду'")
    elif normalized == "sonar":
        # Не навязываем конкретную команду — просто подсказка
        cmds.append(
            "echo 'TODO: добавьте команду запуска SonarQube для фронтенда (например, npx sonar-scanner ...)'"
        )
    else:
        raise ValueError(f"Unsupported node job kind: {kind}")

    return cmds


# =========
# Java / mvn
# =========

def make_java_script(kind: JavaKind) -> List[str]:
    """
    Генерирует script для Java-проектов.
    Стратегия:
      - если есть ./mvnw, используем его;
      - иначе используем mvn из образа.
    kind:
      - 'tests' -> mvn test
      - 'build' -> mvn package -DskipTests
      - 'sonar' -> mvn verify sonar:sonar
    """
    normalized = _normalize_kind(kind)
    job_name = f"java_{kind}"

    if normalized == "test":
        goal = "test"
        error_hint = "mvn test завершился с ошибкой — отредактируйте pom.xml/профили"
    elif normalized == "build":
        goal = "package -DskipTests"
        error_hint = "mvn package завершился с ошибкой — проверьте pom.xml"
    elif normalized == "sonar":
        goal = "verify sonar:sonar"
        error_hint = (
            "SonarQube не настроен — укажите параметры sonar.* и переменные окружения SONAR_*"
        )
    else:
        raise ValueError(f"Unsupported java job kind: {kind}")

    cmds: List[str] = [
        f"echo 'Job: {job_name}'",
        "[ -f mvnw ] && chmod +x mvnw || echo 'mvnw не найден, используем mvn из образа'",
        f"./mvnw -B {goal} || mvn -B {goal} || echo '{error_hint}'",
    ]
    return cmds


# =====================
# Python (+pip/poetry)
# =====================

def make_python_script(
    kind: PythonKind,
    manager: PythonManager = "pip",
) -> List[str]:
    """
    Генерирует script для Python-проектов.

    manager:
      - 'pip'    -> requirements.txt, pytest/flake8 через pip
      - 'poetry' -> poetry install, poetry run ...
      - 'pipenv' -> pipenv install, pipenv run ...
    kind:
      - 'lint'  -> flake8
      - 'tests' -> pytest
      - 'build' -> python -m build / poetry build / pipenv run python -m build

    Предполагается, что job добавляется ТОЛЬКО если в проекте реально есть
    нужный менеджер (requirements.txt/pyproject.toml/Pipfile).
    """
    normalized = _normalize_kind(kind)
    job_name = f"python_{kind}"

    cmds: List[str] = [f"echo 'Job: {job_name}'"]

    if manager == "pip":
        install_cmd = (
            "python -m pip install -r requirements.txt "
            "|| echo 'requirements.txt не найден — настройте зависимости для Python-проекта'"
        )

        if normalized == "lint":
            cmds.extend(
                [
                    install_cmd,
                    "python -m pip install flake8 || true",
                    "flake8 . || echo 'flake8 завершился с ошибкой — настройте конфиг или зависимости'",
                ]
            )
        elif normalized == "test":
            cmds.extend(
                [
                    install_cmd,
                    "python -m pip install pytest || true",
                    "pytest || echo 'pytest завершился с ошибкой — проверьте тесты и зависимости'",
                ]
            )
        elif normalized == "build":
            cmds.extend(
                [
                    install_cmd,
                    "python -m pip install build || true",
                    "python -m build || echo 'Команда сборки не настроена — отредактируйте build-конфигурацию'",
                ]
            )
        else:
            raise ValueError(f"Unsupported python job kind: {kind}")

    elif manager == "poetry":
        base_install = "poetry install || echo 'poetry install завершился с ошибкой — проверьте pyproject.toml'"

        if normalized == "lint":
            cmds.extend(
                [
                    base_install,
                    "poetry run flake8 . || echo 'flake8 завершился с ошибкой — настройте конфиг или зависимости'",
                ]
            )
        elif normalized == "test":
            cmds.extend(
                [
                    base_install,
                    "poetry run pytest || echo 'pytest завершился с ошибкой — проверьте тесты и зависимости'",
                ]
            )
        elif normalized == "build":
            cmds.extend(
                [
                    base_install,
                    "poetry build || echo 'poetry build завершился с ошибкой — проверьте pyproject.toml'",
                ]
            )
        else:
            raise ValueError(f"Unsupported python job kind: {kind}")

    elif manager == "pipenv":
        base_install = "pipenv install || echo 'pipenv install завершился с ошибкой — проверьте Pipfile'"

        if normalized == "lint":
            cmds.extend(
                [
                    base_install,
                    "pipenv run flake8 . || echo 'flake8 завершился с ошибкой — настройте конфиг или зависимости'",
                ]
            )
        elif normalized == "test":
            cmds.extend(
                [
                    base_install,
                    "pipenv run pytest || echo 'pytest завершился с ошибкой — проверьте тесты и зависимости'",
                ]
            )
        elif normalized == "build":
            cmds.extend(
                [
                    base_install,
                    "pipenv run python -m build || echo 'Команда сборки не настроена — проверьте конфигурацию'",
                ]
            )
        else:
            raise ValueError(f"Unsupported python job kind: {kind}")

    else:
        raise ValueError(f"Unsupported python manager: {manager}")

    return cmds


# ===========
# Go / golang
# ===========
def make_go_script(kind: GoKind) -> List[str]:
    """
    Генерирует script для Go-проектов.
    kind:
      - 'lint'  -> go vet ./...
      - 'tests' -> go test ./...
      - 'build' -> go build ./...
    """
    normalized = _normalize_kind(kind)
    job_name = f"go_{kind}"

    cmds: List[str] = [f"echo 'Job: {job_name}'"]

    if normalized == "lint":
        cmds.append("go vet ./... || echo 'go vet завершился с ошибкой — проверьте код/зависимости'")
    elif normalized == "test":
        cmds.append("go test ./... || echo 'go test завершился с ошибкой — проверьте тесты/зависимости'")
    elif normalized == "build":
        cmds.append("go build ./... || echo 'go build завершился с ошибкой — проверьте main-пакет и зависимости'")
    else:
        raise ValueError(f"Unsupported go job kind: {kind}")

    return cmds
