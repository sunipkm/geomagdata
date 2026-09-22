from __future__ import annotations

import typing
from datetime import date, datetime, timedelta

import numpy as np
import pandas
import pytz
import whenever
from dateutil.parser import parse

from .readers import load
from .web import downloadfile

#: `whenever` types that carry an unambiguous, exact instant -- always
#: converted to true UTC regardless of the `tzaware` argument (see
#: `todatetime`), unlike a plain `datetime.datetime`, which is ambiguous
#: about what its own tzinfo (or lack of one) actually means.
_WheneverExact = (whenever.Instant, whenever.ZonedDateTime, whenever.OffsetDateTime)

#: Anything `todatetime` accepts: a single time-like value, or a
#: sequence/array/`pandas.DatetimeIndex` of them.
TimeLike = (
    str
    | date
    | datetime
    | np.datetime64
    | whenever.Instant
    | whenever.ZonedDateTime
    | whenever.OffsetDateTime
    | whenever.PlainDateTime
    | whenever.Date
    | typing.Sequence
    | np.ndarray
    | pandas.DatetimeIndex
)


def get_indices(
    time: TimeLike,
    smoothdays: int | None = None,
    forcedownload: bool = False,
    newsource: bool = True,
    tzaware: bool = False,
) -> pandas.DataFrame:
    """Get geomagnetic indices.

    alternative going back to 1931:
    ftp://ftp.ngdc.noaa.gov/STP/GEOMAGNETIC_DATA/INDICES/KP_AP/

    20 year Forecast data from:
    https://sail.msfc.nasa.gov/solar_report_archives/May2016Rpt.pdf

    newsource data from:
    ftp://ftp.gfz-potsdam.de/pub/home/obs/Kp_ap_Ap_SN_F107/

    Args:
        time (TimeLike): Time (or times) near which indices are evaluated.
            A single value or a sequence/array/`pandas.DatetimeIndex`.
        smoothdays (int, optional): Days to average over (for f10.7). Defaults to None.
        forcedownload (bool, optional): Force downloading data from servers every time. Defaults to False.
        newsource (bool, optional): Use the new datasource (newsource). Defaults to True.
        tzaware (bool, optional): Whether supplied datetime is timezone aware.

    Returns:
        pandas.DataFrame: Dataframe containing the retrieved geomagnetic indices.
    """
    dtime = todatetime(time, tzaware)

    _smoothdays = 0 if smoothdays is None else smoothdays  # pass 0 if None
    fn = downloadfile(dtime, _smoothdays, forcedownload, newsource)
    # %% load data
    dat: pandas.DataFrame = load(fn)
    # %% optional smoothing over days
    if isinstance(smoothdays, int):
        periods = np.rint(
            timedelta(days=smoothdays) / (dat.index[1] - dat.index[0])
        ).astype(int)

        # `center=True`: F10.7A/Ap-smoothed conventionally average the
        # `smoothdays` window *centered* on each day (e.g. the standard
        # NRLMSISE-00 F10.7A is the mean of the 40 days before through
        # the 40 days after), not a trailing window ending on that day.
        # pandas' own `rolling()` default (`center=False`) is trailing;
        # leaving it unset here silently biased every `smoothdays`-based
        # average old, most visibly right after a solar-activity swing.
        if "f107" in dat:
            dat["f107s"] = (
                dat["f107"].rolling(periods, center=True, min_periods=1).mean()
            )
        if "Ap" in dat:
            dat["Aps"] = dat["Ap"].rolling(periods, center=True, min_periods=1).mean()

    # %% pull out the times we want
    i = dat.index.get_indexer(
        pandas.Index(dtime), method="nearest"
    )  # fix for get_loc deprecation warning
    Indices = dat.iloc[i, :]

    return Indices


