import os

API_PORT = int(os.getenv("API_PORT", "4000"))
PLANNER_URL = os.getenv("PLANNER_URL", "http://localhost:8001")
PLANNER_TOKEN = os.getenv("PLANNER_TOKEN", "dev-internal-token")
SITE_KEY = os.getenv("SITE_KEY", "sk_dev_local")
