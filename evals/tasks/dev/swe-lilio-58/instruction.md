Unclear error message when an empty calendar is passed to `resample` function.
When executing the following code:
```py
import lilio
from lilio import Calendar
import xarray as xr

ds = xr.load_dataset(path_to_data) # just some sample data
cal = Calendar("12-25") 
# note that no intervals are added to the calendar
# cal.add_intervals("target", length="7d")
# cal.add_intervals("precursor", length="7d")
cal.map_to_data(ds)
data_resampled = lilio.resample(cal, ds)
```

This will trigger the following `ValueError`

```py
File [~/AI4S2S/lilio/lilio/resampling.py:342](https://vscode-remote+wsl-002bubuntu-002d20-002e04.vscode-resource.vscode-cdn.net/home/yangliu/AI4S2S/lilio/docs/notebooks/~/AI4S2S/lilio/lilio/resampling.py:342), in resample(calendar, input_data, how)
    340     _check_valid_resampling_methods(how)
    341 utils.check_timeseries(input_data)
--> 342 utils.check_input_frequency(calendar, input_data)
    343 utils.check_reserved_names(input_data)
    345 if isinstance(input_data, (pd.Series, pd.DataFrame)):

File [~/AI4S2S/lilio/lilio/utils.py:158](https://vscode-remote+wsl-002bubuntu-002d20-002e04.vscode-resource.vscode-cdn.net/home/yangliu/AI4S2S/lilio/docs/notebooks/~/AI4S2S/lilio/lilio/utils.py:158), in check_input_frequency(calendar, data)
    151 """Compare the frequency of (input) data to the frequency of the calendar.
    152 
    153 Note: Pandas and xarray have the builtin function `infer_freq`, but this function is
    154 not robust enough for our purpose, so we have to manually infer the frequency if the
    155 builtin one fails.
    156 """
    157 data_freq = infer_input_data_freq(data)
--> 158 calendar_freq = get_smallest_calendar_freq(calendar)
    160 if calendar_freq < data_freq:
    161     raise ValueError(
    162         "The data is of a lower time resolution than the calendar. "
    163         "This would lead to incorrect data and/or NaN values in the resampled data."
   (...)
    167         f"{str(calendar_freq)}"
    168     )

File [~/AI4S2S/lilio/lilio/utils.py:145](https://vscode-remote+wsl-002bubuntu-002d20-002e04.vscode-resource.vscode-cdn.net/home/yangliu/AI4S2S/lilio/docs/notebooks/~/AI4S2S/lilio/lilio/utils.py:145), in get_smallest_calendar_freq(calendar)
    143 lengthstr = [replace_month_length(ln) if ln[-1] == "M" else ln for ln in lengthstr]
    144 lengths = [pd.Timedelta(ln) for ln in lengthstr]
--> 145 return min(lengths)

ValueError: min() arg is an empty sequence
```

The error message is not informative. It should remind the user to add intervals to the calendar. This needs to be fixed in the check for `resample` function, in `utils` module.
