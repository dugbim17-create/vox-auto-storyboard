"""System doctor for `python -m app.cli doctor`.

Checks core dependencies (Python, FFmpeg, ffprobe, writable project dir) plus
optional providers (CLIProxy, FlowKit, OmniVoice, GPU). One failing provider
never crashes the whole report; core checks control the exit code.

Contracts:
- ``doctor_report.json`` written to ``config/discovered/``.
- exit code ``0`` when core deps are usable, non-zero otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # httpx is already installed in the runtime venv; degrade if missing.
    import httpx
except ImportError:  # pragma: no cover - fallback for a minimal env
    httpx = None  # type: ignore[assignment]

from datetime import UTC

from app import config

DISCOVERED_DIR = config.REPO_ROOT / "config" / "discovered"


@dataclass
class CheckResult:
    name: str
    status: str  # ok | missing | error | placeholder
    detail: Any = None
    message: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "message": self.message,
            "elapsed_ms": self.elapsed_ms,
        }


def _run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run a command, return (exit_code, trimmed stdout+stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, text.strip()
    except FileNotFoundError:
        return -1, "executable not found"
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout}s"


def _shutil_which(name: str) -> str | None:
    try:
        return shutil.which(name)
    except Exception:
        return None


def check_python() -> CheckResult:
    start = time.perf_counter()
    version = sys.version.split()[0]
    major, minor = (int(p) for p in version.split(".")[:2])
    ok = (major, minor) >= (3, 11)
    return CheckResult(
        name="python",
        status="ok" if ok else "error",
        detail={"version": version, "executable": sys.executable},
        message="" if ok else f"requires Python >= 3.11, found {version}",
        elapsed_ms=int((time.perf_counter() - start) * 1000),
    )


def check_executable(name: str, version_flag: str = "-version") -> CheckResult:
    start = time.perf_counter()
    configured = config.get(f"{name.upper()}_BIN") or name
    path = _shutil_which(configured) or (configured if Path(configured).is_file() else None)
    if path is None:
        return CheckResult(
            name=name,
            status="missing",
            detail={"configured": configured},
            message=f"{configured} not found on PATH",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    code, text = _run_cmd([path, version_flag])
    detail = {"path": path, "version_output": text.splitlines()[0] if text else ""}
    if code != 0:
        return CheckResult(
            name=name,
            status="error",
            detail=detail,
            message=f"{configured} exited {code}",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    return CheckResult(
        name=name,
        status="ok",
        detail=detail,
        message=f"{configured} at {path}",
        elapsed_ms=int((time.perf_counter() - start) * 1000),
    )


def check_project_dir() -> CheckResult:
    start = time.perf_counter()
    target = config.REPO_ROOT / "projects"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CheckResult(
            name="project_dir",
            status="ok",
            detail={"path": str(target)},
            message=f"{target} is writable",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - report any failure as status
        return CheckResult(
            name="project_dir",
            status="error",
            detail={"path": str(target)},
            message=str(exc),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )


def _http_get_json(url: str, timeout: float, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    if httpx is None:
        return -1, {"error": "httpx not installed"}
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers=headers)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {"_text": resp.text[:500]}
    except httpx.RequestError as exc:
        return -1, {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return -1, {"error": str(exc)}


def check_cliproxy() -> CheckResult:
    start = time.perf_counter()
    base = config.get("CLIPROXY_BASE_URL").rstrip("/")
    api_key = config.get("CLIPROXY_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key and not config.is_placeholder(api_key) else None
    models_url = f"{base}/models"
    code, body = _http_get_json(models_url, timeout=15, headers=headers)
    elapsed = int((time.perf_counter() - start) * 1000)
    if code == 200 and isinstance(body, dict):
        model_list = []
        for item in body.get("data") or []:
            if isinstance(item, dict) and item.get("id"):
                model_list.append(item["id"])
        return CheckResult(
            name="cliproxy",
            status="ok",
            detail={"base_url": base, "model_count": len(model_list), "models": model_list[:20]},
            message=f"models endpoint OK ({len(model_list)} models)",
            elapsed_ms=elapsed,
        )
    if code == 200:
        # Non-dict payload still proves the endpoint answers.
        return CheckResult(
            name="cliproxy",
            status="ok",
            detail={"base_url": base, "response": body},
            message="models endpoint answered (non-dict payload)",
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="cliproxy",
        status="error",
        detail={"base_url": base, "http_code": code, "body": body},
        message=f"models endpoint failed (http {code})",
        elapsed_ms=elapsed,
    )


def check_flowkit() -> CheckResult:
    start = time.perf_counter()
    base = config.get("FLOWKIT_BASE_URL").rstrip("/")
    # Try common health paths; first hit wins.
    for path in ("/health", "/healthz", "/api/health", "/"):
        url = f"{base}{path}"
        try:
            if httpx is None:
                return CheckResult(name="flowkit", status="error", detail={}, message="httpx not installed", elapsed_ms=int((time.perf_counter() - start) * 1000))
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code < 500:
                return CheckResult(
                    name="flowkit",
                    status="ok",
                    detail={"base_url": base, "path": path, "http_code": resp.status_code},
                    message=f"responded {resp.status_code} at {path}",
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                )
        except Exception:
            continue
    return CheckResult(
        name="flowkit",
        status="error",
        detail={"base_url": base},
        message="no health path responded (tried /health, /healthz, /api/health, /)",
        elapsed_ms=int((time.perf_counter() - start) * 1000),
    )


def check_omnivoice() -> CheckResult:
    start = time.perf_counter()
    host = config.get("OMNIVOICE_WORKER_HOST") or "127.0.0.1"
    port = config.get("OMNIVOICE_WORKER_PORT") or "8791"
    health_url = f"http://{host}:{port}/health"
    code, body = _http_get_json(health_url, timeout=5)
    if code == 200 and isinstance(body, dict) and body.get("status") == "ok":
        return CheckResult(
            name="omnivoice",
            status="ok",
            detail={"health_url": health_url, **body},
            message="OmniVoice worker health OK",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    configured = config.get("OMNIVOICE_VENV_PYTHON")
    if not configured or config.is_placeholder(configured):
        return CheckResult(
            name="omnivoice",
            status="placeholder",
            detail={"configured": configured, "health_url": health_url, "health": body},
            message="OmniVoice worker unavailable; Python configuration is placeholder",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    py = Path(configured)
    if not py.is_file():
        return CheckResult(
            name="omnivoice",
            status="error",
            detail={"configured": configured, "health_url": health_url, "health": body},
            message=f"OmniVoice worker unavailable; Python not found: {configured}",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    py_code, text = _run_cmd([str(py), "--version"])
    if py_code != 0:
        return CheckResult(
            name="omnivoice",
            status="error",
            detail={"configured": configured},
            message=f"venv python failed: {text[:200]}",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    return CheckResult(
        name="omnivoice",
        status="error",
        detail={
            "venv_python": configured,
            "version": text.strip(),
            "health_url": health_url,
            "health": body,
        },
        message=f"OmniVoice Python is configured but worker is unavailable at {health_url}",
        elapsed_ms=int((time.perf_counter() - start) * 1000),
    )


def _torch_runtime_info() -> Any | None:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return None
    return torch


def check_gpu() -> CheckResult:
    start = time.perf_counter()
    try:
        torch = _torch_runtime_info()
        if torch is None:
            if getattr(sys, "frozen", False):
                return CheckResult(
                    name="gpu",
                    status="not_required",
                    detail={"note": "torch intentionally not bundled"},
                    message="GPU probe not bundled; not required for configured remote providers",
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                )
            return CheckResult(
                name="gpu",
                status="missing",
                detail={"note": "torch not installed in this venv"},
                message="torch not installed — GPU check skipped",
                elapsed_ms=int((time.perf_counter() - start) * 1000),
            )
        cuda_available = bool(torch.cuda.is_available())
        name = torch.cuda.get_device_name(0) if cuda_available else None
        return CheckResult(
            name="gpu",
            status="ok" if cuda_available else "missing",
            detail={"cuda_available": cuda_available, "device_name": name, "torch": torch.__version__},
            message=f"CUDA {'available' if cuda_available else 'not available'}; torch {torch.__version__}",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="gpu",
            status="error",
            detail={"load_error": str(exc)[:400]},
            message="torch installed but failed to load (native lib/VC runtime issue)",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )


def run_all() -> dict[str, Any]:
    """Run every check; never raises. Returns the full report."""
    results = [
        check_python(),
        check_executable("ffmpeg"),
        check_executable("ffprobe"),
        check_project_dir(),
        check_cliproxy(),
        check_flowkit(),
        check_omnivoice(),
        check_gpu(),
    ]
    core = ["python", "ffmpeg", "ffprobe", "project_dir"]
    core_ok = all(r.status == "ok" for r in results if r.name in core)
    report = {
        "report_version": 1,
        "generated_at": _iso_now(),
        "runtime": {"platform": sys.platform, "cwd": str(config.REPO_ROOT)},
        "core_ok": core_ok,
        "checks": [r.to_dict() for r in results],
    }
    return report


def _iso_now() -> str:
    try:
        from datetime import datetime

        return datetime.now(UTC).isoformat()
    except Exception:  # pragma: no cover
        return str(time.time())


def write_report(report: dict[str, Any], target: Path | None = None) -> Path:
    target = target or (DISCOVERED_DIR / "doctor_report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def doctor_main() -> int:
    """CLI entry: print report, persist it, return exit code."""
    report = run_all()
    report_path = write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[doctor] report written to {report_path}")
    return 0 if report["core_ok"] else 1
