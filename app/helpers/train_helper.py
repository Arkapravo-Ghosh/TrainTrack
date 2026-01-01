import html as _html
import re
from datetime import datetime
from typing import Any


def today_str() -> str:
    """Return today's date in the format expected by the upstream site."""
    return datetime.now().strftime("%d-%b-%Y")


def _strip_html(html_text: str) -> str:
    html_text = re.sub(r"(?is)<script.*?>.*?</script>", "", html_text)
    html_text = re.sub(r"(?is)<style.*?>.*?</style>", "", html_text)
    return re.sub(r"<[^>]+>", "", html_text)


def extract_status_lines(html_text: str) -> list[str]:
    """Extract human-readable status lines from the upstream HTML response."""
    text = _strip_html(html_text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    keywords = [
        "Arrived",
        "Arrive",
        "Arriving",
        "Departed",
        "Depart",
        "Departure",
        "On Time",
        "Yet to start",
        "Reached Destination",
        "Current Position",
        "Last Updates On",
        "Start Date",
    ]

    matches: list[str] = []
    for ln in lines:
        lnl = ln.lower()
        for kw in keywords:
            if kw.lower() in lnl:
                matches.append(ln)
                break

    seen: set[str] = set()
    uniq: list[str] = []
    for m in matches:
        if m not in seen:
            uniq.append(m)
            seen.add(m)

    return uniq


def _clean_line(line: str) -> str:
    line = _html.unescape(line)
    line = line.replace("\xa0", " ")
    line = re.sub(r"\s+", " ", line)
    line = re.sub(r"Last Updates On(?=\d)", "Last Updates On ", line)
    return line.strip(" \t\n\r\u00a0")


def _parse_last_update_dt(lines: list[str]) -> datetime | None:
    last_updates: list[datetime] = []
    for ln in lines:
        m = re.search(
            r"Last Updates On\s*(?P<date>\d{1,2}-[A-Za-z]{3}-\d{4})(?:\s+(?P<time>\d{1,2}:\d{2}))?",
            ln,
            flags=re.I,
        )
        if not m:
            continue

        date = m.group("date")
        time = m.group("time") or "00:00"
        try:
            last_updates.append(datetime.strptime(f"{date} {time}", "%d-%b-%Y %H:%M"))
        except Exception:  # pylint: disable=broad-except
            continue

    return max(last_updates) if last_updates else None


def _parse_start_date(lines: list[str]) -> str | None:
    for ln in lines:
        m = re.search(
            r"Start Date\s*:\s*(?P<date>\d{1,2}-[A-Za-z]{3}-\d{4})",
            ln,
            flags=re.I,
        )
        if m:
            return m.group("date")
    return None


def _build_event_dt(
    *,
    date_part: str | None,
    time_part: str | None,
    last_update_dt: datetime | None,
) -> datetime | None:
    time_part = time_part or "00:00"

    if date_part:
        # date_part may be '30-Dec' or '30-Dec-2025'
        if re.match(r"\d{1,2}-[A-Za-z]{3}-\d{4}$", date_part):
            ds = date_part
        else:
            yr = last_update_dt.year if last_update_dt else datetime.now().year
            ds = f"{date_part}-{yr}"
        try:
            return datetime.strptime(f"{ds} {time_part}", "%d-%b-%Y %H:%M")
        except Exception:  # pylint: disable=broad-except
            return None

    if last_update_dt:
        try:
            return datetime.strptime(
                f"{last_update_dt.strftime('%d-%b-%Y')} {time_part}", "%d-%b-%Y %H:%M"
            )
        except Exception:  # pylint: disable=broad-except
            return None

    return None


def parse_train_status_html(html_text: str) -> dict[str, Any]:
    """Parse the upstream HTML into structured data.

    Returns a dict with keys: start_date (str|None), last_update (datetime|None), events (list[dict]).
    """
    raw_lines = extract_status_lines(html_text)
    lines = [_clean_line(r) for r in raw_lines]

    last_update_dt = _parse_last_update_dt(lines)
    start_date = _parse_start_date(lines)

    events: list[dict[str, Any]] = []
    for ln in lines:
        if not re.search(
            r"\b(arrived|arrive|arriving|departed|depart|departure)\b", ln, flags=re.I
        ):
            continue

        ev: dict[str, Any] = {
            "raw": ln,
            "type": None,
            "station": None,
            "code": None,
            "datetime": None,
            "delay": None,
        }

        dm = re.search(
            r"Delay[:\-\s]*\(?\s*(?:Delay\s*)?([0-9:]{1,5})\)?", ln, flags=re.I
        )
        if dm:
            ev["delay"] = dm.group(1)

        m = re.search(
            r"\b(Departed|Arrived)\b\s+(?:from|at)\s+(?P<station>[^()]+?)\s*\(\s*(?P<code>[A-Z0-9]{1,6})\s*\)",
            ln,
            flags=re.I,
        )
        if m:
            ev["type"] = m.group(1).title()
            ev["station"] = m.group("station").strip()
            ev["code"] = m.group("code").strip()

            mtime = re.search(r"(\d{1,2}:\d{2})", ln)
            mdate = re.search(r"(\d{1,2}-[A-Za-z]{3}(?:-\d{4})?)", ln)
            ev_dt = _build_event_dt(
                date_part=mdate.group(1) if mdate else None,
                time_part=mtime.group(1) if mtime else None,
                last_update_dt=last_update_dt,
            )
            ev["datetime"] = ev_dt

            if ev["type"] and ev["station"]:
                events.append(ev)
            continue

        m2 = re.search(
            r"\b(Departed|Arrived)\b\s+(?:from|at)\s+(?P<station>.+?)\s+(?:at|on)\b",
            ln,
            flags=re.I,
        )
        if m2:
            ev["type"] = m2.group(1).title()
            station = m2.group("station").strip()
            station = re.sub(r"\b(on|at)\b$", "", station, flags=re.I).strip()
            ev["station"] = station

            mtime = re.search(r"(\d{1,2}:\d{2})", ln)
            mdate = re.search(r"(\d{1,2}-[A-Za-z]{3}(?:-\d{4})?)", ln)
            ev_dt = _build_event_dt(
                date_part=mdate.group(1) if mdate else None,
                time_part=mtime.group(1) if mtime else None,
                last_update_dt=last_update_dt,
            )
            ev["datetime"] = ev_dt

            if ev["type"] and ev["station"]:
                events.append(ev)
            continue

        mverb = re.search(r"\b(Departed|Arrived)\b", ln, flags=re.I)
        if mverb:
            ev["type"] = mverb.group(1).title()
            mtime = re.search(r"(\d{1,2}:\d{2})", ln)
            mdate = re.search(r"(\d{1,2}-[A-Za-z]{3}(?:-\d{4})?)", ln)
            ev_dt = _build_event_dt(
                date_part=mdate.group(1) if mdate else None,
                time_part=mtime.group(1) if mtime else None,
                last_update_dt=last_update_dt,
            )
            ev["datetime"] = ev_dt
            if ev["datetime"] and ev["type"]:
                events.append(ev)

    seen: set[tuple[Any, Any, Any]] = set()
    uniq_events: list[dict[str, Any]] = []
    for e in events:
        key = (e.get("type"), e.get("station"), e.get("datetime"))
        if key in seen:
            continue
        seen.add(key)
        uniq_events.append(e)

    return {
        "start_date": start_date,
        "last_update": last_update_dt,
        "events": uniq_events,
    }
