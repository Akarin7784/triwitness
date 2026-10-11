Ignore empty strings when deducing column types
An empty cell (not a cell containing None, but containing `""` or `b""`) forces the column type to be `str`, even if the rest of the cells contain eg. numeric data.  A cell containing None is ignored for type deduction; and, is later replaced by the `missingval` value (such as `"?"`).

This makes it difficult to format sparse tables sensibly (columns always forced to `str` type).  One can remove all blank data and replace with None, but:

It makes it impossible to distinguish between "missing" (`None`) and "blank" (`""`) cells, without messing up the typing of the rest of the column.  When fixed, missing cells would be denoted by missingval eg. "?", while empty cells would simply ... remain empty.  

This makes it easy to display sparse tables where a few cells still require input, while many cells are ignored/unimportant (for example), while maintaining proper column formatting for the remaining data.

The idea of a blank value being of a certain type (`str`), instead of an empty instance of the deduced type of the rest of the column's values seems draconian.

This is an easy 3-line fix, and doesn't interfere with any existing unit tests.

Pull forthcoming...
