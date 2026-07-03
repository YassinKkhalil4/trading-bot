from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
        for k,v in {'bot_enabled':'true','last_trade_time':'','paused_reason':'','current_mode':'paper','strategy_state':'no_signal','active_signal_id':'','telegram_offset':'0'}.items(): self.conn.execute("INSERT OR IGNORE INTO bot_state VALUES (?,?,?)",(k,v,now()))
        self.conn.commit()
    def set_state(self,k,v): self.conn.execute("INSERT OR REPLACE INTO bot_state VALUES (?,?,?)",(k,str(v),now())); self.conn.commit()
    def get_state(self,k):
        r=self.conn.execute("SELECT value FROM bot_state WHERE key=?",(k,)).fetchone(); return r['value'] if r else None
    def has_open_trade(self): return self.conn.execute("SELECT 1 FROM trades WHERE status IN ('entry_pending','open') LIMIT 1").fetchone() is not None
    def get_open_trade(self): return self.conn.execute("SELECT * FROM trades WHERE status IN ('entry_pending','open') ORDER BY id DESC LIMIT 1").fetchone()
    def ensure_daily(self, date): self.conn.execute("INSERT OR IGNORE INTO daily_stats(date,updated_at) VALUES (?,?)",(date,now())); self.conn.commit()
    def ensure_weekly(self, week): self.conn.execute("INSERT OR IGNORE INTO weekly_stats(week_id,updated_at) VALUES (?,?)",(week,now())); self.conn.commit()
    def daily(self, date): self.ensure_daily(date); return self.conn.execute("SELECT * FROM daily_stats WHERE date=?",(date,)).fetchone()
    def weekly(self, week): self.ensure_weekly(week); return self.conn.execute("SELECT * FROM weekly_stats WHERE week_id=?",(week,)).fetchone()
    def insert_signal(self, symbol, timeframe, signal):
        cur=self.conn.execute("INSERT INTO signals(symbol,timeframe,signal_type,level,sweep_low,sweep_high,reclaim_close,detected_at,status,rejection_reason) VALUES (?,?,?,?,?,?,?,?,?,?)",(symbol,timeframe,signal.signal_type,signal.level,signal.sweep_low,signal.sweep_high,signal.reclaim_close,signal.detected_at.isoformat(),signal.status,signal.rejection_reason)); self.conn.commit(); return cur.lastrowid
    def mark_signal(self, signal_id, status, reason=None): self.conn.execute("UPDATE signals SET status=?, rejection_reason=? WHERE id=?",(status,reason,signal_id)); self.conn.commit()
    def insert_trade(self, signal_id, symbol, side, mode, status, entry, stop, target, qty, planned_risk, actual_risk, reward, rr, entry_order_id=None):
        cur=self.conn.execute("INSERT INTO trades(signal_id,symbol,side,mode,status,entry_price,stop_price,target_price,quantity,planned_risk_usd,actual_risk_usd,planned_reward_usd,reward_risk,entry_order_id,opened_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(signal_id,symbol,side,mode,status,entry,stop,target,qty,planned_risk,actual_risk,reward,rr,entry_order_id,now() if status in ('open','entry_pending') else None)); self.conn.commit(); return cur.lastrowid
    def update_trade(self, trade_id, **fields: Any):
        if not fields: return
        sets=','.join(f"{k}=?" for k in fields); self.conn.execute(f"UPDATE trades SET {sets} WHERE id=?",(*fields.values(),trade_id)); self.conn.commit()
    def close_trade(self, trade_id, exit_price, pnl, result_r, reason, date, week):
        self.update_trade(trade_id,status='closed',closed_at=now(),exit_price=exit_price,realized_pnl_usd=pnl,result_r=result_r,close_reason=reason)
        self.ensure_daily(date); self.ensure_weekly(week)
        loss=1 if pnl < 0 else 0
        self.conn.execute("UPDATE daily_stats SET trades_taken=trades_taken+1, losses=losses+?, realized_pnl_usd=realized_pnl_usd+?, updated_at=? WHERE date=?",(loss,pnl,now(),date))
        self.conn.execute("UPDATE weekly_stats SET trades_taken=trades_taken+1, realized_pnl_usd=realized_pnl_usd+?, updated_at=? WHERE week_id=?",(pnl,now(),week))
        self.set_state('last_trade_time', now()); self.conn.commit()
