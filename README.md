# repo2pipe

CLI-сервис для автоматической генерации CI/CD-pipeline по репозиторию.

Поддерживаемые системы CI:
- GitLab CI — генерация файла `.gitlab-ci.yml`
- Jenkins — генерация `Jenkinsfile`

На вход подаётся репозиторий (URL, архив или локальная директория с кодом),
на выходе — готовый конфигурационный файл для выбранной CI-системы.

---

## Возможности

- Анализ исходного кода проекта и определение стека (язык, фреймворки, используемые инструменты).
- Автоматическая сборка абстрактного пайплайна (сборка, тесты, линтеры, деплой и т.п.).
- Рендеринг пайплайна в:
  - GitLab CI (`.gitlab-ci.yml`)
  - Jenkins (`Jenkinsfile`)
- Работа из терминала как одна команда `repo2pipe`.
- Поддержка нескольких вариантов входа:
  - HTTPS-ссылка на Git-репозиторий (GitHub/GitLab и т.п.),
  - путь до архива с репозиторием,
  - путь до локального рабочего каталога.

---

## Как это работает (в общих чертах)

1. Клонирование/получение репозитория
   Через слой `GitRepo2Pipe` репозиторий клонируется/распаковывается во временную директорию.
   В CLI в этот момент показывается анимация загрузки (`core/animation.py`).

2. Анализ стека
   Модуль `core/services/analyzer/core.py` анализирует содержимое проекта
   и формирует объект `StackInfo` (язык, фреймворки, наличие Dockerfile и т.п.).

3. Построение абстрактного пайплайна
   Модуль `core/services/builders/pipeline.py` на основе стека строит
   абстрактную модель пайплайна (шаги, джобы, зависимости)
   и формирует краткое резюме пайплайна (`pipeline_summary`).

4. Рендеринг в конкретную CI-систему
   - `core/renders/gitlab.py` → `.gitlab-ci.yml`
   - `core/renders/jenkins.py` → `Jenkinsfile`

5. Результат
   Класс `Repo2PipeCore` возвращает объект `AnalyzeResponse` с:
   - статусом (`ok` / `error`),
   - обнаруженным стеком,
   - словарём CI-шаблонов (`ci_templates`),
   - логами и предупреждениями,
   - резюме пайплайна.

CLI-обёртка печатает результат в консоль и сохраняет файл на диск.

---

## Требования

- Python 3.10+
- Установленный Git (CLI), т.к. используется GitPython
- Поддерживаемые ОС: Linux / macOS / Windows (при наличии Python 3.10+ и git)

Python-зависимости перечислены в `requirements.txt`:

- click
- GitPython
- uvicorn[standard]
- pydantic
- python-multipart

---

## Установка

Рекомендуется использовать виртуальное окружение.

### 1. Создать и активировать виртуальное окружение

```bash
python3.10 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate     # Windows
```

### 2. Установка зависимостей для разработки (вариант)

```bash
pip install -r requirements.txt
pip install -e .
```

### 3. Сборка и установка как пакета (вариант из pyproject.toml)

```bash
python3.10 -m pip install --upgrade pip build
python3.10 -m build
python3.10 -m pip install --force-reinstall dist/repo2pipe-1.0.1-py3-none-any.whl
```

После установки команда `repo2pipe` будет доступна из терминала:

```bash
repo2pipe --help
```

---

## Использование CLI

Точка входа определяется в pyproject.toml:

[project.scripts]
repo2pipe = "cli:main"

### Сигнатура команды

```bash
repo2pipe [OPTIONS] REPOSITORY [BRANCH]
```

Где:

- REPOSITORY — один из вариантов:
  - HTTPS-URL репозитория (`https://github.com/user/repo.git`),
  - путь до архива с репозиторием (`/path/to/repo.zip`),
  - путь до локальной директории с проектом (`/home/user/project`).

- BRANCH — имя ветки Git, для которой нужно собрать пайплайн.
  По умолчанию: master.

### Опции

```python
@click.option(
    "--type",
    default="gitlab",
    help="CI/CD pipline type",
)
@click.option(
    "-o",
    "--output",
    default=".",
    help="Путь к директории, куда сохранить результат",
)
```

- --type
  Тип целевой CI-системы:

  - gitlab — сгенерировать `.gitlab-ci.yml` (значение по умолчанию),
  - jenkins — сгенерировать `Jenkinsfile`.

  Внутри используется:

  ```python
  default_names = { "gitlab": ".gitlab-ci.yml", "jenkins": "Jenkinsfile" }
  ```

- -o, --output
  Путь к директории, куда будет сохранён результирующий файл.
  Имя файла подбирается автоматически на основе --type:
  - для gitlab → <output>/.gitlab-ci.yml
  - для jenkins → <output>/Jenkinsfile

Важно: это директория, а не имя файла.
Пример: `-o ./ci` → `./ci/.gitlab-ci.yml`.

### Примеры команд (кратко)

```bash
# GitLab CI по удалённому репозиторию
repo2pipe https://gitlab.com/user/repo.git master

# GitLab CI с сохранением в существующую поддиректорию ci/
repo2pipe -o ./ci https://gitlab.com/user/repo.git master

# Jenkinsfile по локальному проекту
repo2pipe --type jenkins /home/user/my-service main -o ./ci

# GitLab CI по архиву с проектом
repo2pipe /tmp/project.zip master -o ./pipelines
```

Более развернутые примеры приведены в следующем разделе.

---

## Примеры использования

### 1. GitLab CI по удалённому репозиторию

```bash
repo2pipe https://gitlab.com/user/repo.git master
```

