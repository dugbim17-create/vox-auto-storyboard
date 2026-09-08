"""In-process async job runner (MASTER_PLAN section P1-T05).

A minimal async queue with:
- per-provider max concurrency;
- cancellation;
- retry with backoff;
- timeout;
- heartbeat.
It is intentionally not a distributed queue (no Redis/Celery) for the MVP.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

JobFn = Callable[..., Awaitable[Any]]


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class Job:
    job_id: str
    provider: str
    fn: JobFn
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: float = 300.0
    retry_delay_seconds: float = 1.0
    error: str = ""
    result: Any = None
    created_at: float = field(default_factory=time.monotonic)
    started_at: float = 0.0
    finished_at: float = 0.0
    heartbeat_at: float = 0.0
    cancelled: bool = False

    @property
    def elapsed(self) -> float:
        return (self.finished_at or time.monotonic()) - (self.started_at or self.created_at)


class JobRunner:
    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._jobs: dict[str, Job] = {}

    def _semaphore(self, provider: str, limit: int) -> asyncio.Semaphore:
        if provider not in self._semaphores:
            self._semaphores[provider] = asyncio.Semaphore(max(1, limit))
        return self._semaphores[provider]

    async def submit(
        self,
        job: Job,
        *,
        concurrency_limit: int = 1,
    ) -> Job:
        """Submit a job for execution, returning the tracked Job."""
        self._jobs[job.job_id] = job
        sem = self._semaphore(job.provider, concurrency_limit)
        task = asyncio.create_task(self._run(job, sem))
        self._tasks[job.job_id] = task
        return job

    async def _run(self, job: Job, sem: asyncio.Semaphore) -> None:
        async with sem:
            while job.attempts < job.max_attempts and not job.cancelled:
                job.attempts += 1
                job.status = JobStatus.RUNNING
                job.started_at = time.monotonic()
                job.heartbeat_at = job.started_at
                try:
                    job.result = await asyncio.wait_for(
                        self._heartbeating(job, job.fn(*job.args, **job.kwargs)),
                        timeout=job.timeout_seconds,
                    )
                    job.status = JobStatus.SUCCEEDED
                    break
                except asyncio.CancelledError:
                    job.status = JobStatus.CANCELLED
                    job.cancelled = True
                    break
                except TimeoutError:
                    job.status = JobStatus.TIMED_OUT
                    job.error = f"timed out after {job.timeout_seconds}s"
                except Exception as exc:  # noqa: BLE001
                    job.error = f"{type(exc).__name__}: {exc}"
                    job.status = JobStatus.FAILED
                finally:
                    job.finished_at = time.monotonic()
                # retry with backoff unless cancelled or exhausted
                if job.status in (JobStatus.FAILED, JobStatus.TIMED_OUT) and job.attempts < job.max_attempts and not job.cancelled:
                    await asyncio.sleep(job.retry_delay_seconds * job.attempts)
        if job.status not in (JobStatus.SUCCEEDED, JobStatus.CANCELLED):
            if job.cancelled:
                job.status = JobStatus.CANCELLED
            elif job.attempts >= job.max_attempts:
                job.status = job.status  # keep FAILED/TIMED_OUT

    @staticmethod
    async def _heartbeating(job: Job, coro: Awaitable[Any]) -> Any:
        """Touch the heartbeat while awaiting; re-raises the coro's outcome."""
        result_holder: dict[str, Any] = {}

        async def _tick() -> None:
            while True:
                job.heartbeat_at = time.monotonic()
                await asyncio.sleep(0.5)

        ticker = asyncio.create_task(_tick())
        try:
            result_holder["value"] = await coro
            return result_holder["value"]
        finally:
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.cancelled = True
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        return True

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def pending_jobs(self) -> list[Job]:
        return [j for j in self._jobs.values() if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]

    async def wait(self, job_id: str, timeout: float | None = None) -> Job:
        task = self._tasks.get(job_id)
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout) if timeout else await task
        return self._jobs[job_id]

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        for task in self._tasks.values():
            with contextlib.suppress(asyncio.CancelledError):
                await task
