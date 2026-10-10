#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p lilio
cat > lilio/calendar.py <<'TW_EOF'
"""Lilio's main Calendar module."""
import copy
import re
import warnings
from os import linesep
from typing import List
from typing import Literal
from typing import Tuple
from typing import Union
import pandas as pd
import xarray as xr
from pandas.tseries.offsets import DateOffset
from lilio import _plot
from lilio import utils


_MappingYears = Tuple[Literal["years"], int, int]
_MappingData = Tuple[Literal["data"], pd.Timestamp, pd.Timestamp]


class Interval:
    """Basic construction element of calendar for defining precursors and targets."""

    def __init__(
        self,
        role: Literal["target", "precursor"],
        length: Union[str, dict],
        gap: Union[str, dict] = "0d",
    ) -> None:
        """Construct the basic element of the calendar.

        The Interval is characterised by its type (either target or precursor), its
        length and the gap between it and the previous interval of its type (or the
        anchor date, if the interval is the first target/first precursor).

        Args:
            role: The type of interval. Either "target" or "precursor".
            length: The length of the interval. This can either be a pandas-like
                frequency string (e.g. "10d", "2W", or "3M"), or a pandas.DateOffset
                compatible dictionary such as {days=10}, {weeks=2}, or
                {months=1, weeks=2}.
            gap: The gap between the previous interval and this interval. Valid inputs
                are the same as the length keyword argument. Defaults to "0d".

        Example:
            >>> from lilio import Interval
            >>> iv = Interval("target", length="7d")
            >>> iv
            Interval(role='target', length='7d', gap='0d')

            You can modify the interval's properties in-place:

            >>> iv.gap = "1W"
            >>> iv
            Interval(role='target', length='7d', gap='1W')

        """
        self.length = length
        self.gap = gap
        self._role = role
        self._target = role == "target"

        self._gap_dateoffset: pd.DateOffset
        self._length_dateoffset: pd.DateOffset

        # TO DO: support lead_time
        # self.lead_time = lead_time

    @property
    def is_target(self):
        """Return whether this Intervals is a target interval."""
        return self._target

    @property
    def role(self):
        """Return the type of interval."""
        return self._role

    @property
    def length(self):
        """Return the length of the interval, as a pandas.DateOffset."""
        return self._length

    @length.setter
    def length(self, value: Union[str, dict]):
        self._length = value
        if isinstance(value, str):
            self._length_dateoffset = DateOffset(
                **utils.parse_freqstr_to_dateoffset(value)
            )
        else:
            self._length_dateoffset = DateOffset(**value)

    @property
    def length_dateoffset(self):
        """Return the length property as a dateoffset."""
        return self._length_dateoffset

    @property
    def gap(self):
        """Returns the gap of the interval, as a pandas.DateOffset."""
        return self._gap

    @gap.setter
    def gap(self, value: Union[str, dict]):
        self._gap = value
        if isinstance(value, str):
            self._gap_dateoffset = DateOffset(
                **utils.parse_freqstr_to_dateoffset(value)
            )
        else:
            self._gap_dateoffset = DateOffset(**value)

    @property
    def gap_dateoffset(self):
        """Get the gap property as a dateoffset."""
        return self._gap_dateoffset

    def __repr__(self):
        """Return a string representation of the Interval class."""
        props = [
            ("role", self.role),
            ("length", self.length),
            ("gap", self.gap),
        ]

        propstr = ", ".join([f"{k}={repr(v)}" for k, v in props])
        return f"{self.__class__.__name__}({propstr})"


