CLI subcommands to add files and directories
Add subcommands to allow this:

```bash
mkdir crate
cd crate
rocrate init  # generates minimal metadata file and nothing else
cp /some/other/path/file1 .
cp -rf /some/path/dir1 .
rocrate add file file1
rocrate add dataset dir1
```
