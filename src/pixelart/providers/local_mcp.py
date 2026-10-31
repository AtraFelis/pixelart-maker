from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
import json
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pixelart.config import Profile
from pixelart.providers.base import ProviderError, SubmissionUnknown, find_value, job_state

CORE_NODES = {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"}
OPTIONAL_NODES = {"LoraLoader", "VAELoader"}


def required_nodes(lora="", vae=""):
    return CORE_NODES | ({"LoraLoader"} if lora else set()) | ({"VAELoader"} if vae else set())


def normalize_result(result):
    if result.isError:
        texts = [item.text for item in result.content if getattr(item, "type", "") == "text"]
        raise ProviderError("MCP tool error: " + "\n".join(texts)[:1500])
    data = result.structuredContent
    if data is None:
        for block in result.content:
            if getattr(block, "type", "") == "text":
                try:
                    data = json.loads(block.text)
                    break
                except json.JSONDecodeError:
                    continue
    if data is None:
        raise ProviderError("MCP returned no JSON result")
    # Some comfy-cli versions return an envelope, others return the payload.
    if isinstance(data, dict) and data.get("ok") is False:
        raise ProviderError("Comfy tool rejected the request")
    if isinstance(data, dict) and "data" in data and ("ok" in data or "schema" in data):
        return data["data"]
    return data


class LocalMCP:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.stack = AsyncExitStack()
        self.session = None
        self.tools = {}

    async def __aenter__(self):
        command = shutil.which(self.profile.command) or self.profile.command
        try:
            read, write = await self.stack.enter_async_context(stdio_client(
                StdioServerParameters(command=command, args=self.profile.args, env=self.profile.environment())
            ))
            self.session = await self.stack.enter_async_context(
                ClientSession(read, write, read_timeout_seconds=timedelta(seconds=90))
            )
            await self.session.initialize()
            cursor = None
            while True:
                page = await self.session.list_tools(cursor=cursor)
                self.tools.update({tool.name: tool for tool in page.tools})
                cursor = page.nextCursor
                if not cursor:
                    break
            required = {"server_info", "search_models", "nodes", "validate_workflow", "run_workflow", "job", "fetch_outputs"}
            if not required.issubset(self.tools):
                raise ProviderError("MCP is missing required tools: " + ", ".join(sorted(required - self.tools.keys())))
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        return await self.stack.__aexit__(*args)

    async def call(self, name, arguments):
        return normalize_result(await self.session.call_tool(name, arguments=arguments))

    async def preflight(self, checkpoint: str, lora: str = "", vae: str = ""):
        info = await self.call("server_info", {})
        url = info.get("server", {}).get("url", "")
        if not info.get("server", {}).get("running"):
            raise ProviderError("ComfyUI is not running")
        target = info.get("comfy_target", {})
        host = target.get("host") if isinstance(target, dict) else None
        if urlsplit(url).hostname not in ("localhost", "127.0.0.1", "::1") or host not in (None, "localhost", "127.0.0.1", "::1"):
            raise ProviderError("local-mcp points to a remote target; use a comfy-http profile for target-aware validation")
        models = await self.call("search_models", {"folder": "checkpoints"})
        names = [item["name"] for item in models.get("files", [])]
        if checkpoint and checkpoint not in names:
            raise ProviderError("checkpoint not available on target: " + checkpoint)
        if not names:
            raise ProviderError("no checkpoint found on target")
        for folder, filename in (("loras", lora), ("vae", vae)):
            if filename:
                catalog = await self.call("search_models", {"folder": folder})
                if filename not in [item["name"] for item in catalog.get("files", [])]:
                    raise ProviderError(f"{folder} file not available on target: {filename}")
        # Check only the core nodes this request actually uses. Never install nodes here.
        for name in sorted(required_nodes(lora, vae)):
            node = await self.call("nodes", {"action": "get", "name": name})
            if node.get("id") != name or node.get("is_api_node"):
                raise ProviderError("missing or unsuitable node: " + name)
        return {
            "checkpoint": checkpoint or names[0], "checkpoints": names,
            "server": url, "comfy_version": info.get("freshness", {}).get("core", {}).get("installed"),
            "provider": self.profile.provider, "lora": lora, "vae": vae,
        }

    async def validate(self, workflow_path: Path):
        report = await self.call("validate_workflow", {"workflow_path": str(workflow_path.resolve())})
        if report.get("valid") is not True:
            raise ProviderError("workflow validation failed: " + json.dumps(report, ensure_ascii=False)[:1200])

    async def submit(self, workflow_path: Path):
        try:
            result = await self.call("run_workflow", {
                "workflow_path": str(workflow_path.resolve()), "wait": False, "confirm_spend": False,
            })
        except Exception as exc:
            raise SubmissionUnknown("submission did not return a job id; inspect the server before starting a new job") from exc
        job_id = find_value(result, "prompt_id")
        if not isinstance(job_id, str) or not job_id:
            raise SubmissionUnknown("submission response has no prompt_id; inspect the server before resubmitting")
        return job_id

    async def status(self, job_id: str):
        payload = await self.call("job", {"action": "status", "prompt_id": job_id})
        return {"state": job_state(payload), "payload": payload}

    async def fetch(self, job_id: str, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        await self.call("fetch_outputs", {
            "prompt_id": job_id, "out_dir": str(directory.resolve()), "inline_images": False,
        })
        files = sorted(directory.rglob("*.png"))
        if not files:
            raise ProviderError("completed job has no downloaded PNG outputs")
        return files
