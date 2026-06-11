from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen

from anime_workflow.launcher.config import effective_comfyui_base_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
D_COMFYUI_DIR = Path("/mnt/d/Codex/ai-anime-workflow/ComfyUI")
D_COMFYUI_VENV = Path("/mnt/d/Codex/ai-anime-workflow/comfyui-venv")


def display_path(path: Path) -> str:
    return Path(path).as_posix()


def tail_file(path: Path, lines: int = 120) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


class ComfyUIService:
    def __init__(
        self,
        project_root: Path = PROJECT_ROOT,
        comfyui_dir: Path = D_COMFYUI_DIR,
        comfyui_venv: Path = D_COMFYUI_VENV,
        popen_factory: Callable[..., subprocess.Popen[Any]] = subprocess.Popen,
    ) -> None:
        self.project_root = Path(project_root)
        self.comfyui_dir = Path(comfyui_dir)
        self.comfyui_venv = Path(comfyui_venv)
        self.popen_factory = popen_factory
        self.work_dir = self.project_root / "work"
        self.pid_file = self.work_dir / "comfyui.pid"
        self.log_file = self.work_dir / "comfyui.log"

    def start(self) -> dict[str, Any]:
        if self.is_running():
            return {"status": "already_running", "pid": self._read_pid()}
        self.work_dir.mkdir(parents=True, exist_ok=True)
        command = [
            display_path(self.comfyui_venv / "bin/python"),
            "main.py",
            "--cpu",
            "--listen",
            "127.0.0.1",
            "--port",
            "8188",
        ]
        with self.log_file.open("a", encoding="utf-8") as log:
            process = self.popen_factory(
                command,
                cwd=display_path(self.comfyui_dir),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.pid_file.write_text(str(process.pid), encoding="utf-8")
        return {"status": "started", "pid": process.pid}

    def stop(self) -> dict[str, Any]:
        pid = self._read_pid()
        if not pid:
            return {"status": "not_running"}
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if self.pid_file.exists():
            self.pid_file.unlink()
        return {"status": "stopped", "pid": pid}

    def is_running(self) -> bool:
        pid = self._read_pid()
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False

    def status(self, base_url: str = "http://127.0.0.1:8188", mode: str = "local") -> dict[str, Any]:
        api = check_http_json(f"{base_url.rstrip('/')}/system_stats")
        is_local = mode != "remote"
        return {
            "mode": mode,
            "base_url": base_url,
            "process_running": self.is_running() if is_local else False,
            "pid": self._read_pid() if is_local else None,
            "api_running": api["ok"],
            "api_detail": api["detail"],
            "log_tail": tail_file(self.log_file, 80) if is_local else "",
        }

    def _read_pid(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None


def check_http_json(url: str, timeout: int = 2) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(800).decode("utf-8", errors="replace")
        return {"ok": True, "detail": body}
    except URLError as exc:
        return {"ok": False, "detail": str(exc)}


def environment_status(config: dict[str, Any]) -> dict[str, Any]:
    comfy_mode = str(config.get("comfyui_mode") or "local")
    comfy = ComfyUIService().status(effective_comfyui_base_url(config), mode=comfy_mode)
    ollama = check_http_json("http://127.0.0.1:11434/api/tags")
    return {
        "python": {"ok": True},
        "ffmpeg": {"ok": shutil.which("ffmpeg") is not None, "path": shutil.which("ffmpeg") or ""},
        "ollama": {"ok": ollama["ok"], "detail": ollama["detail"]},
        "comfyui": comfy,
        "openai": {"configured": bool(config.get("openai_api_key"))},
        "paths": {
            "comfyui_dir": display_path(D_COMFYUI_DIR),
            "comfyui_venv": display_path(D_COMFYUI_VENV),
            "ollama_models": "/mnt/d/Codex/ai-anime-workflow/ollama-models",
            "output_dir": str(PROJECT_ROOT / config.get("output_dir", "data/exports")),
        },
        "disk": disk_status(),
    }


def disk_status() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in ["/mnt/c", "/mnt/d"]:
        usage = shutil.disk_usage(path)
        result[path] = {
            "total_gb": round(usage.total / 1024**3, 1),
            "used_gb": round(usage.used / 1024**3, 1),
            "free_gb": round(usage.free / 1024**3, 1),
        }
    return result


def ollama_models() -> list[dict[str, Any]]:
    data = check_http_json("http://127.0.0.1:11434/api/tags")
    if not data["ok"]:
        return []
    try:
        return json.loads(data["detail"]).get("models", [])
    except json.JSONDecodeError:
        return []
