from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


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


class PipelineSummary(BaseModel):
    stages_count: int
    jobs_count: int
    stages: List[str]
    job_names: List[str]
    # Короткое текстовое описание для UI
    description: str

