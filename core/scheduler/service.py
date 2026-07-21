import asyncio
import logging
import time

logger = logging.getLogger(__name__)

class SchedulerService:
    """Runs a publication cycle periodically without overlapping executions."""
    def __init__(self, cycle, interval_seconds=1800):
        self.cycle = cycle; self.interval_seconds = float(interval_seconds); self._running = False

    async def tick(self):
        if self._running:
            logger.info("scheduler_tick skipped=overlap"); return False
        self._running = True; started = time.perf_counter(); logger.info("scheduler_tick"); logger.info("cycle_started")
        try:
            await self.cycle(); logger.info("cycle_finished"); return True
        except Exception:
            logger.exception("cycle_failed"); return False
        finally:
            logger.info("cycle_duration_ms=%d", int((time.perf_counter()-started)*1000)); self._running = False

    async def run_once(self):
        logger.info("scheduler_started"); return await self.tick()

    async def serve(self):
        logger.info("scheduler_started")
        while True:
            await self.tick(); await asyncio.sleep(self.interval_seconds)