class Calendar:
    """Build a calendar from scratch with basic construction elements."""

    def __init__(
        self,
        anchor: str,
        allow_overlap: bool = False,
        mapping: Union[
            None,
            _MappingYears,
            _MappingData,
        ] = None,
        intervals: Union[None, List[Interval]] = None,
    ):
        """Instantiate a basic container for building calendar using basic blocks.

        This is a highly flexible calendar which allows the user to build their own
        calendar with the basic building blocks of target and precursor periods.

        Users have the freedom to create calendar with customized intervals, gap
        between intervals, and even overlapped intervals. They need to manage the
        calendar themselves.

        Some shorthand calendars, such as a `daily_calendar`, `weekly_calendar` and
        `monthly_calendar` are available in lilio.calendar_shorthands. These can be used
        to easily construct basic calendars with only a few parameters, but do not have
        the flexibility that this calendar builder module provides.

        Args:
            anchor: String denoting the anchor date. The following inputs are valid:
                    - "MM-DD" for a month and day. E.g. "12-31".
                    - "MM" for only a month, e.g. "4" for March.
                    - English names and abbreviations of months. E.g. "December" or
                        "jan".
                    - "Www" for a week number, e.g. "W05" for the fifth week of the
                        year.
                    - "Www-D" for a week number plus day of week. E.g. "W01-4" for the
                        first thursday of the year.
            allow_overlap: If overlapping intervals between years is allowed or not.
                Default behaviour is False, which means that anchor years will be
                skipped to avoid data being shared between anchor years.
            mapping: Calendar mapping. Input in the form: ("years", 2000, 2020) or
                ("data", pd.Timestamp("2000-01-01"), pd.Timestamp("2020-01-01")). The
                calendar mapping is usually set with the `map_years` or `map_to_data`
                methods.
            intervals: A list of Interval objects that should be appended to the
                calendar when it is initialized.

        Example:
            Instantiate a custom calendar and appending target/precursor periods.

            >>> import lilio
            >>> calendar = lilio.Calendar(anchor="12-31")
            >>> calendar  # doctest: +NORMALIZE_WHITESPACE
            Calendar(
                anchor='12-31',
                allow_overlap=False,
                mapping=None,
                intervals=None
            )

        """
        self._anchor, self._anchor_fmt = self._parse_anchor(anchor)
        self._allow_overlap = allow_overlap
        self.targets: List[Interval] = []
        self.precursors: List[Interval] = []

        self._first_year: Union[None, int] = None
        self._last_year: Union[None, int] = None

        if intervals is not None:
            # pylint: disable=expression-not-assigned
            [self._append(iv) for iv in intervals]

        self._mapping: Union[None, Literal["years", "data"]]
        self._set_mapping(mapping)

    @property
    def n_targets(self) -> int:
        """Return the number of targets."""
        return len(self.targets)

    @property
    def n_precursors(self) -> int:
        """Return the number of precursors."""
        return len(self.precursors)

    @property
    def anchor(self):
        """Return the anchor."""
        return self._anchor

    @anchor.setter
    def anchor(self, value):
        self._anchor, self._anchor_fmt = self._parse_anchor(value)

    @property
    def allow_overlap(self):
        """Returns the allow_overlap: if overlapping intervals are allowed or not."""
        return self._allow_overlap

    @allow_overlap.setter
    def allow_overlap(self, value: bool):
        if isinstance(value, bool):
            self._allow_overlap = value
        else:
            raise ValueError(
                f"allow_overlap should be either True or False, not {value}"
                f"of type {type(value)}"
            )

    @property
    def mapping(self) -> Union[None, Literal["years", "data"]]:
        """Return the mapping of the calendar. Either  None, "years", or "data"."""
        return self._mapping

    def add_intervals(
        self,
        role: Literal["target", "precursor"],
        length: str,
        gap: str = "0d",
        n: int = 1,
    ) -> None:
        """Add one or more intervals to the calendar.

        The interval can be a target or a precursor, and can be defined by its length,
        a possible gap between this interval and the preceding interval.

        Args:
            role: Either a 'target' or 'precursor' interval(s).
            length: The length of the interval(s), in a format of '5d' for five days,
                '2W' for two weeks, or '1M' for one month.
            gap: The gap between this interval and the preceding target/precursor
                interval. Same format as the length argument.
            n: The number of intervals which should be added to the calendar. Defaults
                to 1.
        """
        if not isinstance(n, int):
            raise ValueError(
                "Please input an 'int' type for the 'n' argument." f" Not a {type(n)}."
            )
        if n <= 0:
            raise ValueError(
                "The number of intervals 'n' has to be 1 or greater, " f"not '{n}'."
            )

        if role in ["target", "precursor"]:
            for _ in range(n):
                self._append(Interval(role, length, gap))
        else:
            raise ValueError(
                f"Type '{role}' is not a valid interval type. Please "
                "choose between 'target' and 'precursor'"
            )

    def _get_anchor(self, year: int) -> pd.Timestamp:
        """Generate an anchor timestamp for your specific calendar.

        The method should return the exact timestamp of the end of the anchor_year's
        0 interval, e.g., for the AdventCalendar:
        pd.Timestamp(year, self.month, self.day)

        Args:
            year (int): anchor year for which the anchor timestamp should be generated

        Returns:
            pd.Timestamp: Timestamp at the end of the anchor_years interval 0.
        """
        return pd.to_datetime(
            f"{year}-" + self._anchor, format="%Y-" + self._anchor_fmt
        )

    def _parse_anchor(self, anchor_str: str) -> Tuple[str, str]:
        """Parse the user-input anchor.

        Args:
            anchor_str: Anchor string in the right formatting.

        Returns:
            Datetime formatter to parse the anchor into a date.
        """
        # non string check
        if not isinstance(anchor_str, str):
            raise ValueError("Anchor input must be a string with expected format.")
        # format match
        if re.fullmatch("\\d{1,2}-\\d{1,2}", anchor_str):
            utils.check_month_day(*[int(x) for x in anchor_str.split("-")])
            fmt = "%m-%d"
        elif re.fullmatch("\\d{1,2}", anchor_str):
            utils.check_month_day(int(anchor_str))
            fmt = "%m"
        elif re.fullmatch("W\\d{1,2}-\\d", anchor_str):
            utils.check_week_day(*[int(x) for x in anchor_str[1:].split("-")])
            fmt = "W%W-%w"
        elif re.fullmatch("W\\d{1,2}", anchor_str):
            utils.check_week_day(int(anchor_str[1:]))
            fmt = "W%W-%w"
            anchor_str += "-1"
        elif anchor_str.lower() in utils.get_month_names():
            anchor_str = str(utils.get_month_names()[anchor_str.lower()])
            fmt = "%m"
        else:
            raise ValueError(
                f"Anchor input '{anchor_str}' does not match expected format."
            )
        return anchor_str, fmt

    def _append(self, interval):
        """Append target/precursor periods to the calendar."""
        if interval.is_target:
            self.targets.append(interval)
        else:
            self.precursors.append(interval)

    def _map_year(self, year: int) -> pd.Series:
        """Return a concrete IntervalIndex for the given year.

        Since our calendars are used to study periodic events, they are first
        instantiated without specific year(s). This method adds a specific year
        to the calendar and returns an intervalindex, mapping the
        Calendar to the given year.

        Intended for internal use, in conjunction with map_years or map_to_data.

        Args:
            year: The year for which the Calendar will be realized

        Returns:
            Pandas Series filled with Intervals of the calendar's frequency, counting
            backwards from the calendar's achor.
        """
        intervals_target = self._concatenate_periods(year, self.targets, True)
        intervals_precursor = self._concatenate_periods(year, self.precursors, False)

        year_intervals = intervals_precursor[::-1] + intervals_target

        # turn the list of intervals into pandas series
        year_intervals = pd.Series(year_intervals[::-1], name=year)
        year_intervals.index.name = "i_interval"
        return year_intervals

    def _concatenate_periods(self, year, list_periods, is_target):
        # generate intervals based on the building blocks
        intervals = []
        if is_target:
            # build from left to right
            left_date = self._get_anchor(year)
            # loop through all the building blocks to
            for block in list_periods:
                left_date += block.gap_dateoffset
                right_date = left_date + block.length_dateoffset
                intervals.append(pd.Interval(left_date, right_date, closed="left"))
                # update left date
                left_date = right_date
        else:
            # build from right to left
            right_date = self._get_anchor(year)
            # loop through all the building blocks to
            for block in list_periods:
                right_date -= block.gap_dateoffset
                left_date = right_date - block.length_dateoffset
                intervals.append(pd.Interval(left_date, right_date, closed="left"))
                # update right date
                right_date = left_date

        return intervals

    def _get_skip_nyears(self) -> int:
        """Determine how many years need to be skipped to avoid overlapping data.

        Required to prevent information leakage between anchor years.

        Returns:
            int: Number of years that need to be skipped.
        """
        if self._allow_overlap:
            return 0

        proto_year = 2000
        skip_years = 0

        start_calendar = self._get_anchor(proto_year)
        for prec in self.precursors:
            start_calendar -= prec.gap_dateoffset
            start_calendar -= prec.length_dateoffset

        while True:
            prev_end_calendar = self._get_anchor(proto_year - 1 - skip_years)
            for target in self.targets:
                prev_end_calendar += target.gap_dateoffset
                prev_end_calendar += target.length_dateoffset
            if prev_end_calendar > start_calendar:
                skip_years += 1
            else:
                break

        return skip_years

    def map_years(self, start: int, end: int):
        """Add a start and end year mapping to the calendar.

        If the start and end years are the same, the intervals for only that single
        year are returned by calendar.get_intervals().

        Args:
            start: The first year for which the calendar will be realized
            end: The last year for which the calendar will be realized

        Returns:
            The calendar mapped to the input start and end year.
        """
        if start > end:
            raise ValueError("The start year cannot be greater than the end year")

        self._first_year = start
        self._last_year = end
        self._mapping = "years"

        self._first_timestamp = None
        self._last_timestamp = None

        return self

    def map_to_data(
        self,
        input_data: Union[pd.Series, pd.DataFrame, xr.Dataset, xr.DataArray],
    ):
        """Map the calendar to input data period.

        Stores the first and last intervals of the input data to the calendar, so that
        the intervals can cover the data to the greatest extent.

        Args:
            input_data: Input data for datetime mapping. Its index must be either
                pandas.DatetimeIndex, or an xarray `time` coordinate with datetime
                data.

        Returns:
            The calendar mapped to the input data period.
        """
        utils.check_timeseries(input_data)

        # check the datetime order of input data
        if isinstance(input_data, (pd.Series, pd.DataFrame)):
            self._first_timestamp = input_data.index.min()
            self._last_timestamp = input_data.index.max()
        else:
            self._first_timestamp = pd.Timestamp(input_data.time.min().values)
            self._last_timestamp = pd.Timestamp(input_data.time.max().values)

        self._mapping = "data"
        self._first_year = None
        self._last_year = None

        return self

    def _set_year_range_from_timestamps(self):
        min_year = self._first_timestamp.year  # type: ignore
        max_year = self._last_timestamp.year  # type: ignore

        # ensure that the input data could always cover the advent calendar
        # last date check
        if self._map_year(max_year).iloc[0].right > self._last_timestamp:
            max_year -= 1
        # first date check
        while self._map_year(min_year).iloc[-1].right <= self._first_timestamp:
            min_year += 1

        # map year(s) and generate year realized advent calendar
        if max_year >= min_year:
            self._first_year = min_year
            self._last_year = max_year
        else:
            raise ValueError(
                "The input data could not cover the target advent calendar."
            )

        return self

    def _set_mapping(self, mapping):
        if mapping is None:
            self._mapping = None
        elif mapping[0] == "years":
            self.map_years(mapping[1], mapping[2])
        elif mapping[0] == "data":
            self._mapping = "data"
            self._first_timestamp = mapping[1]
            self._last_timestamp = mapping[2]
        else:
            raise ValueError(
                "Unknown mapping passed to calendar. Valid options are"
                "either 'years' or 'data'."
            )

    def _rename_intervals(self, intervals: pd.DataFrame) -> pd.DataFrame:
        """Add target labels to the header row of the intervals.

        Args:
            intervals (pd.Dataframe): Dataframe with intervals.

        Returns:
            pd.Dataframe: Dataframe with target periods labelled, sorted by their
                i_interval value.
        """
        # rename precursors
        intervals = intervals.rename(
            columns={
                i: self.n_targets - i - 1
                for i in range(self.n_targets, len(intervals.columns))
            }
        )

        # rename targets
        intervals = intervals.rename(
            columns={i: self.n_targets - i for i in range(self.n_targets)}
        )

        return intervals.sort_index(axis=1)

    def get_intervals(self) -> pd.DataFrame:
        """Retrieve updated intervals from the Calendar object."""
        if self._mapping is None:
            raise ValueError(
                "Cannot retrieve intervals without map_years or "
                "map_to_data having configured the calendar."
            )
        if self._mapping == "data":
            self._set_year_range_from_timestamps()

        year_range = range(
            self._last_year,  # type: ignore
            self._first_year - 1,  # type: ignore
            -(self._get_skip_nyears() + 1),  # type: ignore
        )

        intervals = pd.concat([self._map_year(year) for year in year_range], axis=1).T

        intervals = self._rename_intervals(intervals)

        intervals.index.name = "anchor_year"
        return intervals.sort_index(axis=0, ascending=False)

    def show(self) -> pd.DataFrame:
        """Display the intervals the Calendar will generate for the current setup.

        Returns:
            pd.Dataframe: Dataframe containing the calendar intervals.
        """
        return self.get_intervals()

    def __repr__(self) -> str:
        """Return a string representation of the Calendar."""
        intervals = self.targets + self.precursors
        if len(intervals) == 0:
            intervals_str = repr(None)
        else:
            intervals_str = (
                f"[{linesep}\t\t"
                + f",{linesep}\t\t".join([repr(iv) for iv in intervals])
                + f"{linesep}\t]"
            )

        if self._mapping == "years":
            mapping = ("years", self._first_year, self._last_year)
        elif self._mapping == "data":
            mapping = ("data", self._first_timestamp, self._last_timestamp)
        else:
            mapping = None

        props = [
            ("anchor", repr(self.anchor)),
            ("allow_overlap", repr(self.allow_overlap)),
            ("mapping", repr(mapping)),
            ("intervals", intervals_str),
        ]

        propstr = f"{linesep}\t" + f",{linesep}\t".join([f"{k}={v}" for k, v in props])
        return f"{self.__class__.__name__}({propstr}{linesep})".replace("\t", "    ")

    def visualize(  # noqa: PLR0913 (too-many-arguments)
        self,
        n_years: int = 3,
        interactive: bool = False,
        relative_dates: bool = False,
        show_length: bool = False,
        add_legend: bool = True,
        ax=None,
        **bokeh_kwargs,
    ) -> None:
        """Plot a visualization of the current calendar setup, to aid in user setup.

        Note: The interactive visualization requires the `bokeh` package to be installed
        in the active Python environment.

        Args:
            n_years: Sets the maximum number of anchor years that should be shown. By
                default only the most recent 3 are visualized, to ensure that they
                fit within the plot.
            interactive: If False, matplotlib will be used for the visualization. If
                True, bokeh will be used.
            relative_dates: Toggles if the intervals should be displayed relative to the
                anchor date, or as absolute dates.
            show_length: Toggles if the frequency of the intervals should be displayed.
                Defaults to False (Matplotlib plotter only).
            add_legend: Toggles if a legend should be added to the plot (Matplotlib
                only)
            ax: Matplotlib axis object to plot the visualization into.
            **bokeh_kwargs: Keyword arguments to pass to Bokeh's plotting.figure. See
                https://docs.bokeh.org/en/latest/docs/reference/plotting/figure.html
                for a list of possible keyword arguments.
        """
        calendar = copy.deepcopy(self)
        if calendar._mapping is None:  # pylint: disable=protected-access
            calendar.map_years(2000, 2000)
            if not relative_dates:
                print(
                    "Setting relative_dates=True. To see absolute dates, first call "
                    "calendar.map_years or calendar.map_data"
                )
                relative_dates = True
            add_yticklabels = False
        else:
            add_yticklabels = True

        n_years = max(n_years, 1)
        n_years = min(n_years, len(calendar.get_intervals().index))

        if interactive:
            utils.assert_bokeh_available()
            # pylint: disable=import-outside-toplevel
            from ._bokeh_plots import bokeh_visualization

            if ax is not None:
                warnings.warn(
                    "\n  ax is only a valid keyword argument for the non-interactive"
                    "\n  matplotlib backend. Bokeh's figure can be controlled by"
                    "\n  passing Bokeh figure keyword arguments (e.g. width=800).",
                    UserWarning,
                    stacklevel=1,
                )
            bokeh_visualization(
                calendar, n_years, relative_dates, add_yticklabels, **bokeh_kwargs
            )
        else:
            if bokeh_kwargs:
                warnings.warn(
                    "\n  kwargs for bokeh have been passed to visualize(), but the"
                    "\n  matplotlib backend does not support these. Use the 'ax' kwarg"
                    "\n  instead to control the generated figure.",
                    UserWarning,
                    stacklevel=1,
                )

            _plot.matplotlib_visualization(
                calendar,
                n_years,
                relative_dates,
                show_length,
                add_legend,
                add_yticklabels,
                ax=ax,
            )

    @property
    def flat(self) -> pd.DataFrame:
        """Returns the flattened intervals."""
        return self.get_intervals().stack()  # type: ignore
