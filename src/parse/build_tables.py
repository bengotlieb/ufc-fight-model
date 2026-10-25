"""Build clean events, fights, fight_stats and fighters tables from the raw CSVs.

Reads data/raw/ (see src/scrape/ufcstats.py) and writes Parquet files to data/interim/.
Every table is keyed on the ID at the end of its UFCStats URL, because names are not
unique. The build fails if any integrity check fails.

Usage (from the repo root):
    python -m src.parse.build_tables
"""

import pandas as pd

from src.parse.values import (
    first_fighter_won,
    parse_height,
    parse_landed_attempted,
    parse_mmss,
    parse_reach,
    parse_weight,
)
from src.scrape.fetch import RAW_DIR

INTERIM_DIR = RAW_DIR.parent / "interim"

# Stat columns recorded as "X of Y", renamed to snake_case.
LANDED_ATTEMPTED_COLS = {
    "SIG.STR.": "sig_str",
    "TOTAL STR.": "total_str",
    "TD": "td",
    "HEAD": "head",
    "BODY": "body",
    "LEG": "leg",
    "DISTANCE": "distance",
    "CLINCH": "clinch",
    "GROUND": "ground",
}


# Longest names first, so "Light Heavyweight" matches before "Heavyweight".
WEIGHT_CLASSES = [
    "Women's Strawweight", "Women's Flyweight", "Women's Bantamweight", "Women's Featherweight",
    "Light Heavyweight", "Super Heavyweight", "Heavyweight", "Middleweight", "Welterweight",
    "Lightweight", "Featherweight", "Bantamweight", "Flyweight", "Catch Weight", "Open Weight",
]


def standard_weight_class(label: str) -> str:
    """'UFC Interim Light Heavyweight Title Bout' -> 'Light Heavyweight'. Unrecognized -> 'Other'."""
    return next((wc for wc in WEIGHT_CLASSES if wc in label), "Other")


def read_raw(filename: str) -> pd.DataFrame:
    """Read a raw CSV as text, with surrounding whitespace removed from every cell."""
    df = pd.read_csv(RAW_DIR / filename, dtype=str)
    return df.apply(lambda col: col.str.strip().str.replace(r"\s+", " ", regex=True))


def url_id(url: pd.Series) -> pd.Series:
    """'http://ufcstats.com/fight-details/7db1a3dac7e343e7' -> '7db1a3dac7e343e7'."""
    return url.str.rstrip("/").str.rsplit("/", n=1).str[-1]


def build_events() -> pd.DataFrame:
    raw = read_raw("ufc_event_details.csv")
    return pd.DataFrame({
        "event_id": url_id(raw["URL"]),
        "event_name": raw["EVENT"],
        "date": pd.to_datetime(raw["DATE"], format="%B %d, %Y"),
        "location": raw["LOCATION"],
    }).sort_values("date", ignore_index=True)


def build_name_lookup() -> tuple[dict[str, str], set[str]]:
    """Map fighter names to fighter IDs.

    Fight results only identify fighters by name. The two fighter files spell some names
    differently ("Waldo Cortes Acosta" vs "Waldo Cortes-Acosta"), so both spellings are
    mapped. Names shared by more than one fighter are returned separately as ambiguous.
    """
    details = read_raw("ufc_fighter_details.csv")
    tott = read_raw("ufc_fighter_tott.csv")
    details_names = (details["FIRST"].fillna("") + " " + details["LAST"].fillna("")).str.strip()
    pairs = pd.concat([
        pd.DataFrame({"name": details_names, "fighter_id": url_id(details["URL"])}),
        pd.DataFrame({"name": tott["FIGHTER"], "fighter_id": url_id(tott["URL"])}),
    ]).dropna().drop_duplicates()

    ids_per_name = pairs.groupby("name")["fighter_id"].nunique()
    ambiguous = set(ids_per_name[ids_per_name > 1].index)
    lookup = dict(zip(pairs["name"], pairs["fighter_id"]))
    for name in ambiguous:
        del lookup[name]
    return lookup, ambiguous


