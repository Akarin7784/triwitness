Does not work with alternative pronunciation "zwo"
```py
>>> from zahlwort2num import convert
>>> convert("zwo")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 137, in convert
    return c.convert()
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 123, in convert
    return self.ordBn(number)
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 108, in ordBn
    return self.ordWithBN(number, 0)
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 88, in ordWithBN
    return self.convOrd(number)
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 81, in convOrd
    return self.convt2(number)
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 129, in <lambda>
    self.convt2 = lambda number: self.mult(number, 'tausend', 1000, self.convh2)
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 60, in mult
    return fun(spliter[0])
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 130, in <lambda>
    self.convh2 = lambda number: self.mult(number, 'hundert', 100, self.convu2)
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 60, in mult
    return fun(spliter[0])
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 131, in <lambda>
    self.convu2 = lambda number: self.mult(number, 'und', 1, lambda word: self.CONST_NUMS[word])
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 60, in mult
    return fun(spliter[0])
  File "C:\ProgramData\miniforge3\lib\site-packages\zahlwort2num\__init__.py", line 131, in <lambda>
    self.convu2 = lambda number: self.mult(number, 'und', 1, lambda word: self.CONST_NUMS[word])
KeyError: 'zwo'
```