TW_EOF
mkdir -p lilio
cat > lilio/resampling.py <<'TW_EOF'
"""The implementation of the resampling methods for use with the Calendar."""
import typing
from typing import Callable
from typing import List
from typing import Literal
from typing import Union
from typing import overload
import numpy as np
import pandas as pd
import xarray as xr
from lilio import utils
from lilio._attrs import add_attrs
from lilio.calendar import Calendar


# List of numpy statistical methods, with a single input argument and a single output.
ResamplingMethod = Literal[
    "mean",
    "min",
    "max",
    "median",
    "std",
    "var",
    "ptp",
    "nanmean",
    "nanmedian",
    "nanstd",
    "nanvar",
    "sum",
    "nansum",
    "size",
    "count_nonzero",
]
VALID_METHODS = typing.get_args(ResamplingMethod)


def _check_valid_resampling_methods(method: ResamplingMethod):
    """Check if a method is valid as a (numpy) resampling method."""
    if method not in VALID_METHODS:
        raise ValueError(
            f"{method} is not a valid resampling method. Choose from: {VALID_METHODS}"
        )


def _mark_target_period(
    input_data: Union[pd.DataFrame, xr.Dataset]
) -> Union[pd.DataFrame, xr.Dataset]:
    """Mark interval periods that fall within the given number of target periods.

    Pass a pandas Series/DataFrame with an 'i_interval' column, or an xarray
    DataArray/Dataset with an 'i_interval' coordinate axis. It will return an
    object with an added column in the Series/DataFrame or an
    added coordinate axis in the DataSet called 'target'. This is a boolean
    indicating whether the index time interval is a target period or not. This is
    determined by the instance variable 'n_targets'.

    Args:
        input_data: Input data for resampling. For a Pandas object, one of its
        columns must be called 'i_interval'. An xarray object requires a coordinate
        axis named 'i_interval' containing an interval counter for every period.

    Returns:
        Input data with boolean marked target periods, similar data format as
            given inputs.
    """
    if isinstance(input_data, (pd.Series, pd.DataFrame)):
        input_data["is_target"] = np.ones(input_data.index.size, dtype=bool)
        input_data["is_target"] = input_data["is_target"].where(
            input_data["i_interval"] > 0, other=False
        )

    else:
        # input data is xr.Dataset
        target = input_data["i_interval"] > 0
        input_data = input_data.assign_coords(coords={"is_target": target})

    return input_data


