import asyncio
import threading
import time
import sys
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


async def run(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    text: str = "Загрузка",
    interval: float = 0.1,
    **kwargs: Any,
) -> T:
    """
    Запускает асинхронную функцию func и крутит спиннер в ОТДЕЛЬНОМ потоке,
    пока функция не завершится.
    """
    spinner_chars = "|/-\\"
    stop_event = threading.Event()

    def spinner():
        i = 0
        while not stop_event.is_set():
            frame = spinner_chars[i % len(spinner_chars)]
            sys.stdout.write(f"\r{text} {frame}")
            sys.stdout.flush()
            i += 1
            time.sleep(interval)


        clear_len = len(text) + 2
        sys.stdout.write("\r" + " " * clear_len + "\r")
        sys.stdout.flush()

    thread = threading.Thread(target=spinner, daemon=True)
    thread.start()

    success = False

    try:
        result = await func(*args, **kwargs)
        success = True
        return result
    except Exception:
        success = False
        raise
    finally:
        stop_event.set()
        await asyncio.to_thread(thread.join)


        sys.stdout.write("\r" + " " * (len(text) + 2) + "\r")
        sys.stdout.flush()

        if success:
            sys.stdout.write(f"{text} - ✅ Успешно\n")
        else:
            sys.stdout.write(f"{text} - ❌ Ошибка\n")
        sys.stdout.flush()