from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass(frozen=True)
class Ticker:
    bid: float | None
    ask: float | None
    last: float | None

@dataclass
class Signal:
    signal_type: str
    level: float
    sweep_low: float
    reclaim_close: float
    detected_at: datetime
    sweep_high: float | None = None
    status: str = "detected"
    rejection_reason: str | None = None

@dataclass(frozen=True)
class Retest:
    candle: Candle
    trigger_price: float

@dataclass(frozen=True)
class TradePlan:
    symbol: str
    side: str
    entry_price: float
    stop_price: float
    target_price: float
    reward_risk: float
    signal: Signal
    retest: Retest

@dataclass(frozen=True)
class PositionSize:
    quantity: float
    actual_risk_usd: float
    planned_reward_usd: float
    notional_usd: float

@dataclass(frozen=True)
class Approval:
    approved: bool
    reason: str = ""