def _resample_bins_constructor(
    intervals: Union[pd.Series, pd.DataFrame]
) -> pd.DataFrame:
    """Restructures the interval object into a tidy DataFrame.

    Args:
        intervals: the output interval `pd.Series` or `pd.DataFrame` from the
            `map_to_data` function.

    Returns:
        Pandas DataFrame with 'anchor_year', 'i_interval', and 'interval' as
            columns.
    """
    # Make a tidy dataframe where the intervals are linked to the anchor year
    if isinstance(intervals, pd.DataFrame):
        bins = intervals.copy()
        bins.index.rename("anchor_year", inplace=True)
        bins = bins.melt(
            var_name="i_interval", value_name="interval", ignore_index=False
        )
        bins = bins.sort_values(by=["anchor_year", "i_interval"])
    else:
        # Massage the dataframe into the same tidy format for a single year
        bins = pd.DataFrame(intervals)
        bins = bins.melt(
            var_name="anchor_year", value_name="interval", ignore_index=False
        )
        bins.index.rename("i_interval", inplace=True)
    bins = bins.reset_index()

    return bins


def _contains(interval_index: pd.IntervalIndex, timestamps) -> np.ndarray:
    """Check elementwise if the intervals contain the timestamps.

    Will return a boolean array of the shape (n_timestamps, n_intervals).

    Args:
        interval_index: An IntervalIndex containing all intervals that should be
            checked.
        timestamps: A 1-D array containing

    Returns:
        np.ndarray: 2-D mask array
    """
    if interval_index.closed_left:
        a = np.greater_equal(timestamps, interval_index.left.values[np.newaxis].T)
    else:
        a = np.greater(timestamps, interval_index.left.values[np.newaxis].T)
    if interval_index.closed_right:
        b = np.less_equal(timestamps, interval_index.right.values[np.newaxis].T)
    else:
        b = np.less(timestamps, interval_index.right.values[np.newaxis].T)
    return a & b


