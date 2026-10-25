"""Download UFCStats tables from a public CSV mirror into data/raw/.

UFCStats serves a JavaScript bot check to non-browser clients, so the data comes from
Greco1899/scrape_ufc_stats on GitHub, which republishes the same tables as CSVs.
See docs/decisions.md.

Usage (from the repo root):
    python -m src.scrape.ufcstats             # use cached copies where present
    python -m src.scrape.ufcstats --refresh   # download fresh copies
"""

import sys
import time

from src.scrape.fetch import fetch, url_to_path

BASE_URL = "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main/"

# Expected header row for each file. A renamed or reordered column fails here,
# at download time, rather than downstream in the parser.
FILES = {
    "ufc_event_details.csv": "EVENT,URL,DATE,LOCATION",
    "ufc_fight_results.csv": "EVENT,BOUT,OUTCOME,WEIGHTCLASS,METHOD,ROUND,TIME,TIME FORMAT,REFEREE,DETAILS,URL",
    "ufc_fight_stats.csv": "EVENT,BOUT,ROUND,FIGHTER,KD,SIG.STR.,SIG.STR. %,TOTAL STR.,TD,TD %,SUB.ATT,REV.,CTRL,HEAD,BODY,LEG,DISTANCE,CLINCH,GROUND",
    "ufc_fighter_tott.csv": "FIGHTER,HEIGHT,WEIGHT,REACH,STANCE,DOB,URL",
    "ufc_fighter_details.csv": "FIRST,LAST,NICKNAME,URL",
}


def download_all(refresh: bool = False) -> None:
    for filename, header in FILES.items():
        url = BASE_URL + filename
        start = time.time()
        text = fetch(url, expect=header, refresh=refresh)
        rows = text.count("\n")  # approximate; quoted fields could contain newlines
        print(f"{filename:<24} {rows:>7,} rows  {time.time() - start:5.2f}s  -> {url_to_path(url).name}")


if __name__ == "__main__":
    download_all(refresh="--refresh" in sys.argv)
