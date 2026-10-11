case_insensitive as optional argument?
I have some old code that reads:
```python
from fuzzyfinder import fuzzyfinder
matches = fuzzyfinder(word_before_cursor, fuzzy_words, case_sensitive=True)
```
But I can't see in this project when case_sensitive was ever an option? Am I going crazy? Was case_sensitive the default and the extra parameter I was passing just doing nothing?
