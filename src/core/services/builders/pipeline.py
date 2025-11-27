import click

from typing import List, Tuple

from core.models import StackInfo, PipelineSummary, DockerfileInfo
from model import Pipeline, Job


def _ensure_stage(stages: List[str], stage: str) -> None:
    if stage not in stages:
        stages.append(stage)


def _has_node(stack: StackInfo) -> bool:
    # js/ts или типичные js-фреймворки
    if any(lang in ("javascript", "typescript") for lang in stack.languages):
        return True

    if any(
        fw in ("vue", "react", "angular", "express", "nestjs")
        for fw in stack.frameworks
    ):
        return True

    return False


def _node_pm(stack: StackInfo) -> str:
    # очень грубый выбор менеджера пакетов
    if "yarn" in stack.package_managers:
        return "yarn"
    if "pnpm" in stack.package_managers:
        return "pnpm"
    # по умолчанию npm
    return "npm"


def _append_quality_jobs(
    stack: StackInfo,
    stages: List[str],
    jobs: List[Job],
    logs: List[str],
    warnings: List[str],
) -> None:
    """
    Добавляем stage quality и SonarQube-плейсхолдеры, если стек это позволяет.
    Сейчас покрываем Java (maven) и Node.js-проекты.
    """
    has_java = "java" in getattr(stack, "languages", []) and "maven" in getattr(
        stack, "package_managers", []
    )
    has_node = _has_node(stack)

    if not (has_java or has_node):
        return

    _ensure_stage(stages, "quality")

    # Java + Maven: пример SonarQube-анализа
    if has_java:
        jobs.append(
            Job(
                name="java_sonar",
                stage="quality",
                image="maven:3.9-eclipse-temurin-17",
                script=[
                    "if [ -f mvnw ]; then chmod +x mvnw; ./mvnw -B verify sonar:sonar; "
                    "else mvn -B verify sonar:sonar; fi || echo 'SonarQube не настроен — "
                    "укажите параметры sonar.* и переменные окружения SONAR_*'",
                ],
            )
        )
        logs.append("Добавлена задача качества java_sonar (SonarQube для Maven-проекта).")

    # Node.js: плейсхолдер для SonarQube / фронтенд-анализа
    if has_node:
        jobs.append(
            Job(
                name="node_sonar",
                stage="quality",
                image="node:20-alpine",
                script=[
                    "echo 'TODO: добавьте команду запуска SonarQube для фронтенда "
                    "(например, npx sonar-scanner ...)'",
                ],
            )
        )
        logs.append(
            "Добавлена задача качества node_sonar (SonarQube-плейсхолдер для фронтенда)."
        )

    warnings.append(
        "В stage quality добавлены SonarQube-заглушки (java_sonar/node_sonar). "
        "Настройте SONAR_HOST_URL / SONAR_TOKEN и конкретные команды анализа."
    )


