"""Thin adapter over the Daytona SDK.

All lab code talks to this seam so SDK surface drift (exec vs execute_command,
upload_file argument order) stays contained in one file.
"""
from __future__ import annotations

import os

from daytona import Daytona, DaytonaConfig

ENV_FILE = "/root/.lab_env"


class LabSandbox:
    """One pristine sandbox per acceptance run."""

    def __init__(self, inject_env: dict[str, str] | None = None):
        self._daytona = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
        self._sandbox = None
        self._env = inject_env or {}

    def create(self) -> None:
        self._sandbox = self._daytona.create()
        if self._env:
            exports = "\n".join(f"export {k}={v!r}" for k, v in self._env.items())
            self.write_file(ENV_FILE, exports + "\n")

    def run(self, command: str, timeout: int = 240) -> tuple[int | None, str]:
        """Run a shell command; returns (exit_code, output). Injected env is sourced first."""
        wrapped = f". {ENV_FILE} 2>/dev/null || true; {command}"
        proc = self._sandbox.process
        if hasattr(proc, "exec"):
            resp = proc.exec(wrapped, env=self._env or None, timeout=timeout)
        else:
            resp = proc.execute_command(wrapped, timeout=timeout)
        code = getattr(resp, "exit_code", getattr(resp, "code", None))
        out = getattr(resp, "result", None) or getattr(resp, "output", "") or ""
        return code, str(out)

    def write_file(self, path: str, content: str) -> None:
        fs = self._sandbox.fs
        data = content.encode()
        try:
            fs.upload_file(data, path)
        except TypeError:
            fs.upload_file(path, data)

    def destroy(self) -> None:
        if self._sandbox is None:
            return
        try:
            self._sandbox.delete()
        except AttributeError:
            self._daytona.delete(self._sandbox)
        self._sandbox = None
