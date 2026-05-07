import os
import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_attempts: dict[str, list[float]] = defaultdict(list)
_ns_attempts: dict[tuple[str, str], list[float]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900   # 15 minutes
LOCKOUT_SECONDS = 900  # 15 minutes

# Only trust proxy headers when explicitly running behind a known reverse proxy.
# On Fly.io: set TRUSTED_PROXY=true and use Fly-Client-IP (injected by Fly, not
# spoofable by clients). Falls back to rightmost X-Forwarded-For (proxy-appended).
_TRUSTED_PROXY = os.environ.get("TRUSTED_PROXY", "").lower() == "true"


def _client_ip(request) -> str:
    if _TRUSTED_PROXY:
        # Fly.io sets Fly-Client-IP to the real client IP; prefer it.
        fly_ip = request.headers.get("fly-client-ip", "").strip()
        if fly_ip:
            return fly_ip
        # Generic trusted-proxy fallback: rightmost XFF entry is proxy-appended.
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",")]
            return ips[-1]
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


# Namespaced rate limit — separate bucket per (namespace, ip).
# Used for routes like /forgot-password that need independent limits.
NS_MAX_ATTEMPTS = 5
NS_WINDOW_SECONDS = 900  # 15 minutes


def ns_is_limited(request, namespace: str) -> bool:
    key = (namespace, _client_ip(request))
    now = time.monotonic()
    with _lock:
        recent = [t for t in _ns_attempts[key] if now - t < NS_WINDOW_SECONDS]
        _ns_attempts[key] = recent
        return len(recent) >= NS_MAX_ATTEMPTS


def ns_record(request, namespace: str) -> None:
    key = (namespace, _client_ip(request))
    now = time.monotonic()
    with _lock:
        _ns_attempts[key].append(now)
        _ns_attempts[key] = [t for t in _ns_attempts[key] if now - t < NS_WINDOW_SECONDS]
