"""Runs one long task at a time (like "analyze 5,000 photos") in a background thread.

The UI polls GET /api/jobs/current to show a progress bar.
"""

import threading
import time
import traceback
from typing import Callable

_lock = threading.Lock()
_job: dict | None = None


class Progress:
    """Handed to the running task so it can report what it's doing."""

    def __init__(self, job: dict):
        self._job = job

    def phase(self, text: str, total: int = 0):
        self._job.update(phase=text, done=0, total=total)

    def step(self, n: int = 1):
        self._job["done"] += n


def current() -> dict | None:
    return dict(_job) if _job else None


def start(name: str, fn: Callable[[Progress], dict]) -> dict:
    """Start fn in the background. Raises RuntimeError if another job is still running."""
    global _job
    with _lock:
        if _job and _job["state"] == "running":
            raise RuntimeError("Another task is already running")
        _job = {
            "id": int(time.time() * 1000), "name": name, "state": "running",
            "phase": "Starting…", "done": 0, "total": 0, "result": None, "error": None,
        }
        job = _job

    def run():
        try:
            job["result"] = fn(Progress(job))
            job["state"] = "done"
        except Exception as e:
            traceback.print_exc()
            job.update(state="error", error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return dict(job)
