"""Download files politely and cache each one in data/raw/, so every URL is fetched only once."""

import time
from pathlib import Path

import requests

# Repo root is two folders up from this file (src/scrape/fetch.py), so this works from any folder.
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

DELAY_SECONDS = 1.0   # pause before every real download, so we never hammer the site
MAX_ATTEMPTS = 4      # give up on a URL after this many tries
RETRY_CODES = {429, 500, 502, 503, 504}   # "slow down" or "server hiccup": worth retrying
HEADERS = {"User-Agent": "ufc-fight-model (personal research project)"}  # say who we are

# Long, repetitive URL prefixes we strip so cache filenames stay short and readable.
URL_PREFIXES = [
    "raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main/",
    "ufcstats.com/",
]


def url_to_path(url: str) -> Path:
    """Turn a URL into a readable cache filename, e.g. ufc_event_details.csv."""
    name = url.split("://", 1)[-1]          # drop "http://" or "https://"
    for prefix in URL_PREFIXES:
        name = name.replace(prefix, "")
    for ch in "/?=&":                        # these characters aren't allowed in Windows filenames
        name = name.replace(ch, "_")
    if "." not in name:                      # web pages have no extension, so call them .html
        name += ".html"
    return RAW_DIR / name


def fetch(url: str, expect: str | None = None, refresh: bool = False) -> str:
    """Return the text at url: from the cache if we have it, otherwise download and save it.

    expect: text the real file must start with (e.g. a CSV's header row). If the download
    doesn't start with it, we raise instead of caching it, so junk never gets into data/raw/.
    """
    path = url_to_path(url)

    # 1. Cache hit: no internet, no delay. This is why re-parsing takes seconds.
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")

    # 2. Cache miss: download, waiting longer after each failure (1s, 2s, 4s, 8s).
    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(DELAY_SECONDS * 2 ** (attempt - 1))
        response = requests.get(url, headers=HEADERS, timeout=60)

        if response.status_code == 200:
            response.encoding = "utf-8"   # fighter names have accents; don't let requests guess
            # Lesson 3: a 200 can still be junk (a bot-check page, an error page). Check first.
            if expect is not None and not response.text.startswith(expect):
                raise RuntimeError(
                    f"{url} returned 200 but doesn't start with {expect!r}. "
                    f"It starts with: {response.text[:80]!r}. Not caching it."
                )
            path.parent.mkdir(parents=True, exist_ok=True)   # create data/raw/ if missing
            path.write_text(response.text, encoding="utf-8", newline="")  # save BEFORE returning, byte-for-byte
            return response.text

        if response.status_code in RETRY_CODES:
            print(f"  {response.status_code} on {url}, backing off (attempt {attempt}/{MAX_ATTEMPTS})")
            continue

        response.raise_for_status()   # anything else (e.g. 404) is a real error: stop loudly

    raise RuntimeError(f"Gave up on {url} after {MAX_ATTEMPTS} attempts")
