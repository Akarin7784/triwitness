Pandas 2.0 with pyarrow backend: "TypeError: Cannot interpret 'timestamp[ms][pyarrow]' as a data type"
* Vega-Altair 5.0.1
* Pandas 2.0.3
* PyArrow 12.0.1

Essential outline of what I'm doing:

```
import pandas as pd

arrow_table = [make an Arrow table]
pandas_df = arrow_table.to_pandas(types_mapper=pd.ArrowDtype)
```

<details>
<summary>Stack trace from my actual app</summary>

```
  File "/usr/local/lib/python3.11/site-packages/altair/vegalite/v5/api.py", line 948, in save
    result = save(**kwds)
             ^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/altair/utils/save.py", line 131, in save
    spec = chart.to_dict()
           ^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/altair/vegalite/v5/api.py", line 838, in to_dict
    copy.data = _prepare_data(original_data, context)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/altair/vegalite/v5/api.py", line 100, in _prepare_data
    data = _pipe(data, data_transformers.get())
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/toolz/functoolz.py", line 628, in pipe
    data = func(data)
           ^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/toolz/functoolz.py", line 304, in __call__
    return self._partial(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/altair/vegalite/data.py", line 19, in default_data_transformer
    return curried.pipe(data, limit_rows(max_rows=max_rows), to_values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/toolz/functoolz.py", line 628, in pipe
    data = func(data)
           ^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/toolz/functoolz.py", line 304, in __call__
    return self._partial(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/altair/utils/data.py", line 160, in to_values
    data = sanitize_dataframe(data)
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/altair/utils/core.py", line 383, in sanitize_dataframe
    elif np.issubdtype(dtype, np.integer):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/numpy/core/numerictypes.py", line 417, in issubdtype
    arg1 = dtype(arg1).type
           ^^^^^^^^^^^
TypeError: Cannot interpret 'timestamp[ms][pyarrow]' as a data type
```

</details>
