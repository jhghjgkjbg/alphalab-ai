import asyncio
import unittest
from datetime import UTC, datetime, timedelta

from core.ai_gateway.rate_limit import InMemoryRateLimiter, RateLimitConfig


class RateLimitTests(unittest.TestCase):
    def test_limits_windows_disabled_and_release(self):
        now = [datetime(2024, 1, 1, tzinfo=UTC)]; clock = lambda: now[0]
        async def run():
            limiter = InMemoryRateLimiter(RateLimitConfig(1, 2, 1), clock); self.assertTrue((await limiter.acquire()).allowed); self.assertEqual((await limiter.acquire()).reason, "concurrency_limit_exceeded"); await limiter.release(); self.assertEqual((await limiter.acquire()).reason, "minute_limit_exceeded"); now[0] += timedelta(minutes=1, seconds=1); self.assertTrue((await limiter.acquire()).allowed); await limiter.reset(); self.assertEqual((await limiter.inspect()).minute_count, 0); await limiter.release(); await limiter.release(); self.assertEqual((await limiter.inspect()).active_requests, 0)
        asyncio.run(run())

    def test_hour_and_disabled(self):
        async def run():
            limiter = InMemoryRateLimiter(RateLimitConfig(10, 0, 2)); self.assertEqual((await limiter.acquire()).reason, "hour_limit_exceeded"); disabled = InMemoryRateLimiter(RateLimitConfig(0, 0, 0, False)); self.assertTrue((await disabled.acquire()).allowed)
        asyncio.run(run())

    def test_concurrent_access(self):
        async def run():
            limiter = InMemoryRateLimiter(RateLimitConfig(100, 100, 3)); results = await asyncio.gather(*(limiter.acquire() for _ in range(10))); self.assertEqual(sum(r.allowed for r in results), 3)
        asyncio.run(run())


if __name__ == "__main__": unittest.main()
