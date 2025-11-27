from __future__ import annotations

import click
import json
import os
import re
from pathlib import Path
from typing import Iterable, Tuple, List, Dict

from core.models import StackInfo, DockerfileInfo


# Директории, которые игнорируем при обходе репозитория
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
}

# Карта расширений в 4 основных языка кейса
EXT_TO_LANGUAGE: Dict[str, str] = {
    # Python
    ".py": "python",

    # JavaScript / TypeScript → сводим в один стек "javascript"
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",

    # Java / Kotlin → сводим в один стек "java"
    ".java": "java",
    ".kt": "java",

    # Go
    ".go": "go",
}


def _iter_files(base_dir: Path) -> Iterable[Path]:
    """
    Обход файлов репозитория с пропуском служебных и тяжёлых директорий.
    """
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for filename in files:
            yield Path(root) / filename


def _group_project_files(repo_path: Path) -> Dict[str, List[Path]]:
    """
    Сканируем репозиторий и собираем списки ключевых конфигов:
    - Python: requirements.txt, pyproject.toml, Pipfile
    - Node: package.json (+ tsconfig.json)
    - Java/Kotlin: pom.xml, build.gradle(.kts)
    - Go: go.mod
    """
    req_files: List[Path] = []
    pyproject_files: List[Path] = []
    pipfile_files: List[Path] = []
    package_json_files: List[Path] = []
    pom_files: List[Path] = []
    gradle_files: List[Path] = []
    go_mod_files: List[Path] = []
    tsconfig_files: List[Path] = []

    for file_path in _iter_files(repo_path):
        name = file_path.name.lower()
        if name == "requirements.txt":
            req_files.append(file_path)
        elif name == "pyproject.toml":
            pyproject_files.append(file_path)
        elif name == "pipfile":
            pipfile_files.append(file_path)
        elif name == "package.json":
            package_json_files.append(file_path)
        elif name == "pom.xml":
            pom_files.append(file_path)
        elif name in ("build.gradle", "build.gradle.kts"):
            gradle_files.append(file_path)
        elif name == "go.mod":
            go_mod_files.append(file_path)
        elif name == "tsconfig.json":
            tsconfig_files.append(file_path)

    return {
        "requirements": req_files,
        "pyproject": pyproject_files,
        "pipfile": pipfile_files,
        "package_json": package_json_files,
        "pom": pom_files,
        "gradle": gradle_files,
        "go_mod": go_mod_files,
        "tsconfig": tsconfig_files,
    }


def _detect_dockerfiles(repo_path: Path) -> List[DockerfileInfo]:
    """
    Находит Dockerfile'ы в репозитории и строит по ним DockerfileInfo.
    Простая эвристика:
      - Dockerfile в корне => context=".", name="app"
      - Dockerfile в подпапке (services/api/Dockerfile) => context="services/api", name="api"
      - Dockerfile.* => name из суффикса (Dockerfile.ui -> ui)
    """
    dockerfiles: List[DockerfileInfo] = []

    for p in repo_path.rglob("Dockerfile*"):
        # пропустим .git и прочее мусорное
        if ".git" in p.parts:
            continue

        rel = p.relative_to(repo_path)

        # Определяем context (директория с Dockerfile)
        context_path = rel.parent
        context_str = str(context_path) if str(context_path) != "." else "."

        # Определяем логическое имя
        if p.name == "Dockerfile":
            name = context_path.name or "app"
        else:
            # Dockerfile.api -> api, Dockerfile-ui -> ui
            base = p.name
            if base.startswith("Dockerfile"):
                base = base[len("Dockerfile"):]
            base = base.lstrip("._-")
            name = base or context_path.name or "app"

        dockerfiles.append(
            DockerfileInfo(
                path=str(rel),
                context=context_str,
                name=name,
            )
        )

    return dockerfiles

