import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_attempts: dict[str, list[float]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900   # 15 minutes
LOCKOUT_SECONDS = 900  # 15 minutes


def _client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_locked_out(request) -> bool:
    ip = _client_ip(request)
    now = time.monotonic()
    with _lock:
        timestamps = _attempts[ip]
        recent = [t for t in timestamps if now - t < WINDOW_SECONDS]
        _attempts[ip] = recent
        return len(recent) >= MAX_ATTEMPTS


def record_failure(request) -> int:
    ip = _client_ip(request)
    now = time.monotonic()
    with _lock:
        _attempts[ip].append(now)
        recent = [t for t in _attempts[ip] if now - t < WINDOW_SECONDS]
        _attempts[ip] = recent
        return len(recent)


def clear_attempts(request) -> None:
    ip = _client_ip(request)
    with _lock:
        _attempts.pop(ip, None)


def remaining_lockout(request) -> int:
    ip = _client_ip(request)
    now = time.monotonic()
    with _lock:
        recent = [t for t in _attempts.get(ip, []) if now - t < WINDOW_SECONDS]
        if len(recent) < MAX_ATTEMPTS:
            return 0
        oldest = min(recent)
        return max(0, int(LOCKOUT_SECONDS - (now - oldest)))
