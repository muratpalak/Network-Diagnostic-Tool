"""Safe subprocess execution and time measurement helpers."""

from __future__ import annotations

import subprocess
import time
from typing import Sequence


def run_command(args: Sequence[str], timeout: float = 5.0) -> dict:
    """Run a fixed-argument command without a shell and return its result.

    Keeping shell=False means diagnostic targets cannot inject shell commands.
    """
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(args), capture_output=True, text=True, errors="replace",
            check=False, timeout=timeout, shell=False,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr.strip(),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False, "stdout": "", "stderr": "Command timed out",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except (OSError, ValueError) as exc:
        return {
            "ok": False, "stdout": "", "stderr": str(exc),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
