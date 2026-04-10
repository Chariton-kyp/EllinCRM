"""Rate limiter singleton for FastAPI endpoints.

Used by the chat router to throttle requests per client IP.
Wired into the FastAPI app via ``main.py`` exception handler.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
