from datetime import UTC, datetime, timedelta

class AdaptivePublicationScheduler:
    """Deterministic gate for immediate publication; scheduled runs remain fallback."""
    def __init__(self, high_priority_score: float = 90.0, cooldown_minutes: float = 30.0, clock=None):
        self.high_priority_score = float(high_priority_score)
        self.cooldown = timedelta(minutes=max(0.0, float(cooldown_minutes)))
        self._last_immediate = None
        self._clock = clock or (lambda: datetime.now(UTC))
    def select_immediate(self, candidates):
        now = self._clock()
        if self._last_immediate is not None and now - self._last_immediate < self.cooldown:
            return None
        eligible = [c for c in candidates if float(getattr(c, "final_score", getattr(c, "score", 0.0))) >= self.high_priority_score]
        if not eligible: return None
        winner = max(eligible, key=lambda c: float(getattr(c, "final_score", getattr(c, "score", 0.0))))
        return winner
    def record_immediate_success(self, timestamp=None):
        self._last_immediate = timestamp or self._clock()

    def seed_persisted_success(self, timestamp):
        if timestamp is not None and (self._last_immediate is None or timestamp > self._last_immediate):
            self._last_immediate = timestamp
    def reset(self):
        self._last_immediate = None
