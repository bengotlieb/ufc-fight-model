import math

import pytest

from src.parse.values import (
    first_fighter_won,
    parse_height,
    parse_landed_attempted,
    parse_mmss,
    parse_reach,
    parse_weight,
)

nan = float("nan")
MISSING_INPUTS = ["--", "", "  ", None, nan]


def same(a, b) -> bool:
    """Equality that treats nan == nan as True."""
    if isinstance(a, tuple):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    return a == b


@pytest.mark.parametrize("raw, expected", [
    ("15 of 22", (15.0, 22.0)),
    ("0 of 0", (0.0, 0.0)),
    ("101 of 230", (101.0, 230.0)),
])
def test_parse_landed_attempted(raw, expected):
    assert same(parse_landed_attempted(raw), expected)


@pytest.mark.parametrize("raw, expected", [
    ("1:31", 91.0),
    ("0:00", 0.0),
    ("5:00", 300.0),
    ("15:00", 900.0),
])
def test_parse_mmss(raw, expected):
    assert same(parse_mmss(raw), expected)


@pytest.mark.parametrize("raw, expected", [
    ("5' 11\"", 71.0),
    ("6' 0\"", 72.0),
    ("5' 4\"", 64.0),
    ("7' 0\"", 84.0),
])
def test_parse_height(raw, expected):
    assert same(parse_height(raw), expected)


@pytest.mark.parametrize("raw, expected", [("72\"", 72.0), ("66\"", 66.0), ("84.5\"", 84.5)])
def test_parse_reach(raw, expected):
    assert same(parse_reach(raw), expected)


@pytest.mark.parametrize("raw, expected", [("155 lbs.", 155.0), ("265 lbs.", 265.0)])
def test_parse_weight(raw, expected):
    assert same(parse_weight(raw), expected)


@pytest.mark.parametrize("raw, expected", [
    ("W/L", 1.0),
    ("L/W", 0.0),
    ("D/D", nan),
    ("NC/NC", nan),
    (" W/L ", 1.0),
])
def test_first_fighter_won(raw, expected):
    assert same(first_fighter_won(raw), expected)


@pytest.mark.parametrize("raw", MISSING_INPUTS)
def test_missing_values(raw):
    assert same(parse_landed_attempted(raw), (nan, nan))
    assert same(parse_mmss(raw), nan)
    assert same(parse_height(raw), nan)
    assert same(parse_reach(raw), nan)
    assert same(parse_weight(raw), nan)


def test_unexpected_format_raises():
    # Bad input should fail loudly rather than turn into a wrong number.
    with pytest.raises(ValueError):
        parse_landed_attempted("15/22")
    with pytest.raises(ValueError):
        first_fighter_won("X/Y")
