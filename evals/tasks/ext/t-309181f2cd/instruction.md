scope warning when using _this in spawned code block
`[2,13]:warning:Local variable "_this" is not from this scope (not private)` when running sqflint over

```sqf
_this spawn {
    hint str _this;
};
```
it does *not* complain when the code block is *call*ed, though.
