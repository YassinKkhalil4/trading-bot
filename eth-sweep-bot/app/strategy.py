from __future__ import annotations
from .models import Candle, Signal, Retest, TradePlan

def detect_bullish_sweep(candles: list[Candle], lookback_candles: int, max_signal_candle_range_pct: float) -> Signal | None:
    if len(candles) < lookback_candles + 1: return None
    current = candles[-1]
    previous_window = candles[-lookback_candles-1:-1]
    previous_low = min(c.low for c in previous_window)
    candle_range_pct = (current.high - current.low) / current.open
    if candle_range_pct > max_signal_candle_range_pct: return None
    if current.low < previous_low and current.close > previous_low:
        return Signal('bullish_sweep_reclaim', previous_low, current.low, current.close, current.timestamp, current.high)
    return None

def detect_retest(candles_after_signal: list[Candle], signal: Signal, retest_max_candles: int, retest_tolerance_pct: float) -> Retest | None:
    for candle in candles_after_signal[:retest_max_candles]:
        if candle.low <= signal.sweep_low:
            signal.status = 'invalid'; signal.rejection_reason = 'retest_broke_sweep_low'; return None
        near_level = abs(candle.low - signal.level) / signal.level <= retest_tolerance_pct
        if near_level and candle.close > signal.sweep_low:
            return Retest(candle, candle.high)
    return None

def build_trade_plan(symbol: str, signal: Signal, retest: Retest, stop_buffer_pct: float, target_r_multiple: float, min_reward_risk: float) -> TradePlan | None:
    entry_price = retest.trigger_price
    stop_price = signal.sweep_low * (1 - stop_buffer_pct)
    risk_per_unit = entry_price - stop_price
    if risk_per_unit <= 0: return None
    target_price = entry_price + target_r_multiple * risk_per_unit
    rr = (target_price - entry_price) / risk_per_unit
    if rr < min_reward_risk: return None
    return TradePlan(symbol, 'buy', entry_price, stop_price, target_price, rr, signal, retest)
