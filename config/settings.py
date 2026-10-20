import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
TIMEZONE = os.getenv("TIMEZONE", "UTC").strip()

DATABASE_PATH = BASE_DIR / "data" / "assistant.db"

def validate_config() -> None:
    errors = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "tu_token_de_telegram_aqui":
        errors.append("Falta TELEGRAM_BOT_TOKEN en el archivo .env")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "tu_gemini_api_key_aqui":
        errors.append("Falta GEMINI_API_KEY en el archivo .env")
    
    if errors:
        raise ValueError("\n".join(errors))
