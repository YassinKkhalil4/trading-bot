from __future__ import annotations
from datetime import datetime, timezone, timedelta
from loguru import logger
from .risk import calculate_position_size

class ExecutionEngine:
    def __init__(self, exchange, market_data, settings, runtime, storage, notifier, risk_engine=None):
        self.exchange=exchange; self.market_data=market_data; self.settings=settings; self.runtime=runtime; self.storage=storage; self.notifier=notifier; self.risk=risk_engine
    def place_trade(self, plan, signal_id=None, market_limits=None, free_quote_balance=None):
        if self.storage.has_open_trade(): raise RuntimeError('duplicate_position_blocked')
        market_limits=market_limits or {'min_amount':0,'min_notional':0}
        size=calculate_position_size(self.settings.account.risk_bucket_usd,self.settings.risk.max_risk_per_trade_usd,plan.entry_price,plan.stop_price,plan.target_price,self.settings.risk.max_position_notional_usd,market_limits.get('min_amount',0) or 0,market_limits.get('min_notional',0) or 0,free_quote_balance)
        if self.runtime.mode == 'paper':
            trade_id=self.storage.insert_trade(signal_id, plan.symbol, 'buy', 'paper', 'entry_pending', plan.entry_price, plan.stop_price, plan.target_price, size.quantity, self.settings.risk.max_risk_per_trade_usd, size.actual_risk_usd, size.planned_reward_usd, plan.reward_risk, 'paper-entry')
            logger.info('paper_entry_order_placed trade_id={} symbol={} entry={} qty={}', trade_id, plan.symbol, plan.entry_price, size.quantity); self.notifier.send(f'Entry order placed (paper): {plan.symbol} {size.quantity}')
            return trade_id
        order=self.exchange.create_order(plan.symbol,'limit','buy',size.quantity,plan.entry_price)
        trade_id=self.storage.insert_trade(signal_id, plan.symbol, 'buy', self.runtime.mode, 'entry_pending', plan.entry_price, plan.stop_price, plan.target_price, size.quantity, self.settings.risk.max_risk_per_trade_usd, size.actual_risk_usd, size.planned_reward_usd, plan.reward_risk, order.get('id'))
        self.notifier.send(f'Entry order placed: {order.get("id")}'); return trade_id
    def monitor_open_trade(self):
        trade=self.storage.get_open_trade()
        if not trade: return None
        if trade['mode']=='paper': return self._monitor_paper(trade)
        return self._monitor_real(trade)
    def _monitor_paper(self, trade):
        t=self.market_data.fetch_ticker(trade['symbol']); bid=t.bid or t.last; ask=t.ask or t.last; last=t.last or bid or ask
        if trade['status']=='entry_pending':
            if ask is not None and ask <= trade['entry_price']:
                self.storage.update_trade(trade['id'],status='open',opened_at=datetime.now(timezone.utc).isoformat(),stop_order_id='paper-stop',target_order_id='paper-target')
                logger.info('paper_entry_filled trade_id={}', trade['id']); self.notifier.send(f'Entry filled (paper) trade {trade["id"]}')
            elif self.cancel_stale_entry_order(datetime.fromisoformat(trade['opened_at']) if trade['opened_at'] else datetime.now(timezone.utc)-timedelta(seconds=self.settings.execution.cancel_entry_after_seconds+1)):
                self.storage.update_trade(trade['id'],status='missed',closed_at=datetime.now(timezone.utc).isoformat(),close_reason='stale_entry_canceled')
                logger.info('paper_entry_canceled_stale trade_id={}', trade['id'])
            return None
        if trade['status']=='open':
            exit_price=None; reason=None
            if bid is not None and bid <= trade['stop_price']: exit_price=trade['stop_price']; reason='stop_hit'
            elif last is not None and last >= trade['target_price']: exit_price=trade['target_price']; reason='target_hit'
            if reason:
                pnl=(exit_price-trade['entry_price'])*trade['quantity']; result_r=pnl/trade['actual_risk_usd'] if trade['actual_risk_usd'] else 0
                date=self.risk.cairo_date() if self.risk else datetime.now(timezone.utc).date().isoformat(); week=self.risk.cairo_week() if self.risk else 'unknown'
                self.storage.close_trade(trade['id'],exit_price,pnl,result_r,reason,date,week)
                logger.info('paper_trade_closed trade_id={} reason={} pnl={}', trade['id'], reason, pnl); self.notifier.send(f'Trade closed (paper): {reason} pnl={pnl:.2f}')
            return None
    def _monitor_real(self, trade):
        orders=[] if self.exchange.mode=='paper' else self.exchange.exchange.fetch_open_orders(trade['symbol'])
        if trade['status']=='entry_pending':
            order=self.exchange.exchange.fetch_order(trade['entry_order_id'], trade['symbol'])
            if order.get('status')=='closed':
                self.storage.update_trade(trade['id'],status='open',opened_at=datetime.now(timezone.utc).isoformat())
                self._place_protection_or_exit(trade)
            elif self.cancel_stale_entry_order(datetime.fromisoformat(trade['opened_at']) if trade['opened_at'] else datetime.now(timezone.utc)-timedelta(seconds=self.settings.execution.cancel_entry_after_seconds+1)):
                self.exchange.cancel_order(trade['entry_order_id'], trade['symbol']); self.storage.update_trade(trade['id'],status='missed',closed_at=datetime.now(timezone.utc).isoformat(),close_reason='stale_entry_canceled')
        return orders
    def _place_protection_or_exit(self, trade):
        try:
            stop=self.exchange.create_order(trade['symbol'],'stop_loss','sell',trade['quantity'],None,{'stopPrice': trade['stop_price']})
            self.storage.update_trade(trade['id'],stop_order_id=stop.get('id')); self.notifier.send(f'Stop placed: {stop.get("id")}')
        except Exception as exc:
            self.stop_failure_exit_required(trade, exc); return
        try:
            target=self.exchange.create_order(trade['symbol'],'limit','sell',trade['quantity'],trade['target_price'])
            self.storage.update_trade(trade['id'],target_order_id=target.get('id')); self.notifier.send(f'Target placed: {target.get("id")}')
        except Exception as exc:
            logger.warning('target placement failed once: {}', exc); self.notifier.send('Target placement failed; stop remains active')
    def stop_failure_exit_required(self, trade=None, error=None):
        if trade:
            try: self.exchange.create_order(trade['symbol'],'market','sell',trade['quantity'])
            except Exception as exc: logger.critical('emergency exit failed: {}', exc)
            self.storage.update_trade(trade['id'],error=str(error) if error else 'protective_stop_failed')
        self.storage.set_state('bot_enabled','false'); self.storage.set_state('paused_reason','protective_stop_failed'); self.notifier.send('CRITICAL: stop placement failed; bot paused and emergency exit attempted')
    def cancel_stale_entry_order(self, order_created_at: datetime): return datetime.now(timezone.utc) - order_created_at > timedelta(seconds=self.settings.execution.cancel_entry_after_seconds)
    def reconcile(self):
        trade=self.storage.get_open_trade()
        if not trade: return True
        if self.runtime.mode == 'paper': return True
        open_orders=self.exchange.fetch_open_orders(trade['symbol'])
        if trade['status']=='open' and not any(o.get('id')==trade['stop_order_id'] for o in open_orders):
            self.storage.set_state('bot_enabled','false'); self.storage.set_state('paused_reason','reconciliation_missing_stop'); self.notifier.send('CRITICAL: reconciliation found open trade without stop'); return False
        return True
