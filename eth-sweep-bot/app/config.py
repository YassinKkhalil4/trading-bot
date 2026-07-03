from __future__ import annotations
import os, yaml
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
from dotenv import load_dotenv

class ExchangeConfig(BaseModel):
    id: str = "binance"; symbol: str = "ETH/USDT"; timeframe: str = "5m"; market_type: str = "spot"
    @field_validator('symbol')
    @classmethod
    def only_eth(cls, v):
        if v != 'ETH/USDT': raise ValueError('Version 1 only allows ETH/USDT')
        return v
    @field_validator('market_type')
    @classmethod
    def spot_only(cls, v):
        if v != 'spot': raise ValueError('Version 1 is spot-only')
        return v
class TradingConfig(BaseModel):
    timezone: str; trade_start: str; trade_end: str; poll_interval_seconds: int; max_candle_age_seconds: int
class AccountConfig(BaseModel): core_capital_usd: float; risk_bucket_usd: float
class RiskConfig(BaseModel):
    max_risk_per_trade_usd: float; max_daily_loss_usd: float; max_weekly_loss_usd: float; max_trades_per_day: int; max_losses_per_day: int; max_open_positions: int; min_reward_risk: float; cooldown_minutes_after_trade: int; pause_if_risk_bucket_below_usd: float; max_position_notional_usd: float
class StrategyConfig(BaseModel):
    lookback_candles: int; retest_max_candles: int; retest_tolerance_pct: float; stop_buffer_pct: float; target_r_multiple: float; long_only: bool = True
    @model_validator(mode='after')
    def long(self):
        if not self.long_only: raise ValueError('Version 1 is long-only')
        return self
class FiltersConfig(BaseModel): max_spread_pct: float; max_signal_candle_range_pct: float; min_quote_volume_usd: float = 0.0
class ExecutionConfig(BaseModel): entry_order_type: str; stop_order_type: str; take_profit_order_type: str; cancel_entry_after_seconds: int; post_only_entries: bool = False
class StorageConfig(BaseModel): sqlite_path: str
class LoggingConfig(BaseModel): log_path: str; level: str = "INFO"
class Settings(BaseModel):
    exchange: ExchangeConfig; trading: TradingConfig; account: AccountConfig; risk: RiskConfig; strategy: StrategyConfig; filters: FiltersConfig; execution: ExecutionConfig; storage: StorageConfig; logging: LoggingConfig
class RuntimeConfig(BaseModel):
    mode: str = Field(default='paper'); allow_live_trading: bool = False; binance_api_key: str = ''; binance_api_secret: str = ''; telegram_bot_token: str = ''; telegram_allowed_user_id: str = ''; telegram_chat_id: str = ''
    @model_validator(mode='after')
    def safe_modes(self):
        if self.mode not in {'paper','testnet','live'}: raise ValueError('BOT_MODE must be paper, testnet, or live')
        if self.mode in {'testnet','live'} and (not self.binance_api_key or not self.binance_api_secret): raise ValueError(f'{self.mode} mode requires Binance API credentials')
        if self.mode == 'live' and not self.allow_live_trading: raise ValueError('live mode refused: ALLOW_LIVE_TRADING=true is required')
        return self

def load_config(path='config/settings.yaml') -> tuple[Settings, RuntimeConfig]:
    load_dotenv()
    data = yaml.safe_load(Path(path).read_text())
    runtime = RuntimeConfig(mode=os.getenv('BOT_MODE','paper'), allow_live_trading=os.getenv('ALLOW_LIVE_TRADING','false').lower()=='true', binance_api_key=os.getenv('BINANCE_API_KEY',''), binance_api_secret=os.getenv('BINANCE_API_SECRET',''), telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN',''), telegram_allowed_user_id=os.getenv('TELEGRAM_ALLOWED_USER_ID',''), telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID',''))
    return Settings(**data), runtime
