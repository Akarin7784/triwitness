BUG: Error when serializing metadata that is not a string
```
     37         for key, value in tokenlist.metadata.items():
     38             if value:
---> 39                 line = "# " + key + " = " + value
     40             else:
     41                 line = "# " + key

TypeError: can only concatenate str (not "int") to str
```
I have written a metadata_parser that converts values to `int` which is used in my downstream tasks. However, the serializer then breaks. A simple fix can be achieved by using f-strings (which we should be using anyway, now that there is a python 3.6 requirement)
