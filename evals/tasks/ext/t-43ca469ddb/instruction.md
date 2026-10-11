`pauli.py` should raise an error
## Before reporting this bug:
- [x] Verify there is not an existing issue for it already
- [x] You are using the latest version of `toqito` with a python version `>=3.10`

## Describe the bug

Upon passing `ind >=4` or `ind != {'X', 'Y', 'Z', 'I'}`  to [toqito/matrices/pauli.py]([链接已移除]) we always receive an identity matrix as output

## To Reproduce

```python
from toqito.matrices import pauli

print(pauli(5))
```
 gives

```bash
[[1. 0.]
 [0. 1.]]
```

## Expected behavior

raise a `ValueError` for arguments that are irrelevant for the function
