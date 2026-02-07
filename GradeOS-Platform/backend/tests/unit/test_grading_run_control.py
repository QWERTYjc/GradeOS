import asyncio

from redis.exceptions import RedisError

from src.services.grading_run_control import RedisGradingRunController


class _FakeRedis:
    def __init__(self, *, active_count: int = 0, queued_count: int = 0):
        self.active_count = active_count
        self.queued_count = queued_count
        self.pruned = False

    async def zremrangebyscore(self, *_args, **_kwargs):
        self.pruned = True
        return 0

    async def zcard(self, key: str):
        if ":active:" in key:
            return self.active_count
        return self.queued_count


class _FailRedis:
    async def zremrangebyscore(self, *_args, **_kwargs):
        raise RedisError("boom")


def test_get_teacher_capacity_success() -> None:
    fake = _FakeRedis(active_count=2, queued_count=5)
    controller = RedisGradingRunController(fake)  # type: ignore[arg-type]
    payload = asyncio.run(controller.get_teacher_capacity("teacher-1"))

    assert payload == {"active_count": 2, "queued_count": 5}
    assert fake.pruned is True


def test_get_teacher_capacity_failure_returns_zero() -> None:
    controller = RedisGradingRunController(_FailRedis())  # type: ignore[arg-type]
    payload = asyncio.run(controller.get_teacher_capacity("teacher-2"))

    assert payload == {"active_count": 0, "queued_count": 0}