def _detect_languages(repo_path: Path, logs: List[str]) -> Tuple[List[str], Dict[str, int]]:
    """
    Определяем языки по расширениям файлов + считаем количество файлов на язык.
    """
    click.echo("Определяем языки проекта...")
    language_counts: Dict[str, int] = {}

    for file_path in _iter_files(repo_path):
        lang = EXT_TO_LANGUAGE.get(file_path.suffix.lower())
        if not lang:
            continue
        language_counts[lang] = language_counts.get(lang, 0) + 1

    langs = sorted(language_counts.keys())
    logs.append(f"Определены языки проекта: {langs or 'не обнаружены'} (counts={language_counts})")
    click.echo(f"Определены языки проекта: {langs or 'не обнаружены'} (counts={language_counts})")
    return langs, language_counts


def _detect_package_managers(repo_path: Path, logs: List[str]) -> List[str]:
    """
    Определяем менеджеры пакетов по наличию конфигов во всём репозитории.
    """
    click.echo("Определяем менеджеры пакетов...")
    pm: set[str] = set()
    grouped = _group_project_files(repo_path)

    # Python
    if grouped["requirements"]:
        pm.add("pip")
    if grouped["pyproject"]:
        pm.add("poetry")
    if grouped["pipfile"]:
        pm.add("pipenv")

    # Node.js
    if grouped["package_json"]:
        for pkg in grouped["package_json"]:
            parent = pkg.parent
            if (parent / "yarn.lock").exists():
                pm.add("yarn")
            elif (parent / "pnpm-lock.yaml").exists():
                pm.add("pnpm")
            elif (parent / "package-lock.json").exists():
                pm.add("npm")
            else:
                pm.add("npm")

    # Java/Kotlin
    if grouped["pom"]:
        pm.add("maven")
    if grouped["gradle"]:
        pm.add("gradle")

    # Go
    if grouped["go_mod"]:
        pm.add("go-mod")

    managers = sorted(pm)
    logs.append(f"Обнаружены менеджеры пакетов: {managers or 'не обнаружены'}")
    click.echo(f"Обнаружены менеджеры пакетов: {managers or 'не обнаружены'}")
    return managers


def _detect_frameworks(
    repo_path: Path,
    languages: List[str],
    logs: List[str],
) -> List[str]:
    """
    Грубый детект фреймворков по конфигам и зависимостям.
    """
    click.echo("Грубый детект фреймворков...")
    frameworks: set[str] = set()
    grouped = _group_project_files(repo_path)

    # --- Python: fastapi / flask / django ---
    python_files = grouped["requirements"] + grouped["pyproject"]
    for f in python_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        if "fastapi" in content:
            frameworks.add("fastapi")
        if "flask" in content:
            frameworks.add("flask")
        if "django" in content:
            frameworks.add("django")

    # --- Node.js: vue / react / angular / express / nestjs ---
    for pkg in grouped["package_json"]:
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        deps = data.get("dependencies", {}) or {}
        dev_deps = data.get("devDependencies", {}) or {}
        all_names = {name.lower() for name in {**deps, **dev_deps}.keys()}

        if "vue" in all_names or any(name.startswith("@vue/") for name in all_names):
            frameworks.add("vue")
        if "react" in all_names or any(name.startswith("react-") for name in all_names):
            frameworks.add("react")
        if "@angular/core" in all_names:
            frameworks.add("angular")
        if "express" in all_names:
            frameworks.add("express")
        if "nestjs" in all_names or "@nestjs/core" in all_names:
            frameworks.add("nestjs")

    # --- Java/Kotlin: spring ---
    for pom in grouped["pom"]:
        try:
            content = pom.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if "spring-boot-starter" in content or "org.springframework" in content:
            frameworks.add("spring")

    for gf in grouped["gradle"]:
        try:
            content = gf.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if "spring-boot-starter" in content or "org.springframework" in content:
            frameworks.add("spring")

    fw = sorted(frameworks)
    logs.append(f"Обнаружены фреймворки: {fw or 'не обнаружены'}")
    click.echo(f"Обнаружены фреймворки: {fw or 'не обнаружены'}")
    return fw


