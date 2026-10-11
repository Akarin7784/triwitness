CSV with BOM
It looks like Excel will sometimes save a file with Byte Order Mark (BOM).  When the mailmerge database contains a BOM, it can't seem to find the first header key.

`mailmerge_template.txt`:
```
TO: {{email}}
FROM: My Self <myself@mydomain.com>

Hello {{name}}
```

`mailmerge_database.csv`:
```
name,email
My Name,to@test.com
```

```console
$ file mailmerge_database.csv 
mailmerge_database.csv: UTF-8 Unicode (with BOM) text, with CRLF line terminators
```


[mailmerge_database_with_BOM.csv.txt](https://github.com/awdeorio/mailmerge/files/4621656/mailmerge_database_with_BOM.csv.txt)
