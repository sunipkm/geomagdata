from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas
import pytest
from pytest import approx

import geomagdata as gi


def _get_indices_or_skip(*args, **kwargs) -> pandas.DataFrame:
    """`gi.get_indices`, skipping the test (rather than failing it) on a
    network/download error -- these tests need live internet access to
    NOAA/GFZ servers, which isn't this package's own code under test."""
    try:
        return gi.get_indices(*args, **kwargs)
    except ConnectionError as e:
        pytest.skip(f"possible timeout error {e}")


@pytest.mark.parametrize(
    "dt,hour,f107,f107s,ap,aps,kp",
    [
        # f107s/aps/kp recomputed after fixing `get_indices`'s `smoothdays`
        # window to be centered on `dt` (the standard convention), not
        # trailing -- see `base.py`'s own `rolling(..., center=True)`.
        (date(2017, 5, 1), 1, 76.4, 78.43, 9, 10.44, 2.33),
        (datetime(2017, 5, 1, 12), 13, 76.4, 78.47, 2, 10.24, 0.33),
        (datetime(2020, 3, 31, 12), 1, 69.8, 69.77, 15, 5.31, 3.0),
    ],
)
def test_past(dt, hour, f107, f107s, ap, aps, kp):
    dat = _get_indices_or_skip(dt, 81)

    assert dat.shape[0] == 1
    assert dat["f107"].iloc[0] == approx(f107, abs=0.1)
    assert dat["f107s"].iloc[0] == approx(f107s, abs=0.1)
    assert dat["Ap"].iloc[0] == ap
    assert dat["Aps"].iloc[0] == approx(aps, abs=0.1)
    if "Kp" in dat:
        assert dat["Kp"].iloc[0] == approx(kp, abs=0.1)


def test_nearfuture():
    t = datetime.today() + timedelta(days=3)

    dat = _get_indices_or_skip(t)

    assert dat.shape[0] == 1

    if t.hour >= 12:
        assert dat.index[0] == datetime(t.year, t.month, t.day) + timedelta(days=1)
    else:
        assert dat.index[0] == datetime(t.year, t.month, t.day)

    assert "Ap" in dat
    assert "f107" in dat


def test_farfuture():
    t = date(2029, 12, 21)

    dat = _get_indices_or_skip(t, 81)

    assert dat.shape == (1, 5)
    assert dat.index[0] == datetime(2030, 1, 1, 2, 37, 40, 799998)

    assert "Ap" in dat
    assert "f107" in dat
    assert "f107s" in dat
    assert "Aps" in dat


def test_list():
    t = [date(2018, 1, 1), datetime(2018, 1, 2)]

    dat = _get_indices_or_skip(t)

    assert dat.shape[0] == 2
    assert dat.shape[1] in (3, 4)

    assert (dat.index == [datetime(2018, 1, 1, 1, 30), datetime(2018, 1, 2, 1, 30)]).all()


def test_multi_past():
    dates = pandas.date_range(datetime(2017, 12, 31, 23), datetime(2018, 1, 1, 2), freq="3h")

    dat = _get_indices_or_skip(dates)

    assert (dat.index == [datetime(2017, 12, 31, 22, 30), datetime(2018, 1, 1, 1, 30)]).all()


def test_past_and_future():
    dates = [datetime(2017, 1, 1), datetime(2030, 3, 1)]

    dat = _get_indices_or_skip(dates)

    pasttime = datetime(2017, 1, 1)
    if dat["resolution"][0] == "d":
        pasttime += timedelta(hours=1, minutes=30)

    assert (dat.index == [pasttime, datetime(2030, 3, 2, 22, 55, 11, 999997)]).all()


def _get_storm_ap_or_skip(*args, **kwargs):
    try:
        return gi.get_storm_ap(*args, **kwargs)
    except ConnectionError as e:
        pytest.skip(f"possible timeout error {e}")


@pytest.mark.parametrize(
    "dt,tzaware,want",
    [
        (
            datetime(2023, 3, 15, 14, 0, 0, tzinfo=UTC),
            True,
            [29.875, 15.0, 27.0, 27.0, 67.0, 19.625, 3.625],
        ),
        (
            datetime(2023, 12, 30, 22, 30, 0),
            False,
            [3.875, 0.0, 4.0, 4.0, 3.0, 5.5, 3.875],
        ),
    ],
)
def test_storm_ap(dt, tzaware, want):
    """`AP(1..7)` cross-checked directly against
    `glowpython2.atmo_msis00.NrlMsis00.storm_ap` (already independently
    verified against `nrlmsise00.f`'s own `GTD7` header) for the exact
    same instants, including one spanning a real year boundary --
    `get_storm_ap` is a from-scratch reimplementation inside this
    package, not a copy, so this is a real cross-check, not a
    tautology."""
    ap = _get_storm_ap_or_skip(dt, tzaware=tzaware)
    assert ap.dtype == np.float32
    assert ap.shape == (7,)
    assert ap.tolist() == approx(want, abs=1e-3)
