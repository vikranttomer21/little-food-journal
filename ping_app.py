
import os
import urllib.request
import urllib.error
from datetime import datetime

APP_URL = os.environ["APP_URL"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def ping_app():
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(
        APP_URL,
        headers={"User-Agent": "Mozilla/5.0 LittleFoodJournal-UptimeCheck"},
    )

    timestamp = datetime.now().isoformat(timespec="seconds")

    try:
        response = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error

    status = response.code
    location = response.headers.get("Location", "(none)")

    print(f"{timestamp} | HTTP {status}")
    print(f"Requested URL: {APP_URL}")
    print(f"Redirect destination: {location}")

    if 200 <= status < 300:
        print("Ping successful.")
        return

    if 300 <= status < 400:
        print("Server returned a redirect. Inspect the destination above.")
        return

    raise RuntimeError(f"Unexpected HTTP status: {status}")


if __name__ == "__main__":
    ping_app()
