import asyncio
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as HTTPRequest, HTTPRedirectHandler, build_opener

from pixelart.config import Profile
from pixelart.providers.base import ProviderError, SubmissionRejected, SubmissionUnknown, job_state
from pixelart.providers.local_mcp import CORE_NODES, OPTIONAL_NODES, required_nodes


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Fixed API targets must never forward credentials or rewrite POST into GET.
        return None


class ComfyHTTP:
    """Self-hosted ComfyUI HTTP API. This is not the managed Comfy Cloud API."""

    def __init__(self, profile: Profile):
        self.profile = profile
        self.base = profile.url.rstrip("/")

    async def request(self, route, payload=None, binary=False):
        def send():
            headers = {}
            if self.profile.token_env:
                token = os.environ.get(self.profile.token_env)
                if not token:
                    error = SubmissionRejected if route == "/prompt" and payload is not None else ProviderError
                    raise error("missing token environment variable: " + self.profile.token_env)
                headers["Authorization"] = "Bearer " + token
            body = None
            if payload is not None:
                headers["Content-Type"] = "application/json"
                body = json.dumps(payload).encode()
            request = HTTPRequest(self.base + route, data=body, headers=headers)
            try:
                with build_opener(NoRedirect()).open(request, timeout=30) as response:
                    value = response.read()
            except HTTPError as exc:
                code = exc.code
                exc.close()
                error = SubmissionRejected if route == "/prompt" and payload is not None and 400 <= code < 500 else ProviderError
                raise error(f"ComfyUI HTTP {code}: check target, authentication and workflow") from exc
            except URLError as exc:
                raise ProviderError("ComfyUI network failure; verify target connectivity") from exc
            return value if binary else json.loads(value)
        return await asyncio.to_thread(send)

    async def preflight(self, checkpoint: str, lora: str = "", vae: str = ""):
        await self.request("/system_stats")
        names = await self.request("/models/checkpoints")
        if not isinstance(names, list) or not names:
            raise ProviderError("no checkpoint found on the remote target")
        if checkpoint and checkpoint not in names:
            raise ProviderError("checkpoint not available on target: " + checkpoint)
        for folder, filename in (("loras", lora), ("vae", vae)):
            if filename and filename not in await self.request("/models/" + folder):
                raise ProviderError(f"{folder} file not available on target: {filename}")
        for name in sorted(required_nodes(lora, vae)):
            node = await self.request("/object_info/" + name)
            if name not in node:
                raise ProviderError("target is missing node: " + name)
        return {"checkpoint": checkpoint or names[0], "checkpoints": names, "provider": "comfy-http", "lora": lora, "vae": vae}

    async def validate(self, workflow_path: Path):
        graph = json.loads(workflow_path.read_text(encoding="utf-8"))
        if {node.get("class_type") for node in graph.values()} - (CORE_NODES | OPTIONAL_NODES):
            raise ProviderError("this prototype accepts only its known, local core-node graph")
        # Full schema validation also happens at the target's /prompt endpoint.

    async def submit(self, workflow_path: Path):
        graph = json.loads(workflow_path.read_text(encoding="utf-8"))
        try:
            response = await self.request("/prompt", {"prompt": graph})
        except SubmissionRejected:
            raise
        except Exception as exc:
            raise SubmissionUnknown("remote submission unconfirmed; check history before resubmitting") from exc
        if not response.get("prompt_id"):
            if response.get("error") or response.get("node_errors"):
                raise SubmissionRejected("remote target rejected the workflow")
            raise SubmissionUnknown("remote submission response has no prompt_id")
        return response["prompt_id"]

    async def status(self, job_id: str):
        from urllib.parse import quote
        history = await self.request("/history/" + quote(job_id, safe=""))
        record = history.get(job_id)
        return {"state": job_state(record) if record else "running", "payload": record or {}}

    async def fetch(self, job_id: str, directory: Path):
        from urllib.parse import quote
        history = await self.request("/history/" + quote(job_id, safe=""))
        record = history.get(job_id, {})
        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        for output in record.get("outputs", {}).values():
            for entry in output.get("images", []):
                if entry.get("type") != "output":
                    continue
                query = urlencode({k: entry.get(k, "") for k in ("filename", "subfolder", "type")})
                value = await self.request("/view?" + query, binary=True)
                # Server-provided names never become local paths.
                path = directory / f"image-{len(paths):03d}.png"
                temporary = path.with_suffix(".part")
                temporary.write_bytes(value)
                temporary.replace(path)
                paths.append(path)
        if not paths:
            raise ProviderError("remote job has no output images")
        return paths