def build_pipeline(stack: StackInfo) -> Tuple[Pipeline, List[str], List[str]]:
    """
    Строим абстрактный пайплайн на основе обнаруженного стека.

    Возвращает (Pipeline, logs, warnings).
    """
    logs: List[str] = []
    warnings: List[str] = []
    click.echo(f"Строим пайплайн по стеку: {stack.dict()}")
    logs.append(f"Строим пайплайн по стеку: {stack.dict()}")

    stages: List[str] = []
    jobs: List[Job] = []

    has_python = "python" in stack.languages
    has_node = _has_node(stack)
    has_go = "go" in stack.languages
    has_java = "java" in stack.languages
    pm_node = _node_pm(stack) if has_node else None
    dockerfiles:List[DockerfileInfo] = getattr(stack, "dockerfiles", []) or []

    # --- Python: test / lint ---
    if has_python:
        _ensure_stage(stages, "lint")
        _ensure_stage(stages, "test")

        click.echo("Установка зависимостей Python")
        python_test_script = [
            "if [ -f requirements.txt ]; then python -m pip install -r requirements.txt; "
            "else echo 'requirements.txt не найден — пропускаем установку зависимостей'; fi",
            "python -m pip install pytest || true",
            "pytest || echo 'pytest не настроен или тесты отсутствуют — отредактируйте команду'",
        ]

        jobs.append(
            Job(
                name="python_tests",
                stage="test",
                image="python:3.11-slim",
                script=python_test_script,
            )
        )

        python_lint_script = [
            "python -m pip install flake8 || echo 'flake8 не установлен'",
            "flake8 . || echo 'flake8 нашёл замечания или не настроен — отредактируйте команду'",
        ]

        jobs.append(
            Job(
                name="python_lint",
                stage="lint",
                image="python:3.11-slim",
                script=python_lint_script,
            )
        )
        click.echo("Добавлены задачи для Python: python_tests, python_lint")
        logs.append("Добавлены задачи для Python: python_tests, python_lint")

    # --- Node.js / фронт ---
    if has_node and pm_node:
        _ensure_stage(stages, "lint")
        _ensure_stage(stages, "test")
        _ensure_stage(stages, "build")

        click.echo("Настраиваем задачи для Node.js / фронтенда")

        if pm_node == "yarn":
            # corepack для yarn 3/4 или глобальная установка
            install_cmd = (
                "corepack enable || npm i -g yarn; "
                "yarn install --frozen-lockfile || yarn install"
            )
            test_cmd = "yarn test || echo 'yarn test не настроен — отредактируйте команду'"
            build_cmd = "yarn build || echo 'yarn build не настроен — отредактируйте команду'"
            lint_cmd = "yarn lint || echo 'yarn lint не настроен — отредактируйте команду'"
        elif pm_node == "pnpm":
            # pnpm в node:20-alpine нет → ставим через corepack или npm
            install_cmd = "corepack enable || npm i -g pnpm; pnpm install"
            test_cmd = "pnpm test || echo 'pnpm test не настроен — отредактируйте команду'"
            build_cmd = "pnpm build || echo 'pnpm build не настроен — отредактируйте команду'"
            lint_cmd = "pnpm lint || echo 'pnpm lint не настроен — отредактируйте команду'"
        else:
            install_cmd = "npm ci || npm install"
            test_cmd = "npm test || echo 'npm test не настроен — отредактируйте команду'"
            build_cmd = (
                "npm run build || echo 'npm run build не настроен — отредактируйте команду'"
            )
            lint_cmd = (
                "npm run lint || echo 'npm run lint не настроен — отредактируйте команду'"
            )

        jobs.append(
            Job(
                name="node_lint",
                stage="lint",
                image="node:20-alpine",
                script=[install_cmd, lint_cmd],
            )
        )

        jobs.append(
            Job(
                name="node_tests",
                stage="test",
                image="node:20-alpine",
                script=[install_cmd, test_cmd],
            )
        )

        jobs.append(
            Job(
                name="node_build",
                stage="build",
                image="node:20-alpine",
                script=[install_cmd, build_cmd],
                artifacts=["dist"],
            )
        )
        click.echo("Добавлены задачи для Node.js: node_lint, node_tests, node_build")
        logs.append("Добавлены задачи для Node.js: node_lint, node_tests, node_build")

    # --- Go ---
    if has_go:
        _ensure_stage(stages, "test")
        _ensure_stage(stages, "build")

        click.echo("Настраиваем задачи для Go-проекта")

        jobs.append(
            Job(
                name="go_tests",
                stage="test",
                image="golang:1.22",
                script=[
                    "go test ./... || echo 'go test завершился с ошибкой — проверьте тесты'"
                ],
            )
        )

        jobs.append(
            Job(
                name="go_build",
                stage="build",
                image="golang:1.22",
                script=[
                    "go build ./... || echo 'go build завершился с ошибкой — "
                    "проверьте конфигурацию проекта'",
                ],
            )
        )

        logs.append("Добавлены задачи для Go: go_tests, go_build")

    # --- Java (Maven) ---
    if has_java and "maven" in stack.package_managers:
        _ensure_stage(stages, "test")
        _ensure_stage(stages, "build")

        click.echo("Настраиваем задачи для Java-проекта")

        jobs.append(
            Job(
                name="java_tests",
                stage="test",
                image="maven:3.9-eclipse-temurin-17",
                script=[
                    "if [ -f mvnw ]; then chmod +x mvnw; ./mvnw -B test; "
                    "else mvn -B test; fi || echo 'mvn test завершился с ошибкой — "
                    "отредактируйте pom.xml/профили'",
                ],
            )
        )

        jobs.append(
            Job(
                name="java_build",
                stage="build",
                image="maven:3.9-eclipse-temurin-17",
                script=[
                    "if [ -f mvnw ]; then chmod +x mvnw; ./mvnw -B package -DskipTests; "
                    "else mvn -B package -DskipTests; fi || echo 'mvn package завершился с ошибкой — "
                    "проверьте pom.xml'",
                ],
            )
        )

        logs.append("Добавлены задачи для Java: java_tests, java_build")

    # --- Quality / SonarQube ---
    _append_quality_jobs(stack, stages, jobs, logs, warnings)

    # --- Docker / deploy ---
    # Если анализатор нашёл конкретные Dockerfile'ы, делаем по job'у на каждый
    if dockerfiles:
        _ensure_stage(stages, "docker")
        click.echo(
            "Обнаружены Dockerfile'ы: "
            + ", ".join(df.path for df in dockerfiles)
        )
        logs.append(
            "Обнаружены Dockerfile'ы: "
            + ", ".join(df.path for df in dockerfiles)
        )

        for df in dockerfiles:
            # имя job'а из логического имени сервиса
            job_name = f"docker_build_{df.name.replace('-', '_').replace('.', '_')}"
            image_ref = f"my-image-{df.name}:latest"  # осмысленный, но безопасный плейсхолдер

            docker_script = [
                'echo "Сборка Docker-образа из существующего Dockerfile."',
                (
                    f"docker build -f {df.path} {df.context or '.'} "
                    f"-t {image_ref} || echo 'Настройте docker daemon / registry'"
                ),
                f"echo 'При необходимости замените тег {image_ref} на адрес вашего registry.'",
            ]

            jobs.append(
                Job(
                    name=job_name,
                    stage="docker",
                    image="docker:24",
                    script=docker_script,
                    dockerfile_path=df.path,
                    docker_context=df.context,
                    image_name=df.name,
                )
            )

        warnings.append(
            "Добавлены docker-задачи для каждого найденного Dockerfile. "
            "При необходимости отредактируйте теги образов и настройки registry."
        )

    # Fallback: старое поведение, если есть только флаг has_dockerfile,
    # но список dockerfiles пуст (например, старые данные / неполный анализ).
    elif stack.has_dockerfile:
        _ensure_stage(stages, "docker")
        docker_script = [
            'echo "Сборка Docker-образа. Настройте свой registry и docker runner."',
            "docker build -t my-image:latest . || echo 'Настройте docker daemon / registry'",
        ]
        jobs.append(
            Job(
                name="docker_build",
                stage="docker",
                image="docker:24",
                script=docker_script,
            )
        )
        click.echo(
            "Обнаружен Dockerfile (флаг has_dockerfile), но список dockerfiles пуст. "
            "Добавлена обобщённая задача docker_build."
        )
        logs.append(
            "Обнаружен Dockerfile (только флаг). Добавлена обобщённая задача docker_build."
        )
        warnings.append(
            "Анализатор не вернул конкретные Dockerfile'ы. Пайплайн использует docker build . "
            "Рекомендуется донастроить анализатор, чтобы заполнить StackInfo.dockerfiles."
        )

    _ensure_stage(stages, "deploy")
    deploy_script = [
        'echo "TODO: добавьте реальные команды деплоя (kubectl / ssh / helm и т.п.)"'
    ]
    jobs.append(
        Job(
            name="deploy_placeholder",
            stage="deploy",
            script=deploy_script,
        )
    )

    if not (has_python or has_node or has_go or has_java):
        warnings.append(
            "Не обнаружены Python/Node/Go/Java-проекты. "
            "Пайплайн содержит только placeholder-задачи. "
            "Отредактируйте команды под ваш стек."
        )
        click.echo("Построен пайплайн по умолчанию (без специфики языка).")
        logs.append("Построен пайплайн по умолчанию (без специфики языка).")

    # Приводим стадии к каноническому порядку
    if stages:
        unique = list(dict.fromkeys(stages))
        canonical_order = ["lint", "test", "quality", "build", "docker", "deploy"]
        ordered_stages: List[str] = []
        for name in canonical_order:
            if name in unique:
                ordered_stages.append(name)
        # на всякий случай добавим нестандартные стадии в конец
        for name in unique:
            if name not in ordered_stages:
                ordered_stages.append(name)
    else:
        ordered_stages = []

    pipeline = Pipeline(stages=ordered_stages, jobs=jobs)
    logs.append(
        f"Пайплайн сформирован: {len(pipeline.stages)} стадий и {len(pipeline.jobs)} задач."
    )
    click.echo(
        f"Пайплайн сформирован: {len(pipeline.stages)} стадий и {len(pipeline.jobs)} задач."
    )

    return pipeline, logs, warnings


def summarize_pipeline(pipeline: Pipeline) -> PipelineSummary:
    """
    Строит краткое резюме пайплайна для ответа API/CLI.
    """
    stages = list(pipeline.stages)
    job_names = [job.name for job in pipeline.jobs]
    stages_count = len(stages)
    jobs_count = len(job_names)

    if stages_count == 0 and jobs_count == 0:
        description = "Пайплайн пустой. Отредактируйте конфигурацию."
    else:
        description = (
            f"Сгенерирован пайплайн из {stages_count} стадий и {jobs_count} задач: "
            f"стадии {', '.join(stages)}."
        )
    click.echo(
        f"Сгенерирован пайплайн из {stages_count} стадий и {jobs_count} задач: "
        f"стадии {', '.join(stages)}."
    )

    return PipelineSummary(
        stages_count=stages_count,
        jobs_count=jobs_count,
        stages=stages,
        job_names=job_names,
        description=description,
    )
