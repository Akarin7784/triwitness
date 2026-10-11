ens_name not correctly set in sfcf module
While going over the type hints in #251 I noticed that `ens_name` does not seem to get properly propagated in `_get_rep_names` and `_get_appended_rep_names`.

https://github.com/fjosw/pyerrors/blame/[提交号已移除]/pyerrors/input/sfcf.py#L657-L660

Can you have a look @jkuhl-uni ?
