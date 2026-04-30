import os
import uuid
from typing import Dict

import requests


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def ensure_server_up(timeout: int = 3) -> None:
    response = requests.get(f"{BASE_URL}/", timeout=timeout)
    response.raise_for_status()


def admin_login() -> str:
    response = requests.post(
        f"{BASE_URL}/admin/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=5,
    )
    if response.status_code != 200:
        raise RuntimeError(
            "Admin login failed. Set ADMIN_USERNAME/ADMIN_PASSWORD env vars if needed."
        )
    return response.json()["access_token"]


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def unique_username(prefix: str = "test_staff") -> str:
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"
