from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

from pixelart.config import Profile


class ProviderError(RuntimeError):
    pass


class SubmissionRejected(ProviderError):
    """The request was not accepted, or failed locally before transmission."""


class SubmissionUnknown(ProviderError):
    """A request might have been accepted; never resubmit automatically."""


class Provider(Protocol):
    async def preflight(self, checkpoint: str, lora: str = "", vae: str = "") -> dict: ...
    async def validate(self, workflow_path: Path) -> None: ...
    async def submit(self, workflow_path: Path) -> str: ...
    async def status(self, job_id: str) -> dict: ...
    async def fetch(self, job_id: str, directory: Path) -> list[Path]: ...


@asynccontextmanager
async def connect(profile: Profile):
    if profile.provider == "local-mcp":
        from pixelart.providers.local_mcp import LocalMCP
        async with LocalMCP(profile) as provider:
            yield provider
    else:
        from pixelart.providers.comfy_http import ComfyHTTP
        yield ComfyHTTP(profile)


def find_value(data, key):
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = find_value(value, key)
            if found is not None:
                return found
    if isinstance(data, list):
        for value in data:
            found = find_value(value, key)
            if found is not None:
                return found
    return None


def job_state(data):
    values = []
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("status", "state", "status_str") and isinstance(item, str):
                    values.append(item.lower())
                elif isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(data)
    if any(v in ("failed", "failure", "error", "cancelled", "canceled", "interrupted") for v in values):
        return "failed"
    if any(v in ("completed", "complete", "success", "succeeded", "done") for v in values):
        return "completed"
    return "running"
