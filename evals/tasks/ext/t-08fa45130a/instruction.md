pandas df with datetime.date cols returns false differences if ignore_case=True
When ignore_case=True, identical values with type datetime.date will be reported as unequal.
This happens because in core.py/columns_equal() the attempt to call str.upper() on the col for case insensitive-comparison will throw an exception. The try/except returns false for any caught exception.

```
import pandas as pd
import datacompy
import datetime

df1 = pd.DataFrame([{'date_field':datetime.date(2024,5,8)}])
df2=df1.copy()

print("incorrectly reports unequal")                            
results = datacompy.Compare(df1=df1,df2=df2,on_index=True, ignore_case=True)
print(results.report())

results = datacompy.Compare(df1=df1,df2=df2,on_index=True, ignore_case=False)
print("Works correctly")                            
print(results.report())
```
