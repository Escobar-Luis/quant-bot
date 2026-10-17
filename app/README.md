# quant-bot app

Python agent. Model calls go through the Nicrron API (OpenAI-compatible); every run is traced into PRISM.

## Setup (Luis, once)

1. NicrronNinoo account: open `nicrron.ai/redeem?code=FINTECH-LPBMK`, create the account, confirm the email. Create a key at `nicrron.ai/dashboard/keys`.
2. PRISM: sign up at `prism.blockconvey.com/signup`, redeem `MONEYTALKS#2` at Settings → Billing (one workspace per team). Create a key at Settings → API Keys and copy the project id.
3. `cp .env.example .env` and paste the values into `app/.env`.

## Sync and check

```bash
uv sync && uv run python smoke.py && uv run python -m prismtrace.verify
```

`smoke.py` sends one Nicrron call and traces it into PRISM. `prismtrace.verify` prints `CREDENTIAL OK` and `LIVE CONNECTED` when PRISM is wired up.
