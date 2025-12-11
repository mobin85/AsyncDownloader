import os
import pickle

import aiohttp
import asyncio
import aiofiles

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class Base:
    def asdict(self):
        return asdict(self)


@dataclass
class TaskState(Base):
    """
    each task state
    """
    index: int
    start: int
    end: int
    offset: int


@dataclass
class DownloadState(Base):
    """
    each download state
    data is task state dict
    url is download url
    filename is download filename
    """
    data: dict[int, TaskState] = field(init=False)
    url: str
    filename: str
    total_size: int


class DownloadStateManager:
    def __init__(self, url: str, session: aiohttp.ClientSession, total_size: int, download_filename: str):
        self.url = url
        self.session = session
        self.download_filename = download_filename
        self.total_size = total_size
        self.state_filename = f"{self.download_filename}.pystate"

        self._lock = asyncio.Lock()
        self._state: DownloadState = DownloadState(self.url, self.download_filename, self.total_size)
        self._state.data = {}

    async def state(self) -> DownloadState:
        async with self._lock:
            return self._state

    async def set_state(self, index: int, task_state: TaskState) -> None:
        async with self._lock:
            self._state.data[index] = task_state

            async with aiofiles.open(self.state_filename, "wb") as f:
                await f.write(DownloadStateManager.picklize(self._state))

    async def get_offset(self, index: int) -> int | None:
        async with self._lock:
            if not os.path.exists(self.state_filename):
                return None

            async with aiofiles.open(self.state_filename, "rb") as f:
                if self._state.data.get(index) is not None:
                    return self._state.data[index].offset

                return None

    async def initialize(self):
        async with self._lock:
            if os.path.exists(self.state_filename):
                try:
                    async with aiofiles.open(self.state_filename, 'rb') as f:
                        self._state = pickle.loads(await f.read())
                except pickle.PickleError:
                    ...

    def shutdown(self):
        if os.path.exists(self.state_filename):
            os.remove(self.state_filename)
        del self

    @staticmethod
    def picklize(data: Any) -> bytes:
        return pickle.dumps(data)
