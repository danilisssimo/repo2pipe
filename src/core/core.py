from .animation import run as run_animation
from .renders import gitlab as gitlab_render, jenkins as jenkins_render
from .services.analyzer import core as analyzer
from .services.builders import pipeline as builder
from .services.git_module import GitRepo2Pipe
from .services.git_module.models import LocalRepo
from .services.git_module.exceptions import GitExceptions
from .models import AnalyzeResponse, StackInfo


class Repo2PipeCore:
    def __init__(self, repo_branch="main"):
        self.git = GitRepo2Pipe(default_branch=repo_branch)
        self.pipe_builder = None
        self.renders = None
        self.logs: list[str] = []
        self.warnings: list[str] = []
        self.stack = StackInfo()
        self.ci_templates: dict[str, str] = {}
        self.pipeline_summary = None

    async def create_pipline(self, repository:str, branch:str, pipeline_type:str):
        try:
            cloned:LocalRepo = await run_animation(
                self.git.clone,
                repository,
                branch,
                text=f"Клонирование репозитория {repository}"
            )

            stack, analysis_logs, analysis_warnings = analyzer.analyze_stack(cloned.repo_path)
            # click.echo(analysis_logs)
            # click.echo(analysis_warnings, err=True, color=True)
            self.logs.extend(analysis_logs)
            self.warnings.extend(analysis_warnings)

            # 3) Строим абстрактный пайплайн
            pipeline, pipeline_logs, pipeline_warnings = builder.build_pipeline(stack)
            # click.echo(pipeline_logs)
            self.logs.extend(pipeline_logs)
            self.warnings.extend(pipeline_warnings)

            # 3.1) Строим краткое резюме пайплайна
            pipeline_summary = builder.summarize_pipeline(pipeline)

            # 4) Рендерим CI-шаблоны
            if "gitlab" == pipeline_type:
                self.ci_templates["gitlab"] = gitlab_render.render(pipeline)
            if "jenkins" == pipeline_type:
                self.ci_templates["jenkins"] = jenkins_render.render(pipeline)

            if not self.ci_templates:
                self.warnings.append(
                    "ci_systems пустой — шаблоны CI не сгенерированы. "
                    "Укажите хотя бы 'gitlab' или 'jenkins'."
            )

        except GitExceptions as e:
            self.logs.extend(e.logs)
            self.warnings.append(
                "Не удалось клонировать репозиторий. Проверьте URL/ветку и доступы."
            )
            self.warnings.append("Анализ стека и генерация пайплайна не выполнены.")
            return AnalyzeResponse(
                status="error",
                stack=stack,
                ci_templates=self.ci_templates,
                warnings=self.warnings,
                logs=self.logs,
                pipeline_summary=None,
            )
        finally:
            if cloned is not None:
                try:
                    cloned.cleanup()
                    self.logs.append("Временная папка с репозиторием удалена.")
                except Exception:
                    self.logs.append(
                        "Не удалось удалить временную папку с репозиторием (см. логи сервера)."
                    )

        if not self.warnings:
            self.warnings.append(
                "Шаблоны CI сгенерированы автоматически. Проверьте команды сборки/тестов/деплоя и адаптируйте под ваш проект."
            )

        return AnalyzeResponse(
            status="ok",
            stack=stack,
            ci_templates=self.ci_templates,
            warnings=self.warnings,
            logs=self.logs,
            pipeline_summary=pipeline_summary,
        )
