# Telegram AI Personal Assistant

An intelligent Telegram assistant bot built with Python, `python-telegram-bot`, Google Gemini API (`google-genai`), and SQLite (`aiosqlite`).

## Features

- 💬 **Natural Language & Voice Processing**: Understands both text messages and voice notes via Google Gemini multimodal processing.
- 📝 **Notes Management**: Save, view, and interactively delete notes with inline confirmation buttons.
- ⏰ **Proactive Reminders**: Scheduled notifications delivered to Telegram via `APScheduler` (JobQueue).
- 📅 **Calendar & Agenda**: Schedule and view upcoming events and meetings with interactive deletion flows.
- 🛡️ **Safety & Confirmation**: Inline confirmation buttons (`[ ✅ Sí, borrar ]` / `[ ❌ No, cancelar ]`) prevent accidental data loss.
- 🐳 **Docker & Coolify Ready**: Includes production `Dockerfile` with persistent volume mounting for the SQLite database.

## Tech Stack

- **Python 3.12**
- **python-telegram-bot** (JobQueue / APScheduler)
- **google-genai** (Gemini Flash models with automatic fallback)
- **aiosqlite** (Asynchronous SQLite database)
- **Docker**

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
TIMEZONE=America/Caracas
DATABASE_PATH=data/assistant.db
```

## Running Locally

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

## Deployment with Coolify

1. Connect this repository to your Coolify instance.
2. Select **Dockerfile** as the build pack.
3. Configure Environment Variables (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `TIMEZONE`).
4. Mount a persistent volume at `/app/data` to retain the SQLite database across redeployments.
5. Deploy!
