import asyncio
import functools
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Set, Optional

logger = logging.getLogger("src.core.utils")

# Constants typically from config, but here for utility reference
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

def retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    retry_on_exceptions: tuple = (Exception,),
    retry_status_codes: Set[int] = DEFAULT_RETRY_STATUS_CODES,
) -> Callable:
    """Decorator that retries a function with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if hasattr(result, "status_code"):
                        if result.status_code in retry_status_codes:
                            logger.warning(f"Attempt {attempt}/{max_retries} for {func.__name__} returned {result.status_code}")
                            if attempt < max_retries:
                                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                                continue
                    return result
                except retry_on_exceptions as exc:
                    last_exception = exc
                    logger.warning(f"Attempt {attempt}/{max_retries} for {func.__name__} raised {exc}")
                    if attempt < max_retries:
                        time.sleep(backoff_factor * (2 ** (attempt - 1)))
            if last_exception: raise last_exception
            return result
        return wrapper
    return decorator

def async_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    retry_on_exceptions: tuple = (Exception,),
) -> Callable:
    """Async-compatible retry decorator."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception: Optional[Exception] = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on_exceptions as exc:
                    last_exception = exc
                    logger.warning(f"Async attempt {attempt}/{max_retries} for {func.__name__} raised {exc}")
                    if attempt < max_retries:
                        await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
            if last_exception:
                raise last_exception
            raise Exception("Retries exhausted")
        return wrapper
    return decorator

def save_json(data: Any, path: Path) -> Path:
    """Write data as pretty-printed JSON to path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    return path
