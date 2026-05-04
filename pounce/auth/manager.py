import json
import getpass

import httpx

from pounce import config


def _load() -> dict:
    if config.CREDENTIALS_FILE.exists():
        return json.loads(config.CREDENTIALS_FILE.read_text())
    return {}


def _save(data: dict) -> None:
    config.CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    config.CREDENTIALS_FILE.chmod(0o600)


def get_token() -> str:
    """Return the stored access token, refreshing if needed."""
    creds = _load()
    token = creds.get("access_token", "")
    if not token:
        raise RuntimeError("Not logged in — run: pounce login")
    return token


def get_user_id() -> int:
    creds = _load()
    uid = creds.get("user_id")
    if uid is None:
        raise RuntimeError("Not logged in — run: pounce login")
    return int(uid)


def get_server_url() -> str:
    creds = _load()
    return creds.get("server_url", config.API_BASE_URL)


def login(server_url: str, email: str, password: str | None = None) -> dict:
    """Authenticate against the server and persist credentials."""
    if password is None:
        password = getpass.getpass(f"Password for {email}: ")

    server_url = server_url.rstrip("/")
    with httpx.Client() as client:
        resp = client.post(
            f"{server_url}/api/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )

    if resp.status_code == 401:
        raise RuntimeError("Invalid email or password")
    resp.raise_for_status()

    data = resp.json()
    _save({
        "access_token": data["access_token"],
        "user_id": data["user_id"],
        "email": data["email"],
        "server_url": server_url,
    })
    return data


def logout() -> None:
    if config.CREDENTIALS_FILE.exists():
        config.CREDENTIALS_FILE.unlink()


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_token()}"}
