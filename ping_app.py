
import os
import subprocess
from datetime import datetime

APP_URL = os.environ["APP_URL"]

def ping_app():
    result = subprocess.run(
        [
            "curl",
            "--location",
            "--max-redirs", "5",
            "--connect-timeout", "15",
            "--max-time", "45",
            "--silent",
            "--show-error",
            "--output", "/dev/null",
            "--write-out", "%{http_code} %{url_effective}",
            "--user-agent", "Mozilla/5.0 LittleFoodJournal-UptimeCheck",
            APP_URL,
        ],
        capture_output=True,
        text=True,
        timeout=50,
    )

    timestamp = datetime.now().isoformat(timespec="seconds")

    if result.returncode != 0:
        print(f"{timestamp} | Request failed: {result.stderr.strip()}")
        raise RuntimeError("Website request failed")

    print(f"{timestamp} | HTTP result: {result.stdout}")

    status = int(result.stdout.split()[0])

    if status < 200 or status >= 400:
        raise RuntimeError(f"Unexpected HTTP status: {status}")

if __name__ == "__main__":
    ping_app()
