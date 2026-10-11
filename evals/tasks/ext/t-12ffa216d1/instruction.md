load_words is not prioritized
Looks like the functionality load_words is not prioritized in the spellchecking.

```
from spellchecker import SpellChecker

known_words = ['covid', 'Covid19']

spell = SpellChecker(language='en')
spell.word_frequency.load_words(known_words)


word = 'coved'
misspelled = spell.unknown(word)
print(spell.correction(allwords))
```

the output of this is `loved`
