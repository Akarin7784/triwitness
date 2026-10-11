Autocomplete builtin names
Currently if autocompleting a prompt like

```
hlp |
```

we only look at top-level packages and modules. We should also be including names of builtins.
