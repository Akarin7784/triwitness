`csvkit_lite.parse.parse_rows` raises `IndexError: list index out of range` when the input contains a blank line
(for example a trailing empty line). Blank lines should be skipped.
