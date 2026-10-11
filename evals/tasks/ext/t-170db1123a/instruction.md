tabulate prints "f i r s t r o w" as headers for empty data
I have a use case where i get data about errors received. In that, I keep the headers in the data itself, and use the `firstrow` feature to print. But there are times when there is no error, so the entire data is empty (even the headers are not added). In that case I get each word of "firstrow" printed as a header:

```python
>>> print(tabulate([], headers="firstrow"))
f    i    r    s    t    r    o    w
---  ---  ---  ---  ---  ---  ---  ---
>>>
```