def _resample_pandas(
    calendar: Calendar,
    input_data: Union[pd.Series, pd.DataFrame],
    how: Union[ResamplingMethod, Callable[[np.ndarray], np.ndarray]],
) -> pd.DataFrame:
    """Resample Pandas data.

    Args:
        calendar: Mapped Lilio Calendar object.
        input_data: Data provided by the user to the `resample` function
        how: Which resampling method should be used. Can also be a function that takes a
            single input argument and has a single output argument.

    Returns:
        pd.DataFrame: DataFrame containing the intervals and data resampled to
            these intervals.
    """
    resampling_method = getattr(np, how) if isinstance(how, str) else how

    if isinstance(input_data, pd.Series):
        name = "data" if input_data.name is None else input_data.name
        input_data = pd.DataFrame(input_data.rename(name))

    data = _resample_bins_constructor(calendar.get_intervals())
    contains_matrix = _contains(
        pd.IntervalIndex(data.interval.values), input_data.index.values
    )

    utils.check_empty_intervals(
        indices_list=[np.argwhere(row).T[0] for row in contains_matrix]
    )

    for colname in input_data.columns:
        resampled_data = np.zeros(contains_matrix.shape[0])
        for i, row in enumerate(contains_matrix):
            resampled_data[i] = resampling_method(input_data[colname].values[row])
        data[colname] = resampled_data

    return data