# ---------- Python: зависимости и версия ----------

def _parse_python_requirements_file(path: Path) -> Dict[str, str]:
    """
    Примитивный разбор requirements.txt → {package: version} по строгим ограничениям (==).
    """
    deps: Dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return deps

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ";" in line:
            line = line.split(";", 1)[0].strip()

        m = re.match(
            r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?\s*([<>=!~]+)\s*([^\s]+)",
            line,
        )
        if not m:
            continue
        name, op, ver = m.group(1), m.group(2), m.group(3)
        name = name.lower()
        if op == "==" or name not in deps:
            deps[name] = ver
    return deps


def _detect_python_version(repo_path: Path) -> str | None:
    """
    Пытаемся найти версию Python:
    - .python-version
    - pyproject.toml (requires-python / python = "^3.11")
    - Dockerfile (образ python:3.11-...)
    """
    pyver_file = repo_path / ".python-version"
    if pyver_file.exists():
        try:
            v = pyver_file.read_text(encoding="utf-8", errors="ignore").strip()
            if v:
                return v
        except Exception:
            pass

    grouped = _group_project_files(repo_path)

    for f in grouped["pyproject"]:
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for line in lines:
            s = line.strip()
            if s.lower().startswith("requires-python") and "=" in s:
                rhs = s.split("=", 1)[1].strip().strip("\"'")
                return rhs
            if s.lower().startswith("python") and "=" in s:
                rhs = s.split("=", 1)[1].strip().strip("\"'")
                return rhs

    for file_path in _iter_files(repo_path):
        name = file_path.name.lower()
        if name != "dockerfile" and not name.startswith("dockerfile."):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        m = re.search(r"from\s+python:([\w.\-]+)", content, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return None


def _collect_python(repo_path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
    """
    Собираем Python-зависимости и версию Python/фреймворков.
    """
    grouped = _group_project_files(repo_path)

    dependencies: Dict[str, Dict[str, str]] = {}
    language_versions: Dict[str, str] = {}
    framework_versions: Dict[str, str] = {}

    py_deps: Dict[str, str] = {}
    for f in grouped["requirements"]:
        file_deps = _parse_python_requirements_file(f)
        for name, ver in file_deps.items():
            if name not in py_deps:
                py_deps[name] = ver
    if py_deps:
        dependencies["python"] = py_deps

    pyver = _detect_python_version(repo_path)
    if pyver:
        language_versions["python"] = pyver

    if "python" in dependencies:
        deps_lower = {k.lower(): v for k, v in dependencies["python"].items()}
        for fw in ("fastapi", "django", "flask"):
            if fw in deps_lower:
                framework_versions[fw] = deps_lower[fw]

    return dependencies, language_versions, framework_versions


# ---------- Node/JS/TS ----------

def _collect_node(repo_path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
    """
    Собираем зависимости Node/JS/TS и версию Node из package.json.
    """
    grouped = _group_project_files(repo_path)

    dependencies: Dict[str, Dict[str, str]] = {}
    language_versions: Dict[str, str] = {}
    framework_versions: Dict[str, str] = {}

    node_deps: Dict[str, str] = {}

    for pkg in grouped["package_json"]:
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        for section in ("dependencies", "devDependencies"):
            section_deps = data.get(section) or {}
            for name, ver in section_deps.items():
                key = name.lower()
                if key not in node_deps:
                    node_deps[key] = str(ver)

        engines = data.get("engines") or {}
        node_engine = engines.get("node")
        if node_engine and "node" not in language_versions:
            language_versions["node"] = str(node_engine)

    if node_deps:
        dependencies["node"] = node_deps

        for fw_key, fw_name in [
            ("vue", "vue"),
            ("react", "react"),
            ("@angular/core", "angular"),
            ("express", "express"),
            ("nestjs", "nestjs"),
            ("@nestjs/core", "nestjs"),
            ("typescript", "typescript"),
        ]:
            if fw_key in node_deps and fw_name not in framework_versions:
                framework_versions[fw_name] = node_deps[fw_key]

    return dependencies, language_versions, framework_versions


# ---------- Go ----------

def _collect_go(repo_path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
    """
    Собираем зависимости и версию Go из go.mod.
    """
    grouped = _group_project_files(repo_path)

    dependencies: Dict[str, Dict[str, str]] = {}
    language_versions: Dict[str, str] = {}
    framework_versions: Dict[str, str] = {}

    go_mod_files = grouped["go_mod"]
    if not go_mod_files:
        return dependencies, language_versions, framework_versions

    go_deps: Dict[str, str] = {}

    for gm in go_mod_files:
        try:
            lines = gm.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        in_block = False
        for line in lines:
            s = line.strip()
            if not s or s.startswith("//"):
                continue

            if s.startswith("go "):
                parts = s.split()
                if len(parts) >= 2 and "go" not in language_versions:
                    language_versions["go"] = parts[1]
                continue

            if s.startswith("require ("):
                in_block = True
                continue
            if in_block:
                if s.startswith(")"):
                    in_block = False
                    continue
                parts = s.split()
                if len(parts) >= 2:
                    mod, ver = parts[0], parts[1]
                    go_deps[mod] = ver
                continue

            if s.startswith("require "):
                parts = s.split()
                if len(parts) >= 3:
                    mod, ver = parts[1], parts[2]
                    go_deps[mod] = ver

    if go_deps:
        dependencies["go"] = go_deps

        for mod, ver in go_deps.items():
            lower = mod.lower()
            if "gin-gonic/gin" in lower and "gin" not in framework_versions:
                framework_versions["gin"] = ver
            if "labstack/echo" in lower and "echo" not in framework_versions:
                framework_versions["echo"] = ver
            if "gofiber/fiber" in lower and "fiber" not in framework_versions:
                framework_versions["fiber"] = ver

    return dependencies, language_versions, framework_versions


# ---------- Java / Kotlin ----------

def _collect_java_kotlin(repo_path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
    """
    Собираем зависимости Java/Kotlin из pom.xml и build.gradle(.kts),
    версию Java/Kotlin и версии популярных фреймворков (spring, junit, ktor).
    """
    grouped = _group_project_files(repo_path)

    dependencies: Dict[str, Dict[str, str]] = {}
    language_versions: Dict[str, str] = {}
    framework_versions: Dict[str, str] = {}

    java_deps: Dict[str, str] = {}

    # pom.xml
    for pom in grouped["pom"]:
        try:
            content = pom.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        m = re.search(
            r"<maven\.compiler\.source>\s*([^<]+)</maven\.compiler\.source>",
            content,
        )
        if m and "java" not in language_versions:
            language_versions["java"] = m.group(1).strip()

        for dep_match in re.finditer(
            r"<dependency>\s*"
            r"<groupId>\s*([^<]+)</groupId>\s*"
            r"<artifactId>\s*([^<]+)</artifactId>\s*"
            r"(?:<version>\s*([^<]+)</version>)?",
            content,
            re.DOTALL,
        ):
            group_id = dep_match.group(1).strip()
            artifact_id = dep_match.group(2).strip()
            version = (dep_match.group(3) or "").strip()

            key = f"{group_id}:{artifact_id}"
            if key not in java_deps:
                java_deps[key] = version

            if group_id == "org.springframework.boot" and artifact_id.startswith("spring-boot-starter"):
                if "spring" not in framework_versions and version:
                    framework_versions["spring"] = version

            if "junit" in group_id.lower() or "junit" in artifact_id.lower():
                if "junit" not in framework_versions and version:
                    framework_versions["junit"] = version

            if group_id.startswith("org.jetbrains.kotlin"):
                if "kotlin" not in language_versions and version:
                    language_versions["kotlin"] = version

    # build.gradle / build.gradle.kts
    for gf in grouped["gradle"]:
        try:
            content = gf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        m = re.search(
            r"sourceCompatibility\s*=\s*['\"]([^'\"]+)['\"]",
            content,
        )
        if m and "java" not in language_versions:
            language_versions["java"] = m.group(1).strip()

        for dep_match in re.finditer(
            r"(?:implementation|api|compileOnly|runtimeOnly|testImplementation)\s+['\"]([^:'\"]+):([^:'\"]+):([^'\"\n]+)['\"]",
            content,
        ):
            group_id = dep_match.group(1).strip()
            artifact_id = dep_match.group(2).strip()
            version = dep_match.group(3).strip()

            key = f"{group_id}:{artifact_id}"
            if key not in java_deps:
                java_deps[key] = version

            if group_id == "org.springframework.boot" and artifact_id.startswith("spring-boot-starter"):
                if "spring" not in framework_versions and version:
                    framework_versions["spring"] = version

            if "junit" in group_id.lower() or "junit" in artifact_id.lower():
                if "junit" not in framework_versions and version:
                    framework_versions["junit"] = version

            if group_id.startswith("org.jetbrains.kotlin"):
                if "kotlin" not in language_versions and version:
                    language_versions["kotlin"] = version

            if group_id.startswith("io.ktor"):
                if "ktor" not in framework_versions and version:
                    framework_versions["ktor"] = version

    if java_deps:
        dependencies["java"] = java_deps

    return dependencies, language_versions, framework_versions


def _detect_dependencies_and_versions(
    repo_path: Path,
    logs: List[str],
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
    """
    Обобщённая сборка зависимостей и версий:
    Python + Node/JS/TS + Go + Java/Kotlin.
    """
    deps_all: Dict[str, Dict[str, str]] = {}
    lang_versions_all: Dict[str, str] = {}
    fw_versions_all: Dict[str, str] = {}

    for collector in (_collect_python, _collect_node, _collect_go, _collect_java_kotlin):
        deps, lang_ver, fw_ver = collector(repo_path)

        for eco, pkgs in deps.items():
            dst = deps_all.setdefault(eco, {})
            dst.update(pkgs)

        for k, v in lang_ver.items():
            if k not in lang_versions_all:
                lang_versions_all[k] = v

        for k, v in fw_ver.items():
            if k not in fw_versions_all:
                fw_versions_all[k] = v

    if deps_all:
        short = {eco: list(pkgs.keys())[:5] for eco, pkgs in deps_all.items()}
        logs.append(f"Обнаружены зависимости (усечённый список): {short}")
        click.echo(f"Обнаружены зависимости (усечённый список): {short}")
    else:
        logs.append("Зависимости по конфигурационным файлам не найдены.")
        click.echo("Зависимости по конфигурационным файлам не найдены.")

    if lang_versions_all:
        logs.append(f"Обнаружены версии языков/рантаймов: {lang_versions_all}")
        click.echo(f"Обнаружены версии языков/рантаймов: {lang_versions_all}")

    if fw_versions_all:
        logs.append(f"Обнаружены версии фреймворков/инструментов: {fw_versions_all}")
        click.echo(f"Обнаружены версии фреймворков/инструментов: {fw_versions_all}")

    return deps_all, lang_versions_all, fw_versions_all


def _detect_deploy_artifacts(repo_path: Path, logs: List[str]) -> Tuple[bool, bool, bool]:
    """
    Определяем, есть ли Dockerfile, docker-compose и (очень грубо) k8s-манифесты.
    """
    has_dockerfile = False
    has_docker_compose = False
    has_k8s = False

    click.echo("Определяем Docker/k8s-артефакты...")
    for file_path in _iter_files(repo_path):
        name = file_path.name.lower()
        if name == "dockerfile" or name.startswith("dockerfile."):
            has_dockerfile = True
        if name in {"docker-compose.yml", "docker-compose.yaml"}:
            has_docker_compose = True
        if name.endswith((".yml", ".yaml")) and any(
            part in {"k8s", "kubernetes", "manifests"} for part in file_path.parts
        ):
            has_k8s = True

    logs.append(
        f"Dockerfile: {has_dockerfile}, docker-compose: {has_docker_compose}, k8s-манифесты: {has_k8s}"
    )
    click.echo(
        f"Dockerfile: {has_dockerfile}, docker-compose: {has_docker_compose}, k8s-манифесты: {has_k8s}"
    )
    return has_dockerfile, has_docker_compose, has_k8s


def analyze_stack(repo_path: Path) -> Tuple[StackInfo, List[str], List[str]]:
    """
    Основная функция анализа репозитория.
    Возвращает StackInfo + лог и варнинги.
    """
    click.echo(f"Начинаем анализ репозитория: {repo_path}")

    logs: List[str] = [f"Начинаем анализ репозитория: {repo_path}"]
    warnings: List[str] = []

    if not repo_path.exists():
        click.echo("Путь к репозиторию не существует, анализ невозможен", err=True)
        warnings.append("Путь к репозиторию не существует, анализ невозможен.")
        logs.append("Путь к репозиторию не найден.")
        return StackInfo(), logs, warnings

    # 1. Языки + количество файлов
    languages, lang_counts = _detect_languages(repo_path, logs)

    # 2. Менеджеры пакетов
    package_managers = _detect_package_managers(repo_path, logs)

    # 3. Фреймворки
    frameworks = _detect_frameworks(repo_path, languages, logs)

    # 4. Docker / docker-compose / k8s
    has_dockerfile, has_docker_compose, has_k8s = _detect_deploy_artifacts(repo_path, logs)

    # 5. Зависимости и версии
    dependencies, language_versions, framework_versions = _detect_dependencies_and_versions(repo_path, logs)

    # 6. Убираем "шумовые" языки (один файл + нет профильного менеджера пакетов)
    filtered_languages = list(languages)
    ECO_PMS: Dict[str, set[str]] = {
        "python": {"pip", "poetry", "pipenv"},
        "javascript": {"npm", "yarn", "pnpm"},
        "java": {"maven", "gradle"},
        "go": {"go-mod"},
    }

    for lang in list(filtered_languages):
        pms_for_lang = ECO_PMS.get(lang)
        if not pms_for_lang:
            continue

        files_count = lang_counts.get(lang, 0)
        has_pm = any(pm in pms_for_lang for pm in package_managers)

        if files_count <= 1 and not has_pm:
            warnings.append(
                f"Обнаружен единичный файл языка {lang} без конфигурации зависимостей — "
                f"считаем его вспомогательным и не включаем в основной стек."
            )
            logs.append(
                f"{lang} исключён из списка языков: файлов={files_count}, "
                f"менеджеры пакетов для этого языка не найдены."
            )
            click.echo(
                f"{lang} исключён из основного стека "
                f"(файлов={files_count}, менеджеры пакетов {sorted(pms_for_lang)} не обнаружены)."
            )
            filtered_languages.remove(lang)

    # Объединяем фреймворки из грубого детекта и из версий
    frameworks_all = sorted(set(frameworks) | set(framework_versions.keys()))

    stack = StackInfo(
        languages=sorted(filtered_languages),
        frameworks=frameworks_all,
        package_managers=package_managers,
        dockerfiles=_detect_dockerfiles(repo_path),
        has_dockerfile=has_dockerfile,
        has_docker_compose=has_docker_compose,
        has_k8s_manifests=has_k8s,
        dependencies=dependencies,
        language_versions=language_versions,
        framework_versions=framework_versions,
    )

    if not filtered_languages:
        warnings.append(
            "Не удалось идентифицировать основной язык проекта. "
            "Пайплайн будет построен по умолчаниям."
        )
        click.echo("Не удалось идентифицировать основной язык проекта")
        click.echo("Пайплайн будет построен по умолчаниям")

    return stack, logs, warnings
