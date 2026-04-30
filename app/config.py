import os
from pathlib import Path

import bcrypt


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def _migrate_plaintext_password(env_path: Path) -> None:
    """On first run: if APP_PASSWORD exists, hash it, write APP_PASSWORD_HASH, remove APP_PASSWORD."""
    plaintext = os.environ.get("APP_PASSWORD")
    if not plaintext or os.environ.get("APP_PASSWORD_HASH"):
        return
    hashed = hash_password(plaintext)
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    new_lines = [l for l in lines if not l.startswith("APP_PASSWORD=")]
    new_lines.append(f"APP_PASSWORD_HASH={hashed}")
    env_path.write_text("\n".join(new_lines) + "\n")
    os.environ["APP_PASSWORD_HASH"] = hashed
    del os.environ["APP_PASSWORD"]


def save_env_value(env_path: Path, key: str, value: str) -> None:
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    new_lines = [l for l in lines if not l.startswith(f"{key}=")]
    new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n")
    os.environ[key] = value


class Settings:
    @property
    def data_dir(self) -> Path:
        return Path(os.environ.get("DATA_DIR", Path(__file__).parent.parent))

    @property
    def data_file(self) -> Path:
        return self.data_dir / "debts.json"

    @property
    def env_file(self) -> Path:
        return self.data_dir / ".env"

    @property
    def secret_key(self) -> str:
        key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
        if os.environ.get("APP_ENV", "development").lower() == "production" and key == "dev-secret-change-me":
            raise RuntimeError("SECRET_KEY must be set in production (APP_ENV=production)")
        return key

    @property
    def app_user(self) -> str:
        return os.environ.get("APP_USER", "admin")

    @property
    def app_password_hash(self) -> str:
        return os.environ.get("APP_PASSWORD_HASH", "")

    @property
    def database_url(self) -> str:
        default = f"sqlite+aiosqlite:///{self.data_dir / 'debttracker.db'}"
        return os.environ.get("DATABASE_URL", default)

    @property
    def openai_api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "")

    @property
    def allow_registration(self) -> bool:
        return os.environ.get("ALLOW_REGISTRATION", "false").lower() == "true"

    @property
    def debug(self) -> bool:
        return os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    @property
    def port(self) -> int:
        return int(os.environ.get("PORT", 5050))


settings = Settings()
