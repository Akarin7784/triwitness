Rendering Some Lua Tables False
**Example code:**
```lua 
local Table = {"a", "b", "c"};
```

**I have used ast.to_lua_source for turning the ast into a lua code**
**The output i got:**
```lua
local Table = {
    1 = "a",
    2 = "b",
    3 = "c",
}
;
```

**What it should be:**
```lua
local Table = {
    [1] = "a",
    [2] = "b",
    [3] = "c",
}
;
```


**Used python code:**
```py
from luaparser import ast

src = """
local Table = {"a", "b", "c"};
"""

tree = ast.parse(src)
print(ast.to_lua_source(tree))
```
