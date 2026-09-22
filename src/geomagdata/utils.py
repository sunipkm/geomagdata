from __future__ import annotations

import datetime
from collections.abc import Sequence

import numpy as np


def yeardec2datetime(
    atime: float | Sequence[float] | np.ndarray,
) -> datetime.datetime | list[datetime.datetime]:
    """
    Convert decimal year to datetime.datetime
    http://stackoverflow.com/questions/19305991/convert-fractional-years-to-a-real-date-in-python

    Parameters
    ----------

    atime: float, int, or a sequence/array of either
        time in yyyy.fracyear

    Results
    -------
    T: datetime.datetime or list[datetime.datetime]
        time converted; a list if `atime` was a sequence

    """
    if isinstance(atime, (float, int)):  # typically a float
        year = int(atime)
        remainder = atime - year
        boy = datetime.datetime(year, 1, 1)
        eoy = datetime.datetime(year + 1, 1, 1)
        seconds = remainder * (eoy - boy).total_seconds()

        T = boy + datetime.timedelta(seconds=seconds)

    elif isinstance(atime[0], float):
        return [yeardec2datetime(t) for t in atime]  # type: ignore[misc]
    else:
        raise TypeError(type(atime))

    return T