def get_storm_ap(
    time: TimeLike,
    forcedownload: bool = False,
    newsource: bool = True,
    tzaware: bool = False,
) -> np.ndarray:
    """NRLMSISE-00's real 7-element storm-time `ap` history (`AP(1..7)`,
    `nrlmsise00.f`'s own `GTD7` header convention, quoted verbatim):
    `AP(1)`=daily Ap (mean of the eight 3-hour values for `time`'s own
    UTC day), `AP(2)`=3-hour ap for the current time, `AP(3)`=3-hour ap
    for 3 hours before, `AP(4)`=3-hour ap for 6-9 hours before,
    `AP(5)`=3-hour ap for 9-12 hours before, `AP(6)`=average of the
    eight 3-hour ap indices from 12 to 33 hours prior, `AP(7)`=average
    of the eight 3-hour ap indices from 36 to 57 hours prior. Ported
    from `glowpython2.atmo_msis00.NrlMsis00.storm_ap`, already verified
    against that same header directly -- not re-derived here.

    Unlike `get_indices`, this always resolves one storm-ap array for
    one instant, not a batch -- `time` may be any single `TimeLike`
    value, but only its first resolved instant is used.

    Args:
        time: The instant to resolve the storm-ap history around.
        forcedownload/newsource: forwarded to `get_indices`.
        tzaware: Whether `time` is timezone-aware.

    Returns:
        np.ndarray: length-7 `float32`.
    """
    # Resolve once to a naive-UTC anchor via `todatetime`'s own
    # convention, then reuse `tzaware=False` for every sub-fetch below
    # -- these are already-normalized values, not the caller's own
    # `time`, so re-applying `tzaware=True` would double-convert them
    # (`datetime.astimezone()` on an already-naive value reinterprets
    # it as local system time, not UTC).
    t = todatetime(time, tzaware)[0]
    day_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
    fetch_kwargs = {
        "forcedownload": forcedownload,
        "newsource": newsource,
        "tzaware": False,
    }

    ap = np.zeros(7, dtype=float)

    daily = get_indices(
        [day_start + timedelta(hours=h) for h in range(0, 24, 3)], **fetch_kwargs
    )
    ap[0] = daily["Ap"].to_numpy().mean()

    recent = get_indices(
        [t, t - timedelta(hours=3), t - timedelta(hours=6), t - timedelta(hours=9)],
        **fetch_kwargs,
    )
    ap[1:5] = recent["Ap"].to_numpy()

    mid = get_indices(
        [t - timedelta(hours=h) for h in range(12, 36, 3)], **fetch_kwargs
    )
    ap[5] = mid["Ap"].to_numpy().mean()

    late = get_indices(
        [t - timedelta(hours=h) for h in range(36, 60, 3)], **fetch_kwargs
    )
    ap[6] = late["Ap"].to_numpy().mean()

    return ap.astype(np.float32, order="F")


def todatetime(time: TimeLike, tzaware: bool = True) -> np.ndarray:
    if isinstance(time, str):
        d = todatetime(parse(time), tzaware)
    elif isinstance(time, _WheneverExact):
        # An exact instant is unambiguous -- always convert to true UTC,
        # regardless of what `tzaware` says, unlike the `datetime` branch
        # below (which is guessing at what a plain `datetime`'s own
        # tzinfo, or lack of one, actually means).
        d = todatetime(time.to_stdlib(), tzaware=True)
    elif isinstance(time, whenever.PlainDateTime):
        # Naive by construction -- nothing to reinterpret.
        d = todatetime(time.to_stdlib(), tzaware=False)
    elif isinstance(time, whenever.Date):
        d = todatetime(time.to_stdlib(), tzaware)
    elif isinstance(time, datetime):
        if tzaware:
            d = time.astimezone(pytz.utc).replace(
                tzinfo=None
            )  # convert to UTC and strip timezone
        else:
            d = time.replace(tzinfo=None)  # simply strip timezone info, old behavior
    elif isinstance(time, np.datetime64):
        d = todatetime(time.astype(datetime), tzaware)
    elif isinstance(time, date):
        d = todatetime(datetime(time.year, time.month, time.day), tzaware)
    elif isinstance(time, (tuple, list, np.ndarray)):
        d = np.atleast_1d([todatetime(t, tzaware) for t in time]).squeeze()
    elif isinstance(time, pandas.DatetimeIndex):
        d = todatetime(time.to_pydatetime(), tzaware)  # type: ignore[attr-defined]
    else:
        raise TypeError(f"{time} must be representable as datetime.datetime")

    dates = np.atleast_1d(d).ravel()  # type: ignore[arg-type]

    return dates
