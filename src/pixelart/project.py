from datetime import datetime, timezone
from pathlib import Path
import json
import uuid


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class Project:
    def __init__(self, root: Path, manifest: dict):
        self.root = root.resolve()
        self.manifest = manifest

    @classmethod
    def create(cls, root: Path, request: dict):
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=False)
        manifest = {
            "format_version": 1,
            "id": uuid.uuid4().hex,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "created",
            "request": request,
            "assets": {},
            "quality": "not_reviewed",
        }
        project = cls(root, manifest)
        project.save()
        return project

    @classmethod
    def open(cls, root: Path):
        root = root.resolve()
        manifest = json.loads((root / "project.json").read_text(encoding="utf-8"))
        if manifest.get("format_version") != 1:
            raise ValueError("unsupported project format")
        project = cls(root, manifest)
        for name in manifest.get("assets", {}).values():
            project.asset(name)
        return project

    def asset(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(self.root):
            raise ValueError("asset path must stay inside the project")
        return path

    def save(self):
        write_json(self.root / "project.json", self.manifest)

    def update(self, state: str, **values):
        self.manifest.update(values)
        self.manifest["state"] = state
        self.save()

    def add_asset(self, name: str, path: Path):
        self.manifest["assets"][name] = path.resolve().relative_to(self.root).as_posix()
        self.save()
