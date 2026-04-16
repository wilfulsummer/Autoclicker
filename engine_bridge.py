import json
import os
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from runtime_paths import bundled_path


ENGINE_EXE_CANDIDATES = [
    bundled_path("engine", "publish", "AutoClicker.Engine.exe"),
    bundled_path("engine", "AutoClicker.Engine", "bin", "Release", "net8.0-windows", "AutoClicker.Engine.exe"),
]
ENGINE_DLL_CANDIDATES = [
    bundled_path("engine", "publish", "AutoClicker.Engine.dll"),
    bundled_path("engine", "AutoClicker.Engine", "bin", "Release", "net8.0-windows", "AutoClicker.Engine.dll"),
]
LOCAL_DOTNET = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "dotnet" / "dotnet.exe"
SYSTEM_DOTNET = Path(r"C:\Program Files\dotnet\dotnet.exe")


@dataclass
class EngineConfig:
    interval_ms: float
    button: str
    double_click: bool
    jitter_enabled: bool
    jitter_radius_px: int
    random_interval_offset_min_ms: int
    random_interval_offset_max_ms: int
    high_precision_timing: bool
    process_priority_boost: bool
    precision_mode: bool


class EngineBridge:
    def __init__(self, on_message: Callable[[dict], None] | None = None) -> None:
        self.on_message = on_message
        self.process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._ready_event = threading.Event()

    @property
    def available(self) -> bool:
        return self._launch_command() is not None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start_process(self) -> bool:
        if self.running:
            return True
        command = self._launch_command()
        if command is None:
            return False
        self._ready_event.clear()
        creationflags = 0
        startupinfo = None
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        if self._ready_event.wait(timeout=1.5):
            return True
        self.shutdown()
        return False

    def configure(self, config: EngineConfig) -> None:
        payload = asdict(config)
        self._send(
            {
                "type": "configure",
                "intervalMs": payload["interval_ms"],
                "button": payload["button"],
                "doubleClick": payload["double_click"],
                "jitterEnabled": payload["jitter_enabled"],
                "jitterRadiusPx": payload["jitter_radius_px"],
                "randomIntervalOffsetMinMs": payload["random_interval_offset_min_ms"],
                "randomIntervalOffsetMaxMs": payload["random_interval_offset_max_ms"],
                "highPrecisionTiming": payload["high_precision_timing"],
                "processPriorityBoost": payload["process_priority_boost"],
                "precisionMode": payload["precision_mode"],
            }
        )

    def start_clicking(self) -> None:
        self._send({"type": "start"})

    def stop_clicking(self) -> None:
        self._send({"type": "stop"})

    def shutdown(self) -> None:
        self._ready_event.clear()
        if not self.running:
            return
        self._send({"type": "shutdown"})
        if self.process:
            try:
                self.process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def _send(self, payload: dict) -> None:
        if not self.running or not self.process or not self.process.stdin:
            return
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def _reader_loop(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for raw_line in self.process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                message = {"type": "log", "message": line}
            if message.get("type") == "ready":
                self._ready_event.set()
            if self.on_message:
                self.on_message(message)

    def _launch_command(self) -> list[str] | None:
        engine_dll = next((candidate for candidate in ENGINE_DLL_CANDIDATES if candidate.exists()), None)
        if engine_dll is not None:
            dotnet_path = self._dotnet_host_path()
            if dotnet_path is not None:
                return [str(dotnet_path), str(engine_dll)]
        engine_exe = next((candidate for candidate in ENGINE_EXE_CANDIDATES if candidate.exists()), None)
        if engine_exe is not None:
            return [str(engine_exe)]
        return None

    @staticmethod
    def _dotnet_host_path() -> Path | None:
        for candidate in (LOCAL_DOTNET, SYSTEM_DOTNET):
            if candidate.exists():
                return candidate
        return None
