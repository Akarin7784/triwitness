Space removed in the extract presto function after query formatting. 
```
sqlparse.format( "SELECT extract(HOUR from from_unixtime(hour_ts) AT TIME ZONE 'America/Los_Angeles') from table", reindent=True)
```
removes space between `from` and `from_unixtime(hour_ts` in the 0.3.1 version, works fine in 0.3.0

Related superset PR: [链接已移除]

Expected
```
SELECT extract(HOUR
               from from_unixtime(hour_ts) AT TIME ZONE 'America/Los_Angeles')
from table
```

Actual
```
SELECT extract(HOUR
               fromfrom_unixtime(hour_ts) AT TIME ZONE 'America/Los_Angeles')
from table
```
