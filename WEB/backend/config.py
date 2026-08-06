import os

# Discord Webhook configuration
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL", 
    "https://discord.com/api/webhooks/1534868329989406824/eBE-aIEaB-XKYvPdLs8fChxFuAdaOZhluyr9dlsduCcd8NZj29QkIrBie6Y_edAnJS3A"
)

# Base directory for the backend app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Asset paths and user data directories
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Ensure required runtime folders exist
for d in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)