def build_fights(events: pd.DataFrame, name_to_id: dict[str, str]) -> pd.DataFrame:
    raw = read_raw("ufc_fight_results.csv")

    # Some events were renamed on UFCStats, and the mirror lists their fights under both
    # names. Keeping only rows whose event exists in the events table removes the old copies
    # (and a few fights from an event with no listed date, which can't be ordered in time).
    event_ids = events.set_index("event_name")["event_id"]
    raw = raw[raw["EVENT"].isin(event_ids.index)]

    fighters = raw["BOUT"].str.split(" vs. ", n=1, expand=True)
    time_format = raw["TIME FORMAT"]
    fights = pd.DataFrame({
        "fight_id": url_id(raw["URL"]),
        "event_id": raw["EVENT"].map(event_ids),
        "fighter_a": fighters[0],
        "fighter_b": fighters[1],
        "fighter_a_id": fighters[0].map(name_to_id),
        "fighter_b_id": fighters[1].map(name_to_id),
        "a_won": raw["OUTCOME"].map(first_fighter_won),
        "result": raw["OUTCOME"].map({"W/L": "win", "L/W": "win", "D/D": "draw", "NC/NC": "no_contest"}),
        "method": raw["METHOD"],
        "method_details": raw["DETAILS"],
        "end_round": pd.to_numeric(raw["ROUND"]),
        "end_time_sec": raw["TIME"].map(parse_mmss),
        "scheduled_rounds": pd.to_numeric(time_format.str.extract(r"^(\d+) Rnd")[0]),
        "time_format": time_format,
        "weight_class": raw["WEIGHTCLASS"].map(standard_weight_class),
        "bout_label": raw["WEIGHTCLASS"],
        # Tournament finals (e.g. The Ultimate Fighter) are labeled "Title Bout" but aren't
        # championship fights.
        "title_fight": raw["WEIGHTCLASS"].str.contains("Title|Championship")
                       & ~raw["WEIGHTCLASS"].str.contains("Tournament"),
        "tournament": raw["WEIGHTCLASS"].str.contains("Tournament"),
        "womens": raw["WEIGHTCLASS"].str.contains("Women's"),
        "referee": raw["REFEREE"],
    })
    fights = fights.merge(events[["event_id", "date"]], on="event_id")
    return fights.sort_values(["date", "fight_id"], ignore_index=True)


def build_fight_stats(fights: pd.DataFrame) -> pd.DataFrame:
    raw = read_raw("ufc_fight_stats.csv")
    raw = raw.dropna(subset=["FIGHTER"])  # early events have rows with no stats recorded

    # Stats rows name the fighter but not the fight URL, so attach fight_id via event + bout,
    # then take the fighter ID from whichever corner of that fight the name matches.
    events = read_raw("ufc_event_details.csv")
    results = read_raw("ufc_fight_results.csv")
    results = results[results["EVENT"].isin(events["EVENT"])]
    bout_to_fight = results.assign(fight_id=url_id(results["URL"]))[["EVENT", "BOUT", "fight_id"]]
    # A pairing that fought twice at one event (early tournaments) can't be told apart by
    # event + bout, so stats for those fights are dropped rather than guessed.
    bout_to_fight = bout_to_fight.drop_duplicates(["EVENT", "BOUT"], keep=False)
    raw = raw.merge(bout_to_fight, on=["EVENT", "BOUT"], how="inner")
    raw = raw.merge(fights[["fight_id", "fighter_a", "fighter_b", "fighter_a_id", "fighter_b_id"]],
                    on="fight_id")
    corner_a = raw["FIGHTER"] == raw["fighter_a"]
    corner_b = raw["FIGHTER"] == raw["fighter_b"]
    if not (corner_a ^ corner_b).all():
        bad = raw.loc[~(corner_a ^ corner_b), ["fight_id", "FIGHTER"]].head()
        raise ValueError(f"stats rows that don't match exactly one fighter in their bout:\n{bad}")

    stats = pd.DataFrame({
        "fight_id": raw["fight_id"],
        "fighter_id": raw["fighter_a_id"].where(corner_a, raw["fighter_b_id"]),
        "fighter_name": raw["FIGHTER"],
        "corner": corner_a.map({True: "a", False: "b"}),
        "round": pd.to_numeric(raw["ROUND"].str.replace("Round ", "", regex=False)),
        "kd": pd.to_numeric(raw["KD"]),
        "sub_att": pd.to_numeric(raw["SUB.ATT"]),
        "rev": pd.to_numeric(raw["REV."]),
        "ctrl_sec": raw["CTRL"].map(parse_mmss),
    })
    for raw_col, name in LANDED_ATTEMPTED_COLS.items():
        parsed = raw[raw_col].map(parse_landed_attempted)
        stats[f"{name}_landed"] = parsed.str[0]
        stats[f"{name}_attempted"] = parsed.str[1]
    return stats.sort_values(["fight_id", "round", "corner"], ignore_index=True)


