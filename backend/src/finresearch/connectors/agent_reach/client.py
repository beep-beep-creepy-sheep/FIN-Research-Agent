from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str
    stderr: str = ""


class AgentReachCommandClient:
    def __init__(self, timeout_seconds: int = 90) -> None:
        self.timeout_seconds = timeout_seconds

    def doctor(self) -> CommandResult:
        if not shutil.which("agent-reach"):
            return CommandResult(False, "", "agent-reach is not installed")
        return self._run(["agent-reach", "doctor", "--json"])

    def exa_search(self, query: str, limit: int = 10) -> CommandResult:
        if not shutil.which("mcporter"):
            return CommandResult(False, "", "mcporter is not installed")
        expression = f'exa.web_search_exa(query: {json.dumps(query)}, numResults: {limit})'
        return self._run(["mcporter", "call", expression])

    def read_url(self, url: str) -> CommandResult:
        endpoint = "https://r.jina.ai/" + quote(url, safe=":/?&=%#")
        try:
            response = requests.get(endpoint, timeout=self.timeout_seconds)
            response.raise_for_status()
            return CommandResult(True, response.text)
        except requests.RequestException as exc:
            return CommandResult(False, "", str(exc))

    def _run(self, argv: list[str]) -> CommandResult:
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return CommandResult(completed.returncode == 0, completed.stdout, completed.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CommandResult(False, "", str(exc))

