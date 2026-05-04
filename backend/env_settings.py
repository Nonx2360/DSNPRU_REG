import os
import re
from pathlib import Path


ENV_FILE = Path(".env")
MAIL_KEYS = (
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_FROM",
    "MAIL_PORT",
    "MAIL_SERVER",
    "MAIL_FROM_NAME",
)
MAIL_DEFAULTS = {
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
    "MAIL_FROM": "",
    "MAIL_PORT": "587",
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_FROM_NAME": "DSNPRU Waitlist",
}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    email = value.strip().lower()
    return email or None


def is_valid_email(value: str | None) -> bool:
    email = normalize_email(value)
    if not email:
        return False
    return bool(EMAIL_PATTERN.match(email))


def read_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            values[key.strip()] = value.strip()

    for key in MAIL_KEYS:
        if key in os.environ and os.environ[key]:
            values[key] = os.environ[key]

    return values


def get_mail_settings() -> dict[str, str]:
    values = read_env_values()
    settings = MAIL_DEFAULTS.copy()
    for key in MAIL_KEYS:
        if key in values:
            settings[key] = values[key]
    return settings


def mail_settings_complete(settings: dict[str, str] | None = None) -> bool:
    current = settings or get_mail_settings()
    required = ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_SERVER", "MAIL_FROM_NAME")
    if any(not current.get(key, "").strip() for key in required):
        return False

    port = current.get("MAIL_PORT", "").strip()
    if not port.isdigit():
        return False

    return True


def write_mail_settings(settings: dict[str, str]) -> dict[str, str]:
    current = get_mail_settings()
    updated = current.copy()
    for key in MAIL_KEYS:
        value = settings.get(key)
        if value is None:
            continue
        updated[key] = str(value).strip()

    lines = []
    index_by_key: dict[str, int] = {}
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        for idx, raw_line in enumerate(lines):
            if "=" not in raw_line:
                continue
            key, _ = raw_line.split("=", 1)
            index_by_key[key.strip()] = idx

    for key in MAIL_KEYS:
        rendered = f"{key}={updated[key]}"
        if key in index_by_key:
            lines[index_by_key[key]] = rendered
        else:
            lines.append(rendered)

    ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    for key in MAIL_KEYS:
        os.environ[key] = updated[key]

    return updated


def serialize_mail_settings() -> dict[str, str | bool | int]:
    settings = get_mail_settings()
    port_value = settings.get("MAIL_PORT", "587").strip()
    return {
        "mail_username": settings.get("MAIL_USERNAME", ""),
        "mail_password": "",
        "mail_from": settings.get("MAIL_FROM", ""),
        "mail_port": int(port_value) if port_value.isdigit() else 587,
        "mail_server": settings.get("MAIL_SERVER", ""),
        "mail_from_name": settings.get("MAIL_FROM_NAME", ""),
        "has_password": bool(settings.get("MAIL_PASSWORD", "").strip()),
        "is_configured": mail_settings_complete(settings),
    }
