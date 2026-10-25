"""Attach historical moneyline odds to the fights table.

Source: the Kaggle "Ultimate UFC Dataset" (mdabbert/ultimate-ufc-dataset), downloaded by
hand into data/raw/kaggle/ufc-master.csv because Kaggle requires a login. Only the odds
columns are used. The file's precomputed fighter stats are career numbers of unclear timing,
so they are ignored in favor of features built from our own fight-level data.

Writes data/interim/odds.parquet with one row per matched fight. Run after build_tables:
    python -m src.parse.join_odds
"""

import unicodedata

import numpy as np
import pandas as pd

from src.parse.build_tables import INTERIM_DIR
from src.scrape.fetch import RAW_DIR

KAGGLE_FILE = RAW_DIR / "kaggle" / "ufc-master.csv"
DATE_TOLERANCE = pd.Timedelta(days=1)  # dates can differ by a day for events outside the US


def normalize_name(names: pd.Series) -> pd.Series:
    """Lowercase ASCII letters only: 'Jiří Procházka' -> 'jiri prochazka'."""
    ascii_names = names.map(lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode())
    return (ascii_names.str.lower()
                       .str.replace(r"[^a-z ]", "", regex=True)
                       .str.replace(r"\s+", " ", regex=True)
                       .str.strip())


def load_kaggle_odds() -> pd.DataFrame:
    cols = ["R_fighter", "B_fighter", "R_odds", "B_odds", "date", "Winner"]
    raw = pd.read_csv(KAGGLE_FILE, usecols=cols)
    return pd.DataFrame({
        "row": np.arange(len(raw)),
        "date": pd.to_datetime(raw["date"]),
        "red": normalize_name(raw["R_fighter"]),
        "blue": normalize_name(raw["B_fighter"]),
        "red_odds": raw["R_odds"],
        "blue_odds": raw["B_odds"],
        "winner": raw["Winner"],
    }).dropna(subset=["red_odds", "blue_odds"])


def match_fights(fights: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """Pair each fight with at most one odds row.

    A fight and an odds row match when their dates are within DATE_TOLERANCE and at least
    one fighter's name is the same. Requiring only one name catches fighters whose names are
    spelled differently or changed (e.g. after marriage), and is safe because a fighter fights
    at most once on a given date. Any fight or odds row with more than one candidate is dropped.
    """
    candidates = []
    for our_side in ["name_a", "name_b"]:
        for their_side in ["red", "blue"]:
            pairs = fights[["fight_id", "date", our_side]].merge(
                odds[["row", "date", their_side]],
                left_on=our_side, right_on=their_side, suffixes=("", "_odds"),
            )
            close = (pairs["date"] - pairs["date_odds"]).abs() <= DATE_TOLERANCE
            candidates.append(pairs.loc[close, ["fight_id", "row"]])

    matches = pd.concat(candidates).drop_duplicates()
    matches = matches[~matches["fight_id"].duplicated(keep=False)]
    return matches[~matches["row"].duplicated(keep=False)]


def main() -> None:
    fights = pd.read_parquet(INTERIM_DIR / "fights.parquet")
    odds = load_kaggle_odds()
    fights = fights.assign(name_a=normalize_name(fights["fighter_a"]),
                           name_b=normalize_name(fights["fighter_b"]))

    matched = (match_fights(fights, odds)
               .merge(fights[["fight_id", "name_a", "name_b", "a_won"]], on="fight_id")
               .merge(odds, on="row"))

    # Orient the odds to our fighter A / fighter B.
    a_is_red = (matched["name_a"] == matched["red"]) | (matched["name_b"] == matched["blue"])
    a_is_blue = (matched["name_a"] == matched["blue"]) | (matched["name_b"] == matched["red"])
    matched = matched[a_is_red ^ a_is_blue]
    a_is_red = a_is_red[matched.index]

    result = pd.DataFrame({
        "fight_id": matched["fight_id"],
        "odds_a": matched["red_odds"].where(a_is_red, matched["blue_odds"]),
        "odds_b": matched["blue_odds"].where(a_is_red, matched["red_odds"]),
        "source": "kaggle_ultimate_ufc",
    }).reset_index(drop=True)

    # Sanity check: both sources should agree on who won.
    kaggle_a_won = np.where(matched["winner"] == "Red", a_is_red, ~a_is_red)
    decided = matched["a_won"].notna() & matched["winner"].isin(["Red", "Blue"])
    agreement = (kaggle_a_won[decided] == (matched.loc[decided, "a_won"] == 1)).mean()
    if agreement < 0.99:
        raise ValueError(f"only {agreement:.1%} of matched fights agree on the winner; matching is off")

    if result["fight_id"].duplicated().any():
        raise ValueError("odds: duplicate fight_id")

    result.to_parquet(INTERIM_DIR / "odds.parquet", index=False)

    in_range = fights[(fights["date"] >= odds["date"].min()) & (fights["date"] <= odds["date"].max())]
    print(f"odds rows with both prices:  {len(odds):,} ({odds['date'].min():%Y-%m-%d} to {odds['date'].max():%Y-%m-%d})")
    print(f"fights in that date range:   {len(in_range):,}")
    print(f"fights matched to odds:      {len(result):,} ({len(result) / len(in_range):.1%})")
    print(f"winner agreement:            {agreement:.2%}")


if __name__ == "__main__":
    main()