def build_fighters() -> pd.DataFrame:
    tott = read_raw("ufc_fighter_tott.csv")
    details = read_raw("ufc_fighter_details.csv")
    nicknames = details.assign(fighter_id=url_id(details["URL"])).set_index("fighter_id")["NICKNAME"]
    fighter_id = url_id(tott["URL"])
    return pd.DataFrame({
        "fighter_id": fighter_id,
        "name": tott["FIGHTER"],
        "nickname": fighter_id.map(nicknames),
        "height_in": tott["HEIGHT"].map(parse_height),
        "weight_lb": tott["WEIGHT"].map(parse_weight),
        "reach_in": tott["REACH"].map(parse_reach),
        "stance": tott["STANCE"],
        "dob": pd.to_datetime(tott["DOB"].replace("--", None), format="%b %d, %Y"),
    }).sort_values("fighter_id", ignore_index=True)


def check_integrity(events, fights, fight_stats, fighters) -> None:
    """Raise if a primary key is duplicated or a foreign key points nowhere."""
    def unique(df, cols, table):
        dupes = df.duplicated(cols).sum()
        if dupes:
            raise ValueError(f"{table}: {dupes} duplicate rows for key {cols}")

    def references(df, col, target, target_col, table):
        orphans = df[col].notna() & ~df[col].isin(target[target_col])
        if orphans.any():
            raise ValueError(f"{table}.{col}: {orphans.sum()} values not found in {target_col}")

    unique(events, ["event_id"], "events")
    unique(fights, ["fight_id"], "fights")
    unique(fight_stats, ["fight_id", "corner", "round"], "fight_stats")
    unique(fighters, ["fighter_id"], "fighters")
    references(fights, "event_id", events, "event_id", "fights")
    references(fights, "fighter_a_id", fighters, "fighter_id", "fights")
    references(fights, "fighter_b_id", fighters, "fighter_id", "fights")
    references(fight_stats, "fight_id", fights, "fight_id", "fight_stats")

    decided = fights["result"] == "win"
    if fights.loc[decided, "a_won"].isna().any() or fights.loc[~decided, "a_won"].notna().any():
        raise ValueError("fights: a_won must be set exactly when the result is a win")


def main() -> None:
    events = build_events()
    name_to_id, ambiguous = build_name_lookup()
    fights = build_fights(events, name_to_id)
    fight_stats = build_fight_stats(fights)
    fighters = build_fighters()
    check_integrity(events, fights, fight_stats, fighters)

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    tables = {"events": events, "fights": fights, "fight_stats": fight_stats, "fighters": fighters}
    for name, df in tables.items():
        df.to_parquet(INTERIM_DIR / f"{name}.parquet", index=False)
        print(f"{name:<12} {len(df):>7,} rows")

    unmatched = pd.concat([
        fights.loc[fights["fighter_a_id"].isna(), "fighter_a"],
        fights.loc[fights["fighter_b_id"].isna(), "fighter_b"],
    ])
    print(f"\nFights with an unresolved fighter ID: "
          f"{(fights['fighter_a_id'].isna() | fights['fighter_b_id'].isna()).sum():,}")
    print(f"  shared names ({len(ambiguous)}): {', '.join(sorted(ambiguous))}")
    other = sorted(set(unmatched) - ambiguous)
    print(f"  names not in either fighter file ({len(other)}): {', '.join(other) or 'none'}")


if __name__ == "__main__":
    main()
