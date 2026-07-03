from datetime import datetime, timezone
def candles_are_stale(candles, max_age_seconds: int) -> bool:
    if not candles: return True
    age=(datetime.now(timezone.utc)-candles[-1].timestamp).total_seconds()
    return age > max_age_seconds
