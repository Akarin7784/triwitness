[Feature Request] Debuggable wrapper functions
`@beartype` dynamically wraps each decorated callable with a unique wrapper function efficiently type-checking that callable. That's great, because efficient. But that's also currently invisible to debuggers, because `@beartype` fails to register the Python code underlying these wrapper functions with [the little-known standard `linecache` module](https://docs.python.org/3/library/linecache.html).

This feature request tracks work towards rendering `@beartype` compatible with debuggers. For now, please refer to [this superb writeup by witty QA strongman @posita for a detailed discussion of the exact issue under discussion here – complete with the inevitable working solution infused with wisdom by cautionary AI futurologist @TeamSpen210](https://github.com/beartype/beartype/discussions/84).

Humble gratitude to both @posita and @TeamSpen210 for finally shaming me into doing this thing that desperately needs doing.
