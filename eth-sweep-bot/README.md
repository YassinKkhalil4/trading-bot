# ETH Sweep Bot

A deterministic, long-only, spot ETH/USDT trading bot for a bullish liquidity sweep + reclaim + retest strategy. Version 1 prioritizes capital protection over trade frequency and defaults to paper mode.

## Legal and Risk Warnings

- Egypt has restrictive crypto regulations. This project is educational software and is configured to default to paper mode. Consult qualified legal/tax advice before any exchange trading.
- There is no profit guarantee. You can lose money, including from bugs, latency, exchange outages, slippage, and incorrect configuration.
- Never enable withdrawal permissions on API keys. Trading permission only is sufficient.
- Do not use cross margin, leverage, futures, or perpetuals. Version 1 is spot-only.

## Setup

```bash
cd eth-sweep-bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with environment variables only. Do not put API keys in YAML config.

## Modes

### Paper mode

Paper mode uses real Binance market data and does not call private order endpoints.

```bash
BOT_MODE=paper python -m app.main
```

### Binance Spot Testnet

Create Binance Spot Testnet API credentials with trading permissions and no withdrawals, then set:

```bash
BOT_MODE=testnet
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
```

Run:

```bash
python -m app.main
```

### Live mode

Live mode is disabled unless all of the following are true:

1. You completed `LIVE_APPROVAL_CHECKLIST.md` manually.
2. `BOT_MODE=live`.
3. `ALLOW_LIVE_TRADING=true`.
4. Binance API credentials are present.
5. You explicitly approve deployment.

Start with tiny spot size only. Never enable withdrawals.

## Docker

```bash
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

## Telegram

If `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, and `TELEGRAM_CHAT_ID` are set, notifications are enabled. If missing, the bot still runs and logs Telegram as disabled.

Commands restricted to `TELEGRAM_ALLOWED_USER_ID`:

- `/status`
- `/pause`
- `/resume`
- `/kill`
- `/today`
- `/open`

`/kill` disables new trades and cancels unfilled orders where implemented. Version 1 defaults to leaving protective stops active unless emergency close is explicitly enabled in future code.

## Logs and SQLite

Inspect logs:

```bash
tail -f logs/bot.log
```

Inspect trades:

```bash
sqlite3 data/bot.db 'select * from trades order by id desc limit 20;'
```

Daily stats:

```bash
sqlite3 data/bot.db 'select * from daily_stats order by date desc limit 20;'
```

## Strategy

The bot looks for a visible low, sweep below it, close back above, valid retest above the sweep low, then a break above the retest candle high. Stop is below the sweep low, target is 2R, and any reward/risk below 2.0 is rejected.

## Deployment Path

1. Run unit tests.
2. Run paper mode locally for at least 7 trading days.
3. Run Docker locally.
4. Run paper mode on a VPS.
5. Run Binance Spot Testnet for at least 2 weeks.
6. Review logs and SQLite trades.
7. Only after manual approval, consider live mode with tiny spot size.