Результат:

- в консоль выводится содержимое `.gitlab-ci.yml`,
- файл сохраняется в текущую директорию: `./.gitlab-ci.yml`.

---

### 2. Jenkinsfile по локальному проекту

```bash
repo2pipe --type jenkins /home/user/my-service main -o ./ci
```

Результат:

- в консоль выводится содержимое `Jenkinsfile`,
- файл сохраняется в `./ci/Jenkinsfile`.

---

### 3. GitLab CI по архиву с проектом

```bash
repo2pipe /tmp/project.zip master -o ./pipelines
```

Результат:

- в консоль выводится содержимое `.gitlab-ci.yml`,
- файл сохраняется в `./pipelines/.gitlab-ci.yml`.

---

## Структура проекта

Дерево src/:

src/
├── api
│   ├── __init__.py
│   └── v1
│       ├── __init__.py
│       ├── analyze.py
│       └── models.py
├── api_server.py
├── cli.py
├── core
│   ├── __init__.py
│   ├── animation.py
│   ├── ci_sctipts.py
│   ├── config.py
│   ├── core.py
│   ├── models.py
│   ├── renders
│   │   ├── __init__.py
│   │   ├── gitlab.py
│   │   └── jenkins.py
│   └── services
│       ├── __init__.py
│       ├── analyzer
│       │   ├── __init__.py
│       │   └── core.py
│       ├── builders
│       │   ├── __init__.py
│       │   └── pipeline.py
│       └── git_module
│           ├── __init__.py
│           ├── core.py
│           ├── exceptions.py
│           ├── models.py
│           └── utils.py
├── exception.py
├── model.py
├── models
│   └── schemas.py
├── settings.py
└── utils.py

### Краткое описание модулей

- cli.py
  Входная точка CLI (repo2pipe). Обрабатывает аргументы командной строки,
  вызывает Repo2PipeCore, выводит и сохраняет результаты.

- core/core.py
  Основной класс Repo2PipeCore:
  - оркеструет операции: клонирование → анализ стека → сборка пайплайна → рендеринг;
  - собирает логи и предупреждения;
  - возвращает AnalyzeResponse с шаблонами CI.

- core/animation.py
  Обёртка run для запуска долгих операций (например, git clone) с анимацией в терминале.

- core/services/git_module/*
  Работа с Git-репозиториями:
  - core.py — логика клонирования/получения репозитория (GitRepo2Pipe);
  - models.py — модели для представления локального репозитория (LocalRepo и т.п.);
  - exceptions.py — специализированные исключения (GitExceptions);
  - utils.py — вспомогательные функции (временные директории, пути и т.д.).

- core/services/analyzer/core.py
  Анализ стека проекта:
  - определение языка/фреймворка,
  - поиск Dockerfile и других файлов,
  - формирование StackInfo,
  - генерация логов/предупреждений.

- core/services/builders/pipeline.py
  Построение абстрактного пайплайна:
  - создание шагов/джобов на основе стека;
  - метод build_pipeline(stack);
  - метод summarize_pipeline(pipeline) для краткого описания пайплайна.

- core/renders/gitlab.py, core/renders/jenkins.py
  Рендеринг абстрактного пайплайна в:
  - GitLab CI YAML,
  - Jenkins Declarative Pipeline (или Scripted — в зависимости от реализации).

- api_server.py, api/v1/*
  Заготовка под HTTP API (на базе FastAPI).
  Позволяет вызывать тот же Repo2PipeCore через HTTP-запросы (например, из UI или других сервисов).

- models/schemas.py, model.py
  Pydantic-схемы и модельные классы, используемые в API и ядре.

- settings.py
  Глобальные настройки проекта (в т.ч. LOGO для CLI).

- utils.py
  Вспомогательные функции, включая async_click — обёртку для асинхронных CLI-команд.

- exception.py
  Общие исключения верхнего уровня (если используются).

---

## Логи и предупреждения

В процессе работы Repo2PipeCore.create_pipline:

- в self.logs накапливаются технические сообщения (ход выполнения, статусы операций);
- в self.warnings — предупреждения для пользователя:
  - проблемы с клонированием,
  - невозможность удалить временную папку,
  - напоминание проверить сгенерированный CI.

При ошибках клонирования выбрасывается GitExceptions, и в ответе выставляется статус error:

return AnalyzeResponse(
    status="error",
    stack=stack,
    ci_templates=self.ci_templates,
    warnings=self.warnings,
    logs=self.logs,
    pipeline_summary=None,
)

CLI в текущей версии выводит только итоговый шаблон и сообщения о сохранении файла.
Более подробные логи и summary доступны через API или при прямой работе с Repo2PipeCore.

---

## Ограничения и планы

- Поддерживаются системы CI:
  - GitLab CI,
  - Jenkins.
- Другие CI-системы (GitHub Actions, TeamCity и т.п.) пока не реализованы.
- Сгенерированные пайплайны являются автоматическим шаблоном, который рекомендуется
  просмотреть и при необходимости адаптировать под конкретный проект
  (команды сборки, тестов, деплоя и т.д.).

---

## Авторы

Проект разрабатывается командой:

- Артемий Шмонин — amsh004@gmail.com
- Данила Демидов — andercomand@gmail.com
- Данила Потапчук — potapchuk01@mail.ru
- Оксана Тётченко — oksanatetcenko@gmail.com
- Валерия Цветкова — cvetkovalerocka@gmail.com

---

## Лицензия

Проект распространяется под лицензией MIT.
Текст лицензии указан в pyproject.toml и может быть вынесен в отдельный файл LICENSE.