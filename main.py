import hashlib
import os

import asyncio
from pathlib import Path

import aiohttp
import aiofiles
import aiofiles.os as aio_os

from utils import Error, ErrorType, detect_filename, guess_filename_from_bytes, make_unique_filename
from logger import error, debug
from state import DownloadStateManager, TaskState

CHUNK_DIV = 5
CHUNK_SIZE = 1024 * 1024
FILE_PATH = r"D:\!Film\21b57e27b2e068307260e3ef038e27d340136412-720p.mp4"

file_write_lock, write_calls = asyncio.Lock(), 0


async def check_url(url: str, session: aiohttp.ClientSession) -> Error | tuple:
    try:
        r = await session.get(url)
    except Exception as err:
        raise Error(err, type(err))
    headers = r.headers
    length = headers.get('Content-Length')
    if not (ar := headers.get('Accept-Ranges')) or ar != 'bytes' or not length:
        raise Error("Not Sopported Url", ErrorType.UnSupportedURL)
    
    return divmod(float(length), CHUNK_DIV), float(length)

async def write(index: int, filename: str, b: bytes,
                state_manager: DownloadStateManager, start: int, end: int,
                offset: int, total_size: int):
    global write_calls
    async with file_write_lock:
        write_calls += 1
        if not os.path.exists(filename):
            async with aiofiles.open(filename, 'wb') as f:
                await f.seek(total_size - 1)
                await f.write(b'\0')
    
    async with file_write_lock, aiofiles.open(filename, 'r+b') as f:
        await f.seek(offset)
        await f.write(b)
        await f.flush()

        await state_manager.set_state(index, TaskState(
            index=index,
            start=start,
            end=end,
            offset=offset,
        ))


async def download_chunk(index: int, state_manager: DownloadStateManager, url: str,
                         session: aiohttp.ClientSession, filename: str,
                         total_size: int, start: int, end: int | None = None, offset: int | None = None):
    headers = {}

    if not isinstance(start, int):
        raise Error("start must be integer", ErrorType.UnvalidType)  # pyright: ignore[reportUnreachable]
    
    if end is not None and not isinstance(end, int):
        raise Error("start must be integer", ErrorType.UnvalidType)  # pyright: ignore[reportUnreachable]

    if end is not None:
        headers['Range'] = f'bytes={offset or start}-{end}'
    else:
        headers['Range'] = f'bytes={offset or start}-'

    print(f'download chunk {total_size = }, {start = }, {end = }, {offset = }')

    async with session.get(url, headers=headers) as r:
        if r.status not in (200, 206):
            raise Error(f'NOT VALID RESPONSE FROM SERVER {r.status}', ErrorType.NotValidStatusResponse)

        offset = offset or start
        buffer = bytearray()
        
        async for ch in r.content.iter_chunked(CHUNK_SIZE):
            buffer.extend(ch)
            if len(buffer) >= CHUNK_SIZE:
                await write(index, filename, buffer, state_manager, start, end, offset, total_size)

                offset += len(buffer)
                buffer.clear()
        
        if buffer:
            await write(index, filename, buffer, state_manager, start, end, offset, total_size)


async def download(url: str, session: aiohttp.ClientSession, filename: str):
    start_t = asyncio.get_event_loop().time()
    (c, r), length = await check_url(url, session)
    
    print(f"{c = }, {r = }, {length = }")
    debug(f'start make_unique_filename(filename)')
    st = asyncio.get_event_loop().time()
    filename = make_unique_filename(filename)
    debug(f"end make_unique_filename(filename) {asyncio.get_event_loop().time() - st}")

    async with asyncio.TaskGroup() as tg:
        state_manager = DownloadStateManager(url, session, total_size=length, download_filename=filename)
        await state_manager.initialize()

        for i in range(0, CHUNK_DIV):
            start = c * i + (1 if i != 0 else 0)
            end = (c * (i + 1)) + (r if CHUNK_DIV - 1 == i else 0)

            tg.create_task(download_chunk(
                i,
                state_manager,
                url,
                session,
                filename,
                total_size=int(length),
                start=int(start),
                end=int(end) if end is not None else end,
                offset=await state_manager.get_offset(i)
                ))

    state_manager.shutdown()
    # if filename == "SOME_FILE_NAME_THAT_WILL_CHANGE":
    #     async with aiofiles.open(filename, 'rb') as f:
    #         new_filename = guess_filename_from_bytes(filename, await f.read(4096))
    #
    #     if new_filename != filename:
    #         new_filename = make_unique_filename(new_filename)
    #         await aio_os.rename(filename, new_filename, loop=asyncio.get_event_loop())
    #         filename = new_filename

    make_unique_filename(filename)
    end_t = asyncio.get_event_loop().time()
    print(f'File {filename} downloaded in {end_t - start_t} seconds')

async def main():
    # async with aiofiles.open("") as f:
    #     f.f
    url = "http://localhost:8000/file"
    async with aiohttp.ClientSession() as c, asyncio.TaskGroup() as tg:

        tg.create_task(download(url, c, await detect_filename(url, c)))
        await asyncio.sleep(1)
        tg.create_task(download(url, c, await detect_filename(url, c)))

if __name__ == '__main__':
    asyncio.run(main())