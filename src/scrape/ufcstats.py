"""Download the UFCStats tables from the public CSV mirror into data/raw/.

UFCStats itself now blocks scripts with a JavaScript bot check (see docs/decisions.md),
so we use Greco1899/scrape_ufc_stats on GitHub, which republishes the same data as CSVs.

Run from the repo root:   python -m src.scrape.ufcstats
Re-download fresh copies: python -m src.scrape.ufcstats --refresh
"""

import sys
import time

from src.scrape.fetch import fetch, url_to_path

BASE_URL = "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main/"

# Each file and the exact header row it must start with. If the mirror ever renames or
# reorders columns, the download fails loudly here instead of breaking our parser later.
FILES = {
    "ufc_event_details.csv": "EVENT,URL,DATE,LOCATION",
    "ufc_fight_results.csv": "EVENT,BOUT,OUTCOME,WEIGHTCLASS,METHOD,ROUND,TIME,TIME FORMAT,REFEREE,DETAILS,URL",
    "ufc_fight_stats.csv": "EVENT,BOUT,ROUND,FIGHTER,KD,SIG.STR.,SIG.STR. %,TOTAL STR.,TD,TD %,SUB.ATT,REV.,CTRL,HEAD,BODY,LEG,DISTANCE,CLINCH,GROUND",
    "ufc_fighter_tott.csv": "FIGHTER,HEIGHT,WEIGHT,REACH,STANCE,DOB,URL",
}


def download_all(refresh: bool = False) -> None:
    for filename, header in FILES.items():
        url = BASE_URL + filename
        start = time.time()
        text = fetch(url, expect=header, refresh=refresh)
        rows = text.count("\n")   # rough row count, just a sanity check
        print(f"{filename:<24} {rows:>7,} rows  {time.time() - start:5.2f}s  -> {url_to_path(url).name}")


if __name__ == "__main__":
    download_all(refresh="--refresh" in sys.argv)
