from pydantic import BaseModel
from typing import List, Optional


class Job(BaseModel):
    """
    Абстрактная задача пайплайна.
    На этом уровне не привязана к GitLab или Jenkins.
    """

    name: str
    stage: str
    image: Optional[str] = None
    script: List[str]

    artifacts: List[str] = None
    only_branches: Optional[List[str]] = None
    tags: Optional[List[str]] = None   # runner tags (для GitLab)
    when: Optional[str] = None         # on_success, manual и т.п.
    environment: Optional[str] = None  # имя окружения деплоя, если нужно
    

    dockerfile_path: Optional[str] = None
    docker_context: Optional[str] = None
    image_name: Optional[str] = None


class Pipeline(BaseModel):
    """
    Абстрактный пайплайн: порядок стадий + набор задач.
    """

    stages: List[str]
    jobs: List[Job]