def _resample_dataset(
    calendar: Calendar,
    input_data: xr.Dataset,
    how: Union[ResamplingMethod, Callable[[np.ndarray], np.ndarray]],
) -> xr.Dataset:
    """Resample xarray data.

    Args:
        calendar: A mapped Lilio Calendar object
        input_data (xr.DataArray or xr.Dataset): Data provided by the user to the
            `resample` function
        how: Which resampling method should be used. Can also be a function that takes a
            single input argument and has a single output argument.

    Returns:
        xr.Dataset: Dataset containing the intervals and data resampled to
            these intervals.
    """
    resampling_method = getattr(np, how) if isinstance(how, str) else how
    data = calendar.flat.to_xarray().rename("interval")
    data = data.to_dataset()
    data = data.stack(anch_int=("anchor_year", "i_interval"))

    intervals = pd.IntervalIndex(data["interval"].values)
    timesteps = input_data["time"].to_numpy()

    indices_list: List[np.ndarray] = [np.ndarray(0)] * len(intervals)
    for i in range(len(intervals)):
        row = _contains(intervals[[i]], timesteps)[0]
        indices_list[i] = np.argwhere(row).T[0]

    utils.check_empty_intervals(indices_list)

    # Separate data with time dims (should be resampled), from data without time dims
    #   (which does not need resampling).
    input_data_time = input_data[
        [var for var in input_data.data_vars if "time" in input_data[var].dims]
    ]
    input_data_nontime = input_data[
        [var for var in input_data.data_vars if "time" not in input_data[var].dims]
    ]

    data_list = [xr.Dataset] * len(intervals)
    for i in range(len(intervals)):
        data_list[i] = xr.apply_ufunc(
            resampling_method,
            input_data_time.isel(time=indices_list[i]),
            input_core_dims=[["time"]],
            output_core_dims=[[]],
            vectorize=True,
            dask="parallelized",  # only does something when data is a Dask array
            dask_gufunc_kwargs={"allow_rechunk": True},  # Same as above
        )

    input_data_resampled = xr.concat(data_list, dim="anch_int")  # type: ignore

    if input_data_nontime.data_vars:
        data = xr.merge(
            [data, input_data_nontime, input_data_resampled]  # type: ignore
        )
    else:
        data = xr.merge([data, input_data_resampled])  # type: ignore

    data = data.unstack()
    data = utils.convert_interval_to_bounds(data)
    data = data.transpose("anchor_year", "i_interval", ...)
    return data.sortby("anchor_year", "i_interval")


