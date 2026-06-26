from __future__ import annotations

from getpass import getpass
from pathlib import Path
from urllib.parse import quote_plus


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV = ROOT / "backend" / ".env"
BACKEND_EXAMPLE = ROOT / "backend" / ".env.example"


def main() -> int:
    print("Configure FIN Research Agent for local PostgreSQL")
    print("=" * 52)
    print("Leave blank to use the default shown in brackets.")
    host = prompt("Host", "localhost")
    port = prompt("Port", "5432")
    database = prompt("Database", "finresearch")
    user = prompt("User", "finresearch")
    password = getpass("Password: ")

    if not password:
        print("Password is required so the app can connect safely.")
        return 1

    url = (
        "postgresql+psycopg://"
        f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(database)}"
    )
    ensure_env()
    upsert_env("DATABASE_URL", url)
    print("\nSaved backend/.env")
    print("Restart the app after changing the database.")
    print("Tables are created automatically on first backend start.")
    return 0


def prompt(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def ensure_env() -> None:
    if BACKEND_ENV.exists():
        return
    if BACKEND_EXAMPLE.exists():
        BACKEND_ENV.write_text(BACKEND_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        BACKEND_ENV.write_text("", encoding="utf-8")


def upsert_env(key: str, value: str) -> None:
    lines = BACKEND_ENV.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"{key}={value}")
    BACKEND_ENV.write_text("\n".join(output) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
