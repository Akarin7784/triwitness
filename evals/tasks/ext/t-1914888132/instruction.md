Sort FileCheckers alphabetically
Whenever I run *flake8* on a large set of code which has multiple violations, I am presented with an apparently deterministic, but not alphabetical order of the files. This makes it hard to work on them in a coordinated manner, as the file list inside the file manager or IDE usually is sorted alphabetically. Current example output, where I would expect `dummies.py` to be displayed before `sample.py`:

```bash
(.env) stefan@localhost:~/projects/samples> flake8 samples/
samples/sample.py:79:1: E501 line too long (100 > 80 characters)
samples/dummies.py:68:7: E265 block comment should start with '# '
```

Skimming through the available options, the documentation and the source code, this does not seem to be supported for now. Judging from the source code, this seems like some hard-coded behavior of `flake8.checker.Manager.report` and therefore hard to implement (or hacky) to fix from the outside.

This might be fixed by simply replacing the iteration over all the checkers inside the aforementioned method by something like the following snippet, although this will not separate files and directories if this is something which should be considered:

```python3
for checker in sorted(self._all_checkers, key=operator.attrgetter('filename')):
   ...
```
