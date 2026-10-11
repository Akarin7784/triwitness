`timefmt.parse_duration("1h30m")` returns 3630 instead of 5400. Durations like `"2m"` or `"1h30m15s"` are wrong
too; `"45s"` and `"2h"` are fine. Expected: `h` = 3600 s, `m` = 60 s, `s` = 1 s.
