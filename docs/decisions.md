# Design Decisions



## 2026-10-14: Don't commit data files

- **What:** data/raw/ and data/processed/ are in .gitignore.

- **Why:** Raw HTML is large and is UFCStats' content, not mine. Processed data can be regenerated from code, so committing it risks a stale copy that doesn't match the code.

- **Alternatives considered:** Committing processed data so others can skip scraping (rejected for now), or Git LFS for large files.



## 2026-10-14: Use a Python virtual environment (venv)

- **What:** All project libraries are installed into a project-local `.venv`, with exact versions pinned in `requirements.txt`.

- **Why:** Reproducibility and isolation. Anyone can rebuild the exact environment with `pip install -r requirements.txt`, and upgrading a library for another project can't break this one.

- **Alternatives considered:** Installing globally (no isolation, can't reproduce versions) and conda (more powerful, but unnecessary for a pure-Python project).

## 2026-10-14: Cache every downloaded page; separate fetching from parsing
- **What:** All downloads go through `src/scrape/fetch.py`, which saves each page's raw HTML to `data/raw/` and reads from there on later calls. Parsing code only ever reads cached HTML.
- **Why:** Parser bugs are fixed and re-run in seconds instead of re-scraping 10,000+ pages for hours. UFCStats is hit once per page, with a 1s delay and exponential backoff on 429/5xx. The cache is a fixed snapshot of the data the model was built on.
- **Alternatives considered:** Fetching and parsing in one step (every parser fix needs a full re-scrape), hashed cache filenames (unreadable when debugging).

## 2026-10-17: Get UFCStats data from a public CSV mirror instead of scraping the site
- **What:** `src/scrape/ufcstats.py` downloads four CSVs (events, fight results, per-round fight stats, fighter physicals) from the Greco1899/scrape_ufc_stats GitHub repo, which republishes UFCStats data and is kept current.
- **Why:** UFCStats now serves a JavaScript bot check ("Checking your browser...") to scripts, with a 200 status. Getting around it would mean deliberately bypassing the site's protection, so I didn't. The mirror has the same data and keeps the UFCStats URLs as stable IDs.
- **Risks:** A third-party scrape can contain errors and changes weekly. Mitigations: cached copies are a fixed snapshot, header checks on download, sanity checks when parsing, and spot checks against UFCStats in a browser.
- **Alternatives considered:** Solving the bot check in code (circumvents the site), Kaggle datasets (often pre-cleaned and stale), saving 10,000+ pages by hand (impractical).

## 2026-10-17: Validate every download before caching it
- **What:** `fetch()` takes an `expect` argument (for the CSVs, the exact header row) and refuses to cache a file that doesn't start with it.
- **Why:** My first run cached the bot-check page because it came back with status 200. A status code isn't proof of good data, and a cache full of junk fails silently and instantly on every later run. Checking the header also catches the mirror renaming or reordering columns before it breaks the parser.

## 2026-10-25: Clean tables keyed on UFCStats IDs, stored as Parquet
- **What:** `src/parse/build_tables.py` builds four tables in `data/interim/`: `events` (key `event_id`), `fights` (`fight_id`), `fight_stats` (`fight_id`, `corner`, `round`) and `fighters` (`fighter_id`). Every ID is the hash at the end of the UFCStats URL. The build fails if a key is duplicated or a reference points to a missing row.
- **Why:** Names aren't unique (there are two different fighters named Bruno Silva), so names can't be keys. Parquet keeps column types (dates, numbers, booleans), so nothing has to be re-parsed after loading.
- **Alternatives considered:** CSV (loses types), SQLite (more setup than this project needs yet).

## 2026-10-25: Data cleaning rules
- **Duplicate fights:** some events were renamed and the mirror lists their fights under both names. Only fights whose event appears in the events table are kept, which removes the 25 duplicates and 2 fights from an event with no date.
- **Fighter IDs:** fight results name fighters but don't link to them, so names are matched to IDs using both fighter files (they spell some names differently). 56 fights (0.6%) involve a name shared by two fighters or a name in neither file; their fighter ID is left blank rather than guessed.
- **Missing values** (`--`) become NaN, never 0. A missing reach is unknown, not zero.
- **Draws and no contests** have `a_won` = NaN, since they are neither a win nor a loss.
- **Bout order:** the first-listed fighter won 64% of decided fights, because UFCStats tends to list the winner first. Fighter order must be randomized before modeling, or the model learns the listing order instead of the matchup.
