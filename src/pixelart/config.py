from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import ipaddress
import json
import os
import platform
import shutil


@dataclass
class Profile:
    id: str = "local"
    provider: str = "local-mcp"
    command: str = "comfy-mcp"
    args: list[str] = field(default_factory=list)
    env_refs: dict[str, str] = field(default_factory=dict)
    url: str = ""
    token_env: str = ""

    def __post_init__(self):
        if self.provider not in ("local-mcp", "comfy-http"):
            raise ValueError("provider must be local-mcp or comfy-http; managed cloud needs its own adapter")
        if self.provider == "comfy-http":
            url = urlsplit(self.url)
            if url.scheme not in ("http", "https") or not url.hostname:
                raise ValueError("remote profile requires an http(s) URL")
            if url.username or url.password or url.query or url.fragment:
                raise ValueError("put authentication in token_env, not in the URL")
            try:
                loopback = ipaddress.ip_address(url.hostname).is_loopback
            except ValueError:
                loopback = url.hostname.lower() == "localhost"
            if self.token_env and url.scheme != "https" and not loopback:
                raise ValueError("authenticated remote targets require HTTPS or a loopback tunnel")
        if not self.id.strip():
            raise ValueError("profile id must not be empty")

    @classmethod
    def load(cls, path: Path | None):
        if path is None:
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    def environment(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        for target, source in self.env_refs.items():
            if source not in os.environ:
                raise ValueError(f"missing environment variable: {source}")
            env[target] = os.environ[source]
        # The CLI wrapper must be available even when MCP inherits a minimal PATH.
        if self.provider == "local-mcp" and "COMFY_BIN" not in env:
            executable = shutil.which("comfy")
            if executable:
                env["COMFY_BIN"] = executable
        return env

    def fingerprint(self):
        # Machine executable paths and credentials must not enter a portable project.
        identity = {"id": self.id, "provider": self.provider, "url": self.url.rstrip("/")}
        if self.provider == "local-mcp":
            identity["machine"] = platform.node()
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