@overload
def resample(calendar: Calendar, input_data: xr.Dataset) -> xr.Dataset:
    ...


@overload
def resample(calendar: Calendar, input_data: xr.DataArray) -> xr.DataArray:
    ...


@overload
def resample(
    calendar: Calendar, input_data: Union[pd.Series, pd.DataFrame]
) -> pd.DataFrame:
    ...


def resample(
    calendar: Calendar,
    input_data: Union[pd.Series, pd.DataFrame, xr.DataArray, xr.Dataset],
    how: Union[ResamplingMethod, Callable[[np.ndarray], np.ndarray]] = "mean",
) -> Union[pd.DataFrame, xr.DataArray, xr.Dataset]:
    """Resample input data to the Calendar's intervals.

    Pass a pandas Series/DataFrame with a datetime axis, or an
    xarray DataArray/Dataset with a datetime coordinate called 'time'.
    It will return the same object with the datetimes resampled onto
    the Calendar's Index by binning the data into the Calendar's intervals
    and calculating the mean of each bin.

    The default behavior is to calculate the mean for each interval. However, many other
    statistics can be calculated, namely:
        - mean, min, max, median
        - std, var, ptp (peak-to-peak)
        - nanmean, nanmedian, nanstd, nanvar
        - sum, nansum, size, count_nonzero

    "size" will compute the number of datapoints that are in each interval, and can be
    used to check if the input data is of a sufficiently high resolution to be resampled
    to the calendar.

    Note: this function is intended for upscaling operations, which means
    the calendar frequency is larger than the original frequency of input data (e.g.
    `freq` is "7days" and the input is daily data). It supports downscaling
    operations but the user need to be careful since the returned values may contain
    "NaN".

    Args:
        calendar: Calendar object with either a map_year or map_to_data mapping.
        input_data: Input data for resampling. For a Pandas object its index must be
            either a pandas.DatetimeIndex. An xarray object requires a dimension
            named 'time' containing datetime values.
        how: Which method for resampling should be used. Either a string or function.
            The following methods are supported as a string input:
                mean, min, max, median
                std, var, ptp (peak-to-peak)
                nanmean, nanmedian, nanstd, nanvar
                sum, nansum, size, count_nonzero
            Alternatively, a function can be passed. For example
            `resample(how=np.mean)`.

    Raises:
        UserWarning: If the calendar frequency is smaller than the frequency of
            input data

    Returns:
        Input data resampled based on the calendar frequency, similar data format as
            given inputs.

    Example:
        Assuming the input data is pd.DataFrame containing random values with index
        from 2021-11-11 to 2021-11-01 at daily frequency.

        >>> import lilio
        >>> import pandas as pd
        >>> import numpy as np
        >>> cal = lilio.daily_calendar(anchor="12-31", length="180d")
        >>> time_index = pd.date_range("20191201", "20211231", freq="1d")
        >>> var = np.arange(len(time_index))
        >>> input_data = pd.Series(var, index=time_index)
        >>> cal = cal.map_to_data(input_data)
        >>> bins = lilio.resample(cal, input_data)
        >>> bins # doctest: +NORMALIZE_WHITESPACE
            anchor_year  i_interval                  interval   data  is_target
        0          2019          -1  [2019-07-04, 2019-12-31)   14.5      False
        1          2019           1  [2019-12-31, 2020-06-28)  119.5       True
        2          2020          -1  [2020-07-04, 2020-12-31)  305.5      False
        3          2020           1  [2020-12-31, 2021-06-29)  485.5       True
    """
    if calendar.mapping is None:
        raise ValueError("Generate a calendar map before calling resample")
    if calendar.n_targets + calendar.n_precursors == 0:
        raise ValueError("The calendar has no intervals: resampling is not possible.")

    if isinstance(how, str):
        _check_valid_resampling_methods(how)
    utils.check_timeseries(input_data)
    utils.check_input_frequency(calendar, input_data)
    utils.check_reserved_names(input_data)

    if isinstance(input_data, (pd.Series, pd.DataFrame)):
        resampled_data = _resample_pandas(calendar, input_data, how)
    elif isinstance(input_data, xr.DataArray):
        da_name = "data" if input_data.name is None else input_data.name
        input_data.name = da_name
        resampled_data = _resample_dataset(calendar, input_data.to_dataset(), how)
    else:
        resampled_data = _resample_dataset(calendar, input_data, how)

    resampled_data = _mark_target_period(resampled_data)

    if isinstance(input_data, xr.DataArray):
        resampled_dataarray = resampled_data[da_name]
        resampled_dataarray.attrs = input_data.attrs
        add_attrs(resampled_dataarray, calendar)
        return resampled_dataarray
    if isinstance(input_data, xr.Dataset):
        resampled_data.attrs = input_data.attrs
        add_attrs(resampled_data, calendar)
    return resampled_data
TW_EOF
