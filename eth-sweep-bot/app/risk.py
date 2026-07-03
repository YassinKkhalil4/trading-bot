from __future__ import annotations
from datetime import datetime, time, timedelta
import pytz
from .models import Approval, TradePlan, PositionSize

class RiskEngine:
    def __init__(self, settings, storage=None): self.settings=settings; self.storage=storage; self.tz=pytz.timezone(settings.trading.timezone)
    def cairo_date(self, dt=None): return (dt or datetime.now(self.tz)).astimezone(self.tz).date().isoformat()
    def cairo_week(self, dt=None):
        d=(dt or datetime.now(self.tz)).astimezone(self.tz); y,w,_=d.isocalendar(); return f"{y}-W{w:02d}"
    def check_trading_window(self, dt=None):
        d=(dt or datetime.now(self.tz)).astimezone(self.tz); s=time.fromisoformat(self.settings.trading.trade_start); e=time.fromisoformat(self.settings.trading.trade_end); return s <= d.time() <= e
    def check_daily_loss(self, realized): return realized > -self.settings.risk.max_daily_loss_usd
    def check_weekly_loss(self, realized): return realized > -self.settings.risk.max_weekly_loss_usd
    def check_trade_count(self, count): return count < self.settings.risk.max_trades_per_day
    def check_loss_count(self, count): return count < self.settings.risk.max_losses_per_day
    def check_min_reward_risk(self, rr): return rr >= self.settings.risk.min_reward_risk
    def check_risk_bucket(self): return self.settings.account.risk_bucket_usd >= self.settings.risk.pause_if_risk_bucket_below_usd
    def can_trade_now(self, daily=None, weekly=None, open_positions=0, now=None) -> Approval:
        if not self.check_trading_window(now): return Approval(False,'outside_trading_window')
        if open_positions >= self.settings.risk.max_open_positions: return Approval(False,'max_open_positions')
        if not self.check_risk_bucket(): return Approval(False,'risk_bucket_below_minimum')
        if daily:
            if not self.check_daily_loss(daily.get('realized_pnl_usd',0)): return Approval(False,'max_daily_loss_hit')
            if not self.check_trade_count(daily.get('trades_taken',0)): return Approval(False,'max_trades_per_day_hit')
            if not self.check_loss_count(daily.get('losses',0)): return Approval(False,'max_losses_per_day_hit')
        if weekly and not self.check_weekly_loss(weekly.get('realized_pnl_usd',0)): return Approval(False,'max_weekly_loss_hit')
        return Approval(True,'approved')

def calculate_position_size(risk_bucket_usd: float, max_risk_per_trade_usd: float, entry_price: float, stop_price: float, target_price: float, max_position_notional_usd: float, min_amount: float=0.0, min_notional: float=0.0, free_quote_balance: float|None=None) -> PositionSize:
    risk_distance = entry_price - stop_price
    if risk_distance <= 0: raise ValueError('risk_distance_must_be_positive')
    raw_quantity = max_risk_per_trade_usd / risk_distance
    max_quantity_by_notional = max_position_notional_usd / entry_price
    quantity = min(raw_quantity, max_quantity_by_notional)
    notional = quantity * entry_price
    actual_risk = quantity * risk_distance
    reward = quantity * (target_price - entry_price)
    if quantity < min_amount: raise ValueError('quantity_below_exchange_min_amount')
    if notional < min_notional: raise ValueError('notional_below_exchange_min_notional')
    if actual_risk <= 0 or actual_risk > max_risk_per_trade_usd + 1e-9: raise ValueError('actual_risk_invalid')
    if notional > max_position_notional_usd + 1e-9: raise ValueError('position_notional_exceeds_max')
    if free_quote_balance is not None and notional > free_quote_balance: raise ValueError('insufficient_free_quote_balance')
    return PositionSize(quantity, actual_risk, reward, notional)

def validate_trade_plan(plan: TradePlan, settings, market_limits: dict, free_quote_balance: float|None=None) -> Approval:
    if plan.symbol != settings.exchange.symbol: return Approval(False,'symbol_not_allowed')
    if plan.reward_risk < settings.risk.min_reward_risk: return Approval(False,'reward_risk_below_minimum')
    try:
        calculate_position_size(settings.account.risk_bucket_usd, settings.risk.max_risk_per_trade_usd, plan.entry_price, plan.stop_price, plan.target_price, settings.risk.max_position_notional_usd, market_limits.get('min_amount',0) or 0, market_limits.get('min_notional',0) or 0, free_quote_balance)
    except ValueError as e: return Approval(False,str(e))
    return Approval(True,'approved')
