# Security Notes — Debt Tracker

Accepted risks and known gaps documented for owner review. Items below are non-blocking
for the current single-user / homelab deployment but must be addressed before any
multi-tenant or public-facing release.

---

## MEDIUM — No CSRF Protection on POST Forms

**Affected routes:** all HTML form POSTs (`/login`, `/settings`, `/debts`, `/admin`, etc.)

FastAPI does not include CSRF middleware by default. A logged-in user visiting a
malicious page could have state-mutating requests submitted on their behalf.

**Current mitigations:**
- `SameSite=lax` on the session cookie (Starlette `SessionMiddleware` default) blocks
  cross-site POSTs from third-party navigations in modern browsers.
- Application is not exposed to the public internet in its current deployment.

**Required before public exposure:** add `starlette-csrf` or equivalent middleware and
emit a CSRF token into every form template.

---

## HIGH — No Rate Limiting on Login Endpoint

**Affected route:** `POST /login`

There is no brute-force protection on the login endpoint. An attacker with network
access can make unlimited password-guessing attempts.

**Current mitigations:**
- bcrypt work factor provides natural slowdown (~100 ms per attempt).
- Deployment is behind a private network / VPN with no public ingress.

**Required before public exposure:**
- Add `slowapi` (FastAPI-native) or an upstream rate-limiting reverse proxy rule
  (nginx `limit_req`, OpenShift Route annotations).
- Recommended threshold: 10 attempts per minute per IP, exponential back-off on
  repeated failures.

---

## LOW — Session Cookie Name is Starlette Default ("session")

The `SessionMiddleware` is mounted without a custom `session_cookie` name. The cookie
is named `session`, which is the Starlette framework default.

**Risk:** negligible. The cookie name is not a secret — the HMAC signature on the
payload is the security control, not obscurity of the cookie name. There is no
collision risk unless another `session`-named cookie is set by upstream middleware
on the same path/domain.

**Mitigation (optional):** pass `session_cookie="dt_session"` to `SessionMiddleware`
in `app/__init__.py` to differentiate from other apps on the same domain.

---

## INFO — OpenAI API Key Rotation Required

The `.env` file contains a live `OPENAI_API_KEY` that was present on disk during a
prior security review. The key was never committed to git history (confirmed via
`git ls-files .env`), but the key should be treated as potentially exposed.

**Action required (owner):** rotate the key in the OpenAI dashboard. Update `.env`
with the new key. Do not share the key via chat, logs, or environment dumps.

---

## INFO — Docker Compose DB Credentials

`docker-compose.yml` now references `${DB_USER}`, `${DB_PASSWORD}`, and `${DB_NAME}`
from the environment. These must be set in a `.env` file (gitignored) or injected
via the shell before running `docker compose up`.

See `.env.example` for the required variable names.
