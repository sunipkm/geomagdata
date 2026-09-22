#!/usr/bin/env python
"""
plot graphs of geophysical indices for comparison with other sources

Example
-------
plot all of 2015 (also regenerates this directory's `2015.png`, used by the
top-level README)

python plotindices.py 2015-01-01 2016-01-01
"""
from datetime import timedelta
from pathlib import Path

import pandas
from dateutil.parser import parse
from matplotlib import pyplot as plt

import geomagdata as gi

plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["mathtext.fontset"] = "cm"

if __name__ == "__main__":
    from argparse import ArgumentParser

    p = ArgumentParser()
    p.add_argument(
        "start_stop", help="date or date range of observation yyyy-mm-dd  (START, STOP)", nargs="+"
    )
    a = p.parse_args()

    start = parse(a.start_stop[0])
    if len(a.start_stop) > 1:
        end = parse(a.start_stop[1])
    else:
        end = start + timedelta(days=1)

    dates = pandas.date_range(start, end, freq="3h")

    inds = gi.get_indices(dates).select_dtypes(include="number")

    # %% plot
    fig = plt.figure(figsize=(6.4, 4.8), dpi=300)
    ax = fig.gca()
    inds.plot(ax=ax, linewidth=0.75)
    ax.set_ylabel("index values")
    ax.set_xlabel("time [UTC]")
    ax.grid(True)
    fig.tight_layout()

    fig.savefig(Path(__file__).parent / "2015.png", dpi=300)

    plt.show()
