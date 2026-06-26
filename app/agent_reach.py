from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import quote

import requests


@dataclass
class CommandResult:
    ok: bool
    stdout: str
    stderr: str = ""


class AgentReachClient:
    """Optional adapter for Agent Reach-installed upstream tools.

    Agent Reach is an installer/router rather than a single research API, so this
    adapter invokes the documented upstream commands directly.
    """

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def doctor(self) -> CommandResult:
        if not shutil.which("agent-reach"):
            return CommandResult(False, "", "agent-reach is not installed")
        return self._run(["agent-reach", "doctor", "--json"])

    def exa_search(self, query: str, num_results: int = 5) -> CommandResult:
        if os.getenv("EXA_ENABLED", "false").lower() != "true":
            return CommandResult(False, "", "EXA_ENABLED=false")
        if not shutil.which("mcporter"):
            return CommandResult(False, "", "mcporter is not installed")
        expression = f'exa.web_search_exa(query: {json.dumps(query)}, numResults: {num_results})'
        return self._run(["mcporter", "call", expression])

    def read_url(self, url: str) -> CommandResult:
        # Jina Reader endpoint documented by Agent Reach.
        endpoint = "https://r.jina.ai/" + quote(url, safe=":/?&=%#")
        try:
            response = requests.get(
                endpoint,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "fin-research-agent/0.1"},
            )
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
