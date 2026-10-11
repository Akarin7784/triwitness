AssertionError is raised when using a CASE statement in a CASE statement
Hi David!

Thank you for `sqlvalidator`! :)
The following query seems correct:
```sql
SELECT
  CASE
    WHEN CASE
    WHEN code = 1 THEN 'VALID'
    WHEN code = 2 THEN 'INVALID'
END
  = 'VALID' THEN 'OK'
  ELSE
  'KO'
END
FROM table
```

However, `sqlvalidator` fails to validate/format it: an `AssertionError` is raised.
