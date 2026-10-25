"""Convert raw UFCStats text fields into numbers.

Every parser returns NaN for missing values. UFCStats marks missing data as "--",
and pandas reads empty cells as NaN, so both count as missing (see is_missing).
"""

import math

MISSING = float("nan")


def is_missing(value) -> bool:
    """True for NaN/None, empty strings, and the "--" placeholder."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return True
    return str(value).strip() in {"", "--"}


def parse_landed_attempted(value) -> tuple[float, float]:
    """'15 of 22' -> (15.0, 22.0). Missing -> (nan, nan)."""
    if is_missing(value):
        return (MISSING, MISSING)
    parts = str(value).strip().split(" of ")
    if len(parts) != 2:
        raise ValueError(f"expected 'X of Y', got {value!r}")
    return (float(parts[0]), float(parts[1]))


def parse_mmss(value) -> float:
    """Clock time to seconds: '1:31' -> 91.0, '0:00' -> 0.0. Missing -> nan."""
    if is_missing(value):
        return MISSING
    parts = str(value).split(":")
    if len(parts) != 2:
        raise ValueError(f"expected 'X:Y', got {value!r}")
    seconds = float(parts[0]) * 60 + float(parts[1])
    return seconds


def parse_height(value) -> float:
    """Height to inches: '5\\' 11"' -> 71.0, '6\\' 0"' -> 72.0. Missing -> nan."""
    if is_missing(value):
        return MISSING
    text = str(value).replace('"', "")
    parts = text.split("'")
    if len(parts) != 2:
        raise ValueError(f"expected X' Y\", got {value!r}")
    inches = float(parts[0]) * 12 + float(parts[1])
    return inches


def parse_reach(value) -> float:
    """Reach to inches: '72"' -> 72.0. Missing -> nan."""
    if is_missing(value):
        return MISSING
    inches = float(str(value).strip('"'))
    return inches


def parse_weight(value) -> float:
    """Weight to pounds: '155 lbs.' -> 155.0. Missing -> nan."""
    if is_missing(value):
        return MISSING
    pounds = float(str(value).replace(" lbs.", ""))
    return pounds


def first_fighter_won(outcome) -> float:
    """Result from the first-listed fighter's side.

    'W/L' -> 1.0 (first fighter won), 'L/W' -> 0.0 (second fighter won),
    'D/D' (draw) or 'NC/NC' (no contest) -> nan.
    """
    if is_missing(outcome):
        return MISSING
    outcome_dict = {"W/L": 1.0, "L/W": 0.0, "D/D": MISSING, "NC/NC": MISSING}
    key = str(outcome).strip()
    if key not in outcome_dict:
        raise ValueError(f"expected X/Y, got {outcome!r}")
    return outcome_dict[key]
