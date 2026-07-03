from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = [
"""CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS daily_stats (date TEXT PRIMARY KEY,trades_taken INTEGER NOT NULL DEFAULT 0,losses INTEGER NOT NULL DEFAULT 0,realized_pnl_usd REAL NOT NULL DEFAULT 0,max_daily_loss_hit INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS weekly_stats (week_id TEXT PRIMARY KEY,trades_taken INTEGER NOT NULL DEFAULT 0,realized_pnl_usd REAL NOT NULL DEFAULT 0,max_weekly_loss_hit INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT NOT NULL,timeframe TEXT NOT NULL,signal_type TEXT NOT NULL,level REAL NOT NULL,sweep_low REAL,sweep_high REAL,reclaim_close REAL NOT NULL,detected_at TEXT NOT NULL,status TEXT NOT NULL,rejection_reason TEXT)""",
"""CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT,signal_id INTEGER,symbol TEXT NOT NULL,side TEXT NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,entry_price REAL NOT NULL,stop_price REAL NOT NULL,target_price REAL NOT NULL,quantity REAL NOT NULL,planned_risk_usd REAL NOT NULL,actual_risk_usd REAL NOT NULL,planned_reward_usd REAL NOT NULL,reward_risk REAL NOT NULL,entry_order_id TEXT,stop_order_id TEXT,target_order_id TEXT,opened_at TEXT,closed_at TEXT,exit_price REAL,realized_pnl_usd REAL,result_r REAL,close_reason TEXT,error TEXT)"""
]
def now(): return datetime.now(timezone.utc).isoformat()
class Storage:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True); self.conn = sqlite3.connect(path); self.conn.row_factory = sqlite3.Row; self.init_db()
    def init_db(self):
        for sql in SCHEMA: self.conn.execute(sql)
        for k,v in {'bot_enabled':'true','last_trade_time':'','paused_reason':'','current_mode':'paper'}.items(): self.conn.execute("INSERT OR IGNORE INTO bot_state VALUES (?,?,?)",(k,v,now()))
        self.conn.commit()
    def set_state(self,k,v): self.conn.execute("INSERT OR REPLACE INTO bot_state VALUES (?,?,?)",(k,v,now())); self.conn.commit()
    def get_state(self,k):
        r=self.conn.execute("SELECT value FROM bot_state WHERE key=?",(k,)).fetchone(); return r['value'] if r else None
    def has_open_trade(self): return self.conn.execute("SELECT 1 FROM trades WHERE status IN ('open','entry_pending') LIMIT 1").fetchone() is not None
    def daily(self, date): return self.conn.execute("SELECT * FROM daily_stats WHERE date=?",(date,)).fetchone()
    def weekly(self, week): return self.conn.execute("SELECT * FROM weekly_stats WHERE week_id=?",(week,)).fetchone()
