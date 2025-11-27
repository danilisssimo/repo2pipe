import functools
import asyncio

class AsyncContext():

    def __init__(self, delay):
        self.delay = delay

    async def __aenter__(self):
        await asyncio.sleep(self.delay)
        return self.delay

    async def __aexit__(self, exc_type, exc, tb):
        await asyncio.sleep(self.delay)


def async_click(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper