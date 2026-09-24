import time
from collections import defaultdict
from threading import Lock

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()

class RateLimitExceededError(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Too many attempts. Try again in {retry_after_seconds} seconds.")

def check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> None:
    now = time.time()
    with _lock:
        recent = [t for t in _attempts[key] if now - t < window_seconds]
        _attempts[key] = recent
        if len(recent) >= max_attempts:
            oldest = min(recent)
            retry_after = int(window_seconds - (now - oldest)) + 1
            raise RateLimitExceededError(retry_after)

def record_attempt(key: str) -> None:
    with _lock:
        _attempts[key].append(time.time())

def get_client_key(request, prefix: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{prefix}:{ip}"