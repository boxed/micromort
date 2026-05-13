import math

import pytest

from micromort import convert as c


def test_from_one_in():
    assert c.from_one_in(1_000_000) == pytest.approx(1.0)
    assert c.from_one_in(11_000) == pytest.approx(90.909, rel=1e-3)


def test_from_probability_and_percent():
    assert c.from_probability(1e-6) == pytest.approx(1.0)
    assert c.from_percent(0.0001) == pytest.approx(1.0)


def test_from_deaths_per():
    # 11 deaths per million ≈ 11 micromorts
    assert c.from_deaths_per(11, 1_000_000) == pytest.approx(11.0)


def test_from_rate_per_100k():
    # 7 deaths / 100,000 / yr → 70 µmt / yr
    assert c.from_rate_per_100k(7) == pytest.approx(70.0)


def test_hourly_to_activity():
    assert c.hourly_to_activity(10, 2.5) == pytest.approx(25.0)


def test_lifetime_to_annual():
    assert c.lifetime_to_annual(8000, 80) == pytest.approx(100.0)


def test_parse_one_in():
    p = c.parse("1 in 11,000")
    assert p.micromorts == pytest.approx(90.909, rel=1e-3)


def test_parse_per():
    p = c.parse("5 deaths per 100,000")
    assert p.micromorts == pytest.approx(50.0)


def test_parse_bad():
    with pytest.raises(ValueError):
        c.parse("totally not a risk")


def test_rejects_invalid():
    with pytest.raises(ValueError):
        c.from_one_in(0)
    with pytest.raises(ValueError):
        c.from_probability(1.5)
    with pytest.raises(ValueError):
        c.from_deaths_per(1, 0)
