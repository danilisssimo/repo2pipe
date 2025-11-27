from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Optional

class DockerfileInfo(BaseModel):
    """
    Описание одного Dockerfile в репозитории.
    path    — относительный путь до Dockerfile от корня репо
    context — контекст сборки (директория, в которой запускаем docker build)
    name    — логическое имя сервиса/образа, будет использоваться в названии job'а
    kind    — опциональный тип/роль, на будущее (frontend/backend/test и т.п.)
    """
    path: str
    context: str
    name: str
    kind: Optional[str] = None

class StackInfo(BaseModel):
    languages: List[str] = []
    frameworks: List[str] = []
    package_managers: List[str] = []
    has_dockerfile: bool = False
    has_docker_compose: bool = False
    has_k8s_manifests: bool = False

    # Новое: зависимости и версии (для соответствия кейсу)
    # dependencies["python"] = {"fastapi": "0.110.0", "pytest": "7.4.0", ...}
    dependencies: Dict[str, Dict[str, str]] = Field(default_factory=dict)

    # language_versions["python"] = "3.11", language_versions["go"] = "1.22" и т.п.
    language_versions: Dict[str, str] = Field(default_factory=dict)

    # framework_versions["spring"] = "3.2.0", framework_versions["fastapi"] = "0.110.0" и т.п.
    framework_versions: Dict[str, str] = Field(default_factory=dict)

    dockerfiles: List[DockerfileInfo] = Field(default_factory=list)


class PipelineSummary(BaseModel):
    stages_count: int
    jobs_count: int
    stages: List[str]
    job_names: List[str]
    # Короткое текстовое описание для UI
    description: str


class AnalyzeRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    ci_systems: List[Literal["gitlab", "jenkins"]] = ["gitlab"]

class AnalyzeResponse(BaseModel):
    status: Literal["ok", "error"]
    stack: StackInfo
    ci_templates: Dict[str, str] = {}
    warnings: List[str] = []
    logs: List[str] = []
    pipeline_summary: Optional[PipelineSummary] = None