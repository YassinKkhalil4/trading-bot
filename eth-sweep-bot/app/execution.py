from __future__ import annotations
from datetime import datetime, timezone, timedelta
from loguru import logger
from .risk import calculate_position_size
class ExecutionEngine:
    def __init__(self, exchange, market_data, settings, runtime, storage, notifier): self.exchange=exchange; self.market_data=market_data; self.settings=settings; self.runtime=runtime; self.storage=storage; self.notifier=notifier
    def place_trade(self, plan, market_limits=None, free_quote_balance=None):
        if self.storage.has_open_trade(): raise RuntimeError('duplicate_position_blocked')
        market_limits=market_limits or {'min_amount':0,'min_notional':0}
        size=calculate_position_size(self.settings.account.risk_bucket_usd,self.settings.risk.max_risk_per_trade_usd,plan.entry_price,plan.stop_price,plan.target_price,self.settings.risk.max_position_notional_usd,market_limits.get('min_amount',0) or 0,market_limits.get('min_notional',0) or 0,free_quote_balance)
        if self.runtime.mode == 'paper': return self._paper_trade(plan,size)
        return self._real_trade(plan,size)
    def _paper_trade(self, plan, size):
        logger.info('paper_entry_order_placed symbol={} entry={} qty={}', plan.symbol, plan.entry_price, size.quantity)
        self.notifier.send(f'Entry order placed (paper): {plan.symbol} {size.quantity}')
        return {'paper': True, 'status': 'entry_pending', 'quantity': size.quantity}
    def _real_trade(self, plan, size):
        entry=self.exchange.create_order(plan.symbol,'limit','buy',size.quantity,plan.entry_price)
        self.notifier.send(f'Entry order placed: {entry.get("id")}')
        # Production monitoring loop is intentionally conservative: caller must confirm fill before protective orders.
        return entry
    def cancel_stale_entry_order(self, order_created_at: datetime): return datetime.now(timezone.utc) - order_created_at > timedelta(seconds=self.settings.execution.cancel_entry_after_seconds)
    def stop_failure_exit_required(self): self.storage.set_state('bot_enabled','false'); self.storage.set_state('paused_reason','protective_stop_failed'); self.notifier.send('CRITICAL: stop placement failed; bot paused and exit required')
