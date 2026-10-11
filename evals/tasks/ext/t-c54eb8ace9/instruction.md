`should_warn` is incompatible with flake8 (next)
minimal reproduction (trigger any `B9*` warning with the default settings)

```console
$ rm -rf venv && virtualenv -qq venv && venv/bin/pip install -qq git+https://github.com/pycqa/flake8 git+https://github.com/pycqa/flake8-bugbear && venv/bin/flake8 --config /dev/null - <<< $'class C:\n    def __init__(wat): ...'
Traceback (most recent call last):
  File "venv/bin/flake8", line 8, in <module>
    sys.exit(main())
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/main/cli.py", line 22, in main
    app.run(argv)
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/main/application.py", line 336, in run
    self._run(argv)
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/main/application.py", line 325, in _run
    self.run_checks()
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/main/application.py", line 229, in run_checks
    self.file_checker_manager.run()
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/checker.py", line 252, in run
    self.run_serial()
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/checker.py", line 237, in run_serial
    checker.run_checks()
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/checker.py", line 531, in run_checks
    self.run_ast_checks()
  File "/tmp/y/venv/lib/python3.8/site-packages/flake8/checker.py", line 435, in run_ast_checks
    for (line_number, offset, text, _) in runner:
  File "/tmp/y/venv/lib/python3.8/site-packages/bugbear.py", line 61, in run
    if self.should_warn(e.message[:4]):
  File "/tmp/y/venv/lib/python3.8/site-packages/bugbear.py", line 158, in should_warn
    if code[:i] in self.options.select:
TypeError: argument of type 'NoneType' is not iterable
```

looking at the code, you should be able to delete `should_warn` entirely and rely on `extend-select` (and delete `load_file` while you're at it!)
