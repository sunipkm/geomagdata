"""Fast, offline unit tests -- no network access, unlike test_read.py's
end-to-end tests against the live NOAA/GFZ servers. These target the
`web`/`io` helpers directly."""
import os
from datetime import datetime, timedelta

import pytest

from geomagdata import readers as io
from geomagdata import web


def test_exist_ok_freshness_is_timezone_correct(tmp_path):
    """`exist_ok`'s age check must not depend on the system's local UTC
    offset (regression test: it used to mix a local-time `datetime.now()`
    against a UTC `datetime.utcfromtimestamp(mtime)`)."""
    fn = tmp_path / "fresh.dat"
    fn.write_bytes(b"x" * 2000)  # exist_ok also requires st_size > 1000

    assert web.exist_ok(fn, timedelta(minutes=5)) is True

    old = (datetime.now() - timedelta(days=10)).timestamp()
    os.utime(fn, (old, old))
    assert web.exist_ok(fn, timedelta(days=1)) is False


def test_exist_ok_too_small_file_is_not_ok(tmp_path):
    fn = tmp_path / "truncated.dat"
    fn.write_bytes(b"x" * 10)
    assert web.exist_ok(fn) is False


def test_exist_ok_missing_file_is_not_ok(tmp_path):
    assert web.exist_ok(tmp_path / "does_not_exist.dat") is False


def test_read_monthly_rejects_unrecognized_suffix(tmp_path):
    fn = tmp_path / "unexpected.csv"
    fn.write_text("not real monthly data")

    with pytest.raises(ValueError):
        io.read_monthly(fn)


def test_readdaily_century_cutoff_tracks_current_year(tmp_path, monkeypatch):
    """The legacy fixed-width format's 2-digit year must be disambiguated
    against the current year, not a hardcoded cutoff (regression test: a
    hardcoded "< 38" cutoff would misread real 2038+ dates as 1938+)."""

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2036, 6, 1)

    monkeypatch.setattr(io, "datetime", FrozenDatetime)

    # cutoff = (2036 + 1) % 100 = 37: "37" is still this-century, "39" rolls
    # over to last-century, matching a real two-digit-year data stream.
    two_digit_years_to_expected = {
        "15": 2015,
        "37": 2037,
        "39": 1939,
        "99": 1999,
    }
    fn = tmp_path / "test_daily"
    fn.write_text(
        "\n".join(f"{yy}0601{' ' * 62}" for yy in two_digit_years_to_expected) + "\n"
    )

    df = io.readdaily(fn)

    assert sorted({d.year for d in df.index}) == sorted(two_digit_years_to_expected.values())
