Test names are not correctly globbed
Test names only respect a wildcard that is placed at the end of the string. Ex. "mbed-os-*".

However, it does not respect the wildcard anywhere else. Ex. "*-timer"

The build tools accept these wildcards, so greentea should as well. This is the line responsible: [链接已移除]

Should be switched to `fnmatch`.

(This is mostly a note to myself to fix it)
