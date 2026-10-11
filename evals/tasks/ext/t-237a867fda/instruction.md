Do not cache configuration files

isort can run in long processes when used in an editor.  In that 
scenario users might edit their configuration files and literally
save a file again to see its outcome.  

This is not possible right now because we `lru_cache()` all the
relevant functions in `settings.py`.  

It is strange that we do this in the first place as we either collect
all known configs using the `Trie` implementation *or* we only
construct exactly one `Config` object based on the first file name, 
the working dir, or from `settings_path|file`...

We can probably remove the caches in `settings.py` completely. 
Except of course you explicitly wanted to optimize for long 
running processes.
