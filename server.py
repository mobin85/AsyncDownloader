
import os
import re
from typing import Optional, Iterator

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI()

FILE_PATH = r"D:\Win10_22H2_English_x64v1.iso"
CHUNK_SIZE = 1024 * 1024   # 1MB برای استریم


def iter_file(path: str, start: int = 0, end: Optional[int] = None) -> Iterator[bytes]:
    """خواندن تکه‌تکه فایل از start تا end (شامل end)"""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = None if end is None else (end - start + 1)

        while True:
            # اگر محدوده تعریف شده، کنترل کنیم
            if remaining is not None:
                if remaining <= 0:
                    break
                chunk_size = min(CHUNK_SIZE, remaining)
            else:
                chunk_size = CHUNK_SIZE

            data = f.read(chunk_size)
            if not data:
                break

            if remaining is not None:
                remaining -= len(data)

            yield data


@app.get("/file")
async def get_file(request: Request):
    if not os.path.exists(FILE_PATH):
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(FILE_PATH)
    range_header = request.headers.get("range")

    # اگر Range نفرستاده بود -> کل فایل
    if range_header is None:
        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        return StreamingResponse(
            iter_file(FILE_PATH, 0, None),
            media_type="application/octet-stream",
            headers=headers,
        )

    # مثال هدر: Range: bytes=1000-2000
    range_match = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not range_match:
        # اگر فرمتش عجیب بود، می‌تونیم کل فایل بدیم یا 416؛ من 416 می‌دم
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start_str, end_str = range_match.groups()

    if start_str == "":
        start = 0
    else:
        start = int(start_str)

    if end_str == "":
        end = file_size - 1
    else:
        end = int(end_str)

    # محدود کردن و چک رنج
    if start >= file_size or start < 0:
        # Range نامعتبر
        headers = {"Content-Range": f"bytes */{file_size}"}
        raise HTTPException(status_code=416, detail="Range Not Satisfiable", headers=headers)

    end = min(end, file_size - 1)
    if end < start:
        headers = {"Content-Range": f"bytes */{file_size}"}
        raise HTTPException(status_code=416, detail="Range Not Satisfiable", headers=headers)

    chunk_size = end - start + 1

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
    }

    return StreamingResponse(
        iter_file(FILE_PATH, start, end),
        status_code=206,
        media_type="application/octet-stream",
        headers=headers,
    )
