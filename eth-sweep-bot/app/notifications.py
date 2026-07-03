from __future__ import annotations
import requests
from loguru import logger
class Notifier:
    def __init__(self, runtime):
        self.token=runtime.telegram_bot_token; self.chat_id=runtime.telegram_chat_id; self.allowed_user_id=runtime.telegram_allowed_user_id; self.enabled=bool(self.token and self.chat_id and self.allowed_user_id)
        if not self.enabled: logger.info('Telegram disabled: missing token, chat id, or allowed user id')
    def send(self, text: str):
        if not self.enabled: return
        try: requests.post(f'https://api.telegram.org/bot{self.token}/sendMessage', json={'chat_id': self.chat_id, 'text': text}, timeout=10)
        except Exception as exc: logger.warning('Telegram send failed: {}', exc)
    def poll_commands(self, storage):
        if not self.enabled: return []
        offset=int(storage.get_state('telegram_offset') or 0); handled=[]
        try:
            r=requests.get(f'https://api.telegram.org/bot{self.token}/getUpdates', params={'offset': offset + 1, 'timeout': 0}, timeout=10).json()
            for upd in r.get('result',[]):
                storage.set_state('telegram_offset', upd['update_id'])
                msg=upd.get('message') or {}; user=msg.get('from',{}).get('id'); text=(msg.get('text') or '').split()[0]
                if text.startswith('/'):
                    handled.append((text,self.handle_command(str(user), text, storage)))
        except Exception as exc: logger.warning('Telegram polling failed: {}', exc)
        return handled
    def handle_command(self, user_id: str, command: str, storage):
        if str(user_id) != str(self.allowed_user_id): return 'unauthorized'
        if command == '/pause': storage.set_state('bot_enabled','false'); storage.set_state('paused_reason','telegram_pause'); self.send('Bot paused'); return 'paused'
        if command == '/resume': storage.set_state('bot_enabled','true'); storage.set_state('paused_reason',''); self.send('Bot resumed'); return 'resumed'
        if command == '/kill': storage.set_state('bot_enabled','false'); storage.set_state('paused_reason','kill_command'); self.send('Bot kill executed; protective stops are left active by default.'); return 'killed'
        if command == '/status': return f"enabled={storage.get_state('bot_enabled')} paused={storage.get_state('paused_reason')}"
        if command == '/today': return 'today stats available in SQLite daily_stats'
        if command == '/open': return 'open trades available in SQLite trades'
        return 'unknown_command'
