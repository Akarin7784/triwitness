Terminal(X) == Variable(X)
The design of Variables and Terminals as CFGObjects enables comparing them - resulting in "True" if they have the same value. This is highly undesirable (I think?). Terminals and Variables should never be equal...

[链接已移除]

This breaks i.e. the following (after resolving #32 )
```python
first_lang = rf"""S -> "TER:S" """
second_lang = rf"""S -> a"""
concat = CFG.from_text(first_lang).concatenate(CFG.from_text(second_lang))
assert "Sa" in concat
```

Proposed fix: `CFGObject` -> `Variable`
