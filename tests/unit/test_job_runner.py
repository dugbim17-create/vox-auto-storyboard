"""Tests for the P1-T05 in-process async job runner."""

from __future__ import annotations

import asyncio

from app.core.job_runner import Job, JobRunner, JobStatus


async def _ok() -> str:
    await asyncio.sleep(0.01)
    return "done"


async def _boom() -> str:
    await asyncio.sleep(0.01)
    raise RuntimeError("boom")


async def _slow() -> str:
    await asyncio.sleep(5)
    return "late"


def _mk(job_id: str, fn, **kw) -> Job:
    return Job(job_id=job_id, provider="test", fn=fn, max_attempts=kw.pop("max_attempts", 1), **kw)


async def test_success() -> None:
    runner = JobRunner()
    job = _mk("j1", _ok)
    await runner.submit(job)
    await runner.wait("j1")
    assert job.status == JobStatus.SUCCEEDED
    assert job.result == "done"


async def test_retry_then_success() -> None:
    calls: dict[str, int] = {}

    async def _flaky() -> str:
        calls["n"] = calls.get("n", 0) + 1
        if calls["n"] < 2:
            raise RuntimeError("flaky")
        return "recovered"

    runner = JobRunner()
    job = Job(job_id="jf", provider="p", fn=_flaky, max_attempts=3, retry_delay_seconds=0.01)
    await runner.submit(job)
    await runner.wait("jf")
    assert job.status == JobStatus.SUCCEEDED
    assert job.result == "recovered"
    assert job.attempts == 2


async def test_cancellation() -> None:
    runner = JobRunner()
    job = Job(job_id="jc", provider="p", fn=_slow, max_attempts=1, timeout_seconds=60)
    await runner.submit(job)
    await asyncio.sleep(0.05)
    runner.cancel("jc")
    await runner.wait("jc")
    assert job.status == JobStatus.CANCELLED


async def test_timeout() -> None:
    runner = JobRunner()
    job = Job(job_id="jt", provider="p", fn=_slow, max_attempts=1, timeout_seconds=0.1)
    await runner.submit(job)
    await runner.wait("jt")
    assert job.status == JobStatus.TIMED_OUT


async def test_failed_does_not_stop_queue() -> None:
    runner = JobRunner()
    bad = Job(job_id="b1", provider="p", fn=_boom, max_attempts=1)
    good = Job(job_id="g1", provider="p", fn=_ok, max_attempts=1)
    await runner.submit(bad)
    await runner.submit(good)
    await asyncio.gather(runner.wait("b1"), runner.wait("g1"))
    assert bad.status == JobStatus.FAILED
    assert good.status == JobStatus.SUCCEEDED


async def test_concurrency_limit() -> None:
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def work() -> None:
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.03)
        async with lock:
            active -= 1

    runner = JobRunner()
    jobs = [Job(job_id=f"c{i}", provider="io", fn=work, max_attempts=1) for i in range(5)]
    for j in jobs:
        await runner.submit(j, concurrency_limit=2)
    await asyncio.gather(*[runner.wait(j.job_id) for j in jobs])
    assert peak <= 2
