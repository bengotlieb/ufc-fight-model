"""Rate-limited HTTP fetching with an on-disk cache in data/raw/."""

import time
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

DELAY_SECONDS = 1.0                      # base delay before each network request
MAX_ATTEMPTS = 4
RETRY_CODES = {429, 500, 502, 503, 504}  # transient: rate limited or server error
HEADERS = {"User-Agent": "ufc-fight-model (personal research project)"}

# Stripped from URLs to keep cache filenames short.
URL_PREFIXES = [
    "raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main/",
    "ufcstats.com/",
]


def url_to_path(url: str) -> Path:
    """Map a URL to its cache file, e.g. .../ufc_event_details.csv -> data/raw/ufc_event_details.csv."""
    name = url.split("://", 1)[-1]
    for prefix in URL_PREFIXES:
        name = name.replace(prefix, "")
    for ch in "/?=&":  # not valid in Windows filenames
        name = name.replace(ch, "_")
    if "." not in name:
        name += ".html"
    return RAW_DIR / name


def fetch(url: str, expect: str | None = None, refresh: bool = False) -> str:
    """Return the body at url, reading from the cache when possible.

    Args:
        url: URL to fetch.
        expect: If given, the body must start with this string (e.g. a CSV header row).
            Responses that don't match raise instead of being cached, since a 200 status
            can still carry a bot-check or error page.
        refresh: Ignore any cached copy and download again.
    """
    path = url_to_path(url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")

    # Exponential backoff: 1s, 2s, 4s, 8s.
    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(DELAY_SECONDS * 2 ** (attempt - 1))
        response = requests.get(url, headers=HEADERS, timeout=60)

        if response.status_code == 200:
            response.encoding = "utf-8"  # don't let requests guess; fighter names contain accents
            if expect is not None and not response.text.startswith(expect):
                raise RuntimeError(
                    f"{url} returned 200 but doesn't start with {expect!r}. "
                    f"It starts with: {response.text[:80]!r}. Not caching it."
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write before returning so an interrupted run keeps everything fetched so far.
            path.write_text(response.text, encoding="utf-8", newline="")
            return response.text

        if response.status_code in RETRY_CODES:
            print(f"  {response.status_code} on {url}, retrying (attempt {attempt}/{MAX_ATTEMPTS})")
            continue

        response.raise_for_status()  # non-transient errors such as 404

    raise RuntimeError(f"Gave up on {url} after {MAX_ATTEMPTS} attempts")
