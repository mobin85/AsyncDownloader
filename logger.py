# logger_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# -------- Exception Logger --------
EXC_LOG_FILE = os.path.join(LOG_DIR, "exceptions.log")
exception_logger = logging.getLogger("exception_logger")
exception_logger.setLevel(logging.ERROR)

exc_handler = RotatingFileHandler(
    EXC_LOG_FILE,
    maxBytes=500_000,
    backupCount=5,
    encoding="utf-8"
)
exc_handler.setLevel(logging.ERROR)
exc_formatter = logging.Formatter("%(levelname)s - %(message)s")
exc_handler.setFormatter(exc_formatter)

if not exception_logger.handlers:
    exception_logger.addHandler(exc_handler)

# -------- Debug Logger --------
DEBUG_LOG_FILE = os.path.join(LOG_DIR, "debug.log")
debug_logger = logging.getLogger("debug_logger")
debug_logger.setLevel(logging.DEBUG)

debug_handler = RotatingFileHandler(
    DEBUG_LOG_FILE,
    maxBytes=500_000,
    backupCount=5,
    encoding="utf-8"
)
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
debug_handler.setFormatter(debug_formatter)

if not debug_logger.handlers:
    debug_logger.addHandler(debug_handler)


def error(msg: object):
    exception_logger.error(msg)

def debug(msg: object):
    debug_logger.debug(msg)