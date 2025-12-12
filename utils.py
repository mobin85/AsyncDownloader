import os
from typing import Optional
from uuid import uuid4

import filetype

import aiohttp

import re

from datetime import datetime
from enum import Enum
from urllib.parse import urlparse, unquote, parse_qs

from logger import error


class ErrorType(Enum):
    UnSupportedURL = 0
    UnvalidType = 1
    NotValidStatusResponse = 2


class Error(Exception):
    def __init__(self, message: str | BaseException, error_type: str | type | ErrorType):
        self.error_type = error_type
        self.message = message
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        error(self.__str__())
        super().__init__(self.__str__())

    def __str__(self):
        log = f"[{self.timestamp}] {self.error_type}: {self.message}"
        return


async def detect_filename(url: str, session: aiohttp.ClientSession) -> str:
    """
    تلاش برای تشخیص نام فایل از Content-Disposition یا از URL.
    """
    # --- 1) HEAD درخواست بزنیم (بهتر از GET چون سبک تر هست)
    try:
        async with session.head(url, allow_redirects=True) as resp:
            cd = resp.headers.get("Content-Disposition")
            if cd:
                # جستجو filename بین "" یا بدون ""
                fname_match = re.findall(r'filename\*?=(?:UTF-8\'\')?"?([^\";]+)"?', cd)
                if fname_match:
                    return unquote(fname_match[-1])
    except Exception:
        # اگر HEAD جواب نداد، بعداً می‌رویم سراغ URL
        pass

    # --- 2) اگر HEAD جواب نداد، یک GET سبک (streaming) می‌زنیم فقط برای هدر
    try:
        async with session.get(url, allow_redirects=True) as resp:
            cd = resp.headers.get("Content-Disposition")
            if cd:
                fname_match = re.findall(r'filename\*?=(?:UTF-8\'\')?"?([^\";]+)"?', cd)
                if fname_match:
                    return unquote(fname_match[-1])
    except Exception:
        pass

    # --- 3) اگر هیچ Content-Disposition وجود نداشت: از URL filename استخراج کن
    parsed = urlparse(url)
    path = parsed.path

    # اگر path خالی بود یا به / ختم می‌شد → فایل واقعی نیست
    if not path or path.endswith("/"):
        # اگر احتمالاً filename داخل query string هست
        qs = parse_qs(parsed.query)
        for key in ["file", "filename", "name", "download"]:
            if key in qs:
                return unquote(qs[key][0])

        # Fallback
        return await detect_filename_download(url, session)

    # جدا کردن اسم فایل از path
    filename = unquote(path.split("/")[-1] or "")

    # اگر filename معتبر نبود، fallback کن
    if not filename or "." not in filename:
        return await detect_filename_download(url, session)

    return filename


def guess_filename_from_bytes(
        filename: str,
        data: bytes,
        original_name: Optional[str] = None,
) -> str:
    """
    از روی بایت‌ها نوع فایل رو با filetype حدس می‌زنه
    و یه اسم فایل با اکستنشن برمی‌گردونه.
    اگر original_name داشته باشیم، سعی می‌کنیم همونو با اکستنشن درست برگردونیم.
    """

    kind = filetype.guess(data)

    # ۱) اگر filetype اصلاً نتونست تشخیص بده
    if kind is None:
        # اگه اسم اصلی داریم همونو برگردون (هرچی که هست)
        if original_name:
            return original_name
        # وگرنه یه اسم فیک می‌سازیم بدون اکستنشن
        return str(uuid4())

    guessed_ext = kind.extension  # مثلا 'pdf', 'jpg', ...

    # ۲) اگر original_name داریم، سعی کنیم اون رو با اکستنشن درست برگردونیم
    if original_name:
        base, ext = os.path.splitext(original_name)

        # اگر اسم اصلی اکستنشن داره ولی اشتباهه، می‌تونیم عوضش کنیم
        if ext.lower().lstrip(".") != guessed_ext.lower():
            return f"{base}.{guessed_ext}"

        # اگر اکستنشنش درسته، همون رو برگردون
        return original_name

    # ۳) اگر هیچ original_name نداریم → از default_basename استفاده کن
    return f"{kind.mime.split('/')[0]}.{guessed_ext}"


async def detect_filename_download(url: str, session: aiohttp.ClientSession) -> Optional[str]:
    async with session.get(url) as r:
        if r.status not in (200, 206):
            raise Error(f'NOT VALID RESPONSE FROM SERVER {r.status}', ErrorType.NotValidStatusResponse)

        buffer = bytearray()

        async for ch in r.content.iter_chunked(4096 * 6):
            buffer.extend(ch)
            if len(buffer) >= 4096 * 6:
                break

        return guess_filename_from_bytes('file', buffer)

def make_unique_filename(filename: str) -> str:
    """
    Generate a unique filename similar to Windows behavior.
    If the file already exists, append (1), (2), ... before extension.
    """

    # Split filename into name and extension
    try:
        base, ext = filename.split('.')
    except ValueError:
        base = filename
        ext = ""

    # Regex to detect if filename already ends with "(n)"
    pattern = r"^(.*)\((\d+)\)$"
    match = re.match(pattern, base)

    # If filename looks like "file (3).txt", extract base and number
    if match:
        pure_base = match.group(1).rstrip()
        counter = int(match.group(2))
    else:
        pure_base = base
        counter = 0

    candidate = filename

    # Loop until finding a non-existing name
    while True:
        exists = os.path.exists(candidate)
        if not exists:
            return candidate  # unique name found

        counter += 1
        candidate = f"{pure_base} ({counter})" + (f".{ext}" if ext else "")
