Fix relative file path
Thanks for this great utility. We've been using it for several months.

I noticed today that the reported violations do not show up in the diff view on a merge request (it's an Ultimate feature). The reason seems to be that the relative file path starts with `./` whereas GitLab seems to expect it not to start with that (see [docs](https://docs.gitlab.com/ee/ci/testing/code_quality.html#implementing-a-custom-tool)).

I did a test by removing those as follows in our pipeline:

```shell
flake8 --format gl-codeclimate | python -c "import sys; import json; lines = [line.replace('./', '') for line in sys.stdin]; print(json.dumps(json.loads('\n'.join(lines)), indent='\t'));" > gl-code-quality-report.json
```

And GitLab successfully showed it in the diff after.

Happy to contribute a PR but might need a little pointer in how to achieve this. It's not immediately clear to me what type `v` and `v.filename` are.
