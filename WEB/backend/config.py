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

# Cloudflare R2 configurations
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "748d1666240cdb1f9fa44a22449db42f")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "5fc0711e3e02f5f1a94e120dcd934cc3")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "17c1ec49060db9a7c697bc24006790972c98b027eb6d56029d34232682dec629")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "dkcvideodraw")
