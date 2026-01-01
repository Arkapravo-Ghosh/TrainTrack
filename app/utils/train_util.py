import re
from datetime import datetime

import requests

from app.helpers.train_helper import today_str


BASE_URL = "https://enquiry.indianrail.gov.in/mntes"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/",
    "Origin": "https://enquiry.indianrail.gov.in",
    "X-Requested-With": "XMLHttpRequest",
}


class UpstreamError(RuntimeError):
    """Raised when the upstream service fails or returns unexpected data."""


def _bootstrap_session(session: requests.Session, *, timeout_s: float) -> None:
    r = session.get(f"{BASE_URL}/", timeout=timeout_s)
    r.raise_for_status()


def _get_csrf_token(session: requests.Session, *, timeout_s: float) -> tuple[str, str]:
    params = {"t": int(datetime.now().timestamp() * 1000)}
    r = session.get(f"{BASE_URL}/GetCSRFToken", params=params, timeout=timeout_s)
    r.raise_for_status()

    match = re.search(r"name='([^']+)' value='([^']+)'", r.text)
    if not match:
        raise UpstreamError("CSRF token not found in upstream response")

    return match.group(1), match.group(2)


def fetch_train_status_html(
    train_number: int | str,
    *,
    timeout_s: float = 10.0,
) -> str:
    """Fetch running status HTML from the upstream website."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    _bootstrap_session(session, timeout_s=timeout_s)
    csrf_key, csrf_val = _get_csrf_token(session, timeout_s=timeout_s)

    params = {
        "opt": "TrainRunning",
        "subOpt": "FindRunningInstance",
        "refDate": today_str(),
    }
    data = {
        "lan": "en",
        "jDate": today_str(),
        "trainNo": str(train_number),
        csrf_key: csrf_val,
    }

    r = session.post(f"{BASE_URL}/tr", params=params, data=data, timeout=timeout_s)
    r.raise_for_status()
    return r.text
