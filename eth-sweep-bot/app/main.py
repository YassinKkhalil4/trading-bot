from __future__ import annotations
import time
from datetime import datetime, timezone, timedelta
from loguru import logger
from .config import load_config
from .utils import setup_logging
from .storage import Storage
from .exchange_client import ExchangeClient
from .market_data import MarketData
from .notifications import Notifier
from .risk import RiskEngine, validate_trade_plan
from .strategy import detect_bullish_sweep, detect_retest, build_trade_plan
from .health import candles_are_stale
from .execution import ExecutionEngine

def cooldown_ok(storage, risk):
    raw=storage.get_state('last_trade_time')
    if not raw: return True
    return datetime.now(timezone.utc) - datetime.fromisoformat(raw) >= timedelta(minutes=risk.settings.risk.cooldown_minutes_after_trade)

def main():
    settings, runtime = load_config()
    setup_logging(settings.logging.log_path, settings.logging.level, runtime.mode, settings.exchange.symbol)
    storage=Storage(settings.storage.sqlite_path); storage.set_state('current_mode', runtime.mode)
    exchange=ExchangeClient(settings,runtime); market=exchange.validate_symbol(); exchange.check_connectivity()
    notifier=Notifier(runtime); notifier.send(f'Bot started in {runtime.mode} mode for {settings.exchange.symbol}')
    risk=RiskEngine(settings, storage); md=MarketData(exchange); execution=ExecutionEngine(exchange, md, settings, runtime, storage, notifier, risk)
    logger.info('startup_complete exchange={} timeframe={} max_risk={}', settings.exchange.id, settings.exchange.timeframe, settings.risk.max_risk_per_trade_usd)
    while True:
        try:
            notifier.poll_commands(storage)
            execution.reconcile()
            if storage.has_open_trade(): execution.monitor_open_trade(); time.sleep(settings.trading.poll_interval_seconds); continue
            if storage.get_state('bot_enabled') != 'true': time.sleep(settings.trading.poll_interval_seconds); continue
            today=risk.cairo_date(); week=risk.cairo_week(); daily=dict(storage.daily(today)); weekly=dict(storage.weekly(week))
            approval=risk.can_trade_now(daily, weekly, 0)
            if not approval.approved: logger.info('scan_blocked reason={}', approval.reason); time.sleep(settings.trading.poll_interval_seconds); continue
            if not cooldown_ok(storage, risk): logger.info('scan_blocked reason=cooldown_active'); time.sleep(settings.trading.poll_interval_seconds); continue
            candles=md.fetch_ohlcv(settings.exchange.symbol, settings.exchange.timeframe, settings.strategy.lookback_candles+settings.strategy.retest_max_candles+50)
            if candles_are_stale(candles, settings.trading.max_candle_age_seconds): storage.set_state('paused_reason','stale_candle_data'); time.sleep(settings.trading.poll_interval_seconds); continue
            spread=md.get_spread_pct(settings.exchange.symbol)
            if spread > settings.filters.max_spread_pct: logger.info('skip spread_too_wide pct={}', spread); time.sleep(settings.trading.poll_interval_seconds); continue
            signal=detect_bullish_sweep(candles, settings.strategy.lookback_candles, settings.filters.max_signal_candle_range_pct)
            if signal:
                storage.set_state('strategy_state','sweep_detected')
                signal_id=storage.insert_signal(settings.exchange.symbol, settings.exchange.timeframe, signal)
                logger.info('signal_detected id={} type={} level={}', signal_id, signal.signal_type, signal.level); notifier.send(f'Signal detected: {signal.signal_type}')
                idx=next(i for i,c in enumerate(candles) if c.timestamp == signal.detected_at)
                retest=detect_retest(candles[idx+1:], signal, settings.strategy.retest_max_candles, settings.strategy.retest_tolerance_pct)
                if not retest:
                    storage.mark_signal(signal_id, signal.status, signal.rejection_reason or 'waiting_for_retest')
                    storage.set_state('strategy_state','waiting_for_retest')
                else:
                    storage.set_state('strategy_state','waiting_for_entry_trigger')
                    plan=build_trade_plan(settings.exchange.symbol, signal, retest, settings.strategy.stop_buffer_pct, settings.strategy.target_r_multiple, settings.risk.min_reward_risk)
                    limits={'min_amount': (market.get('limits',{}).get('amount',{}) or {}).get('min') or 0, 'min_notional': (market.get('limits',{}).get('cost',{}) or {}).get('min') or 0}
                    trade_approval=validate_trade_plan(plan, settings, limits) if plan else None
                    if trade_approval and trade_approval.approved:
                        storage.mark_signal(signal_id, 'approved', None); execution.place_trade(plan, signal_id, limits); storage.set_state('strategy_state','entry_pending')
                    else:
                        reason=trade_approval.reason if trade_approval else 'invalid_trade_plan'; storage.mark_signal(signal_id, 'rejected', reason); logger.info('signal_rejected reason={}', reason); notifier.send(f'Signal rejected: {reason}')
            time.sleep(settings.trading.poll_interval_seconds)
        except Exception as exc:
            logger.exception('critical_unhandled_exception {}', exc); storage.set_state('bot_enabled','false'); storage.set_state('paused_reason','unhandled_exception'); notifier.send(f'Critical error: {exc}'); time.sleep(settings.trading.poll_interval_seconds)
if __name__ == '__main__': main()
