from pathlib import Path
import os
from tempfile import gettempdir

"""
Базовая настройка рабочего каталога для временных репозиториев.

По умолчанию всё складывается в системный /tmp/selfdeploy (или аналог на Windows).
Можно переопределить переменной окружения SELFDEPLOY_WORKDIR.
"""

BASE_TEMP_DIR = Path(
    os.getenv("SELFDEPLOY_WORKDIR", gettempdir())
) / "selfdeploy"

BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
