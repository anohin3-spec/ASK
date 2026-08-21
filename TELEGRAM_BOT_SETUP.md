# Telegram bot setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Add variables to `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
TELEGRAM_COMPANY_ID=00000000-0000-0000-0000-000000000001
TELEGRAM_ACCESS_CODE=4321
```

- `TELEGRAM_ALLOWED_USER_IDS` can be empty to allow all users (not recommended).
- `TELEGRAM_COMPANY_ID` is needed for cloud mode to select your company in Supabase.
- `TELEGRAM_ACCESS_CODE` enables login-by-code flow (`/login <code>`). Good when you want to share bot link without maintaining fixed user IDs.

3. Start bot:

```bash
start_telegram_bot.bat
```

## Implemented bot flow

- `/start` -> equipment list (inline buttons)
- `/login <code>` -> grants access for current Telegram user (saved in `telegram_sessions.json`)
- `/logout` -> removes access for current Telegram user
- tap equipment -> detailed card:
  - VIN
  - STS number
  - current value + update date
  - last maintenance
  - active driver
  - insurance date
  - diagnostic card date
  - MKAD pass date
- buttons:
  - show STS
  - show diagnostic card
  - show insurance
  - issues
- issues list by date/status
- issue details + button to show resolution invoice(s)
