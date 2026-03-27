import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_LINK: str = os.getenv("CHANNEL_LINK", "https://t.me/your_channel")
WEBSITE_LINK: str = os.getenv("WEBSITE_LINK", "https://your-website.com")
DB_PATH: str = os.getenv("DB_PATH", "bot.db")

# Прокси (опционально). Форматы:
#   socks5://user:pass@host:port
#   socks5://host:port
#   http://user:pass@host:port
PROXY_URL: str | None = os.getenv("PROXY_URL", None)

# Mini App (Web App)
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://localhost:8080")
WEBAPP_PORT: int = int(os.getenv("PORT") or os.getenv("WEBAPP_PORT", "8080"))

# Referral bonus percent (1st level)
REF_PERCENT: float = 5.0
