import os

API_PORT = int(os.getenv("API_PORT", "4000"))
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8001")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "dev-internal-token")
SITE_KEY = os.getenv("SITE_KEY", "sk_dev_local")
