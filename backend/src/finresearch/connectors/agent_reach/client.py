from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str
    stderr: str = ""


_DOCTOR_CACHE: tuple[datetime, CommandResult] | None = None


class AgentReachCommandClient:
    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def has_command(self, command: str) -> bool:
        return shutil.which(command) is not None

    def doctor(self, timeout_seconds: int = 5, *, use_cache: bool = True) -> CommandResult:
        global _DOCTOR_CACHE
        if not shutil.which("agent-reach"):
            return CommandResult(False, "", "agent-reach is not installed")
        now = datetime.now(UTC)
        if use_cache and _DOCTOR_CACHE is not None:
            checked_at, result = _DOCTOR_CACHE
            if now - checked_at <= timedelta(minutes=10):
                return result
        result = self._run(["agent-reach", "doctor", "--json"], timeout_seconds=timeout_seconds)
        _DOCTOR_CACHE = (now, result)
        return result

    def exa_search(self, query: str, limit: int = 10, timeout_seconds: int | None = None) -> CommandResult:
        if not shutil.which("mcporter"):
            return CommandResult(False, "", "mcporter is not installed")
        expression = f'exa.web_search_exa(query: {json.dumps(query)}, numResults: {limit})'
        return self._run(["mcporter", "call", expression], timeout_seconds=timeout_seconds)

    def read_url(self, url: str) -> CommandResult:
        endpoint = "https://r.jina.ai/" + quote(url, safe=":/?&=%#")
        try:
            response = requests.get(endpoint, timeout=self.timeout_seconds)
            response.raise_for_status()
            return CommandResult(True, response.text)
        except requests.RequestException as exc:
            return CommandResult(False, "", str(exc))

    def _run(self, argv: list[str], timeout_seconds: int | None = None) -> CommandResult:
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout_seconds or self.timeout_seconds,
                check=False,
            )
            return CommandResult(completed.returncode == 0, completed.stdout, completed.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CommandResult(False, "", str(exc))
