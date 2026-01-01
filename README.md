# TrainTrack

TrainTrack is a small FastAPI service that fetches the **Indian Railways train running status** from the **National Train Enquiry System (NTES)** and converts the returned data into a clean JSON response.

It’s designed to be a lightweight “API wrapper” around the upstream running-status page, with best-effort parsing for arrival/departure events and optional time-window filtering.

## Quickstart

Install dependencies:

```bash
uv sync
```

Run (development):

```bash
uv run uvicorn app.main:app --reload --host localhost --port 8000
```

Run (production):

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API

You can also test the API interactively via Swagger UI at:

- http://localhost:8000/docs

### `GET /`

Health/welcome endpoint.

Example:

```bash
curl http://127.0.0.1:8000/
```

### `GET /train/{train_number}`

Fetch running status for a train and return parsed arrival/departure events.

- `train_number` (path): must be a **5-digit** train number (`10000`–`99999`).
- `start_time` (query, optional): lower-bound for filtering returned events.
- `end_time` (query, optional): upper-bound for filtering returned events.

`start_time` / `end_time` accepted formats:

- Time-only: `HH:MM` or `HH:MM:SS`
- ISO datetime: `YYYY-MM-DDTHH:MM:SS` (optionally with `Z`)

Examples:

```bash
# Fetch and parse running status
curl "http://127.0.0.1:8000/train/34056"

# Only include events between 10:00 and 18:30 (interpreted relative to the chosen base date)
curl "http://127.0.0.1:8000/train/34056?start_time=10:00&end_time=18:30"

# Use an ISO datetime window
curl "http://127.0.0.1:8000/train/34056?start_time=2026-01-01T10:30:00&end_time=2026-01-01T18:30:00"
```

#### Response shape

The response is a JSON object with:

- `train_number`: the requested 5-digit train number
- `start_date`: the start date string reported by upstream (if present)
- `last_update`: the last update timestamp reported by upstream (if detected)
- `events`: a list of parsed events

Each event includes (best-effort):

- `raw`: the original status line extracted from upstream HTML
- `type`: `Arrived` or `Departed` when detected
- `station`: station name when detected
- `code`: station code (like `NDLS`) when detected
- `datetime`: best-effort local timestamp for the event
- `delay`: delay string when present (e.g. `00:10`)

## How it works

1. **Fetch upstream HTML**

   - TrainTrack calls the **National Train Enquiry System (NTES)** by Indian Railways (`https://enquiry.indianrail.gov.in/mntes`).
   - It bootstraps a session, retrieves a CSRF token, then posts the train number and date to the running-status endpoint.

2. **Extract and parse human-readable status lines**

   - The upstream response is HTML.
   - TrainTrack strips scripts/styles and scans the remaining text for “interesting” lines (e.g. containing `Arrived`, `Departed`, `Last Updates On`, `Start Date`, etc.).

3. **Convert lines into structured events**

   - It uses regex-based parsing to detect `Arrived`/`Departed` events, station name/code (when present), delay strings, and timestamps.
   - Timestamps are best-effort: date may be derived from the “Last Updates On” line or current year when upstream doesn’t include the year.

4. **Apply optional time window filtering**

   - If no `start_time`/`end_time` are provided, TrainTrack defaults to a window covering “today” (local) from `00:00` to the next midnight.
   - If only one bound is provided, the other side defaults to “now”.
   - If both are time-only and the end is earlier than the start, it’s interpreted as spanning midnight into the next day.

5. **Serve via FastAPI**
   - The HTTP call + parsing are synchronous; the API endpoint runs the work in a threadpool to keep the FastAPI handler async-friendly.

## Error handling and limitations

- `422` if `train_number` isn’t a 5-digit number, or if time formats are invalid.
- `502` if the upstream website errors or the expected CSRF token cannot be found.

Parsing is best-effort and depends on upstream HTML/text patterns, which can change over time.
