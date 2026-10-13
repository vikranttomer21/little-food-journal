
import os
import urllib.request
from datetime import datetime

APP_URL = os.environ["APP_URL"]

request = urllib.request.Request(
    APP_URL,
    headers={"User-Agent": "LittleFoodJournal-UptimeCheck"},
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"{datetime.now().isoformat()} | HTTP {response.status}")
except Exception as error:
    print(f"Ping failed: {error}")
    raise
