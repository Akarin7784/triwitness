Rules 'contains' condition is case sensitive
### Checks

- [X] I have checked that this issue has not already been reported.
- [X] I have confirmed this bug exists on the latest version of actualpy.

### Reproducible example

```python
from actual import Actual

with Actual(base_url="http://localhost:5006", password="mypass", file="My budget") as actual:
    actual.run_rules()
    actual.commit()
```


### Log output

_No response_

### Issue description

Hello,

It seems that when running the actual.run_rules() function, some rules that use the 'contains' comparator are not applied via the API because the condition evaluation is case sensitive (compared to a case insensitive comparison done by Actual in the GUI).

My guess is there is an issue inside the rules.py file, maybe the following part: (as `in` is not case insensitive)

```python
 elif op == ConditionType.CONTAINS:
        return self_value in true_value
```

### Expected behavior

```
Rule If all of these conditions match 'notes' contains 'LIDL' then set 'description' to '906286fc-88fb-4ec4-94c6-5e12a71126b5' matches for transferred_id=None category_id='541836f1-e756-4473-a5d0-6c1d3f06c7fa' sort_order=1720699638709.0 reconciled=1 amount=-7112 financial_id=None tombstone=0 acct='bfc9afd8-8787-4107-81cd-1a4cbc91d07c' payee_id='906286fc-88fb-4ec4-94c6-5e12a71126b5' type=None cleared=1 is_parent=0 location=None pending=0 schedule_id=None id='d2c01c7d-d8ae-4d4c-bc13-265cf10ac7d2' is_child=0 error=None parent_id=None notes='LIDL xxxxxxxxxx' imported_description='LIDL xxxxxxxxxxxxx' date=20240130 starting_balance_flag=0
```

The rule above only matches if i set the keyword to `LIDL` (capital letters). It should match in lowercase as well (it does this in Actual)

### Installed versions

- actualpy version: v0.2.0
- Actual Server version: v24.7.0
