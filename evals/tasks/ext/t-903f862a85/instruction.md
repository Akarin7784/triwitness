reduce(append_columns=True) has a wrong behavior for non-unique indexes
**Bug report**

This should be `pd.concat([self, resultd_df], axis=1)`:
[链接已移除]

See lsdb's implementation:
[链接已移除]

**Before submitting**
Please check the following:

- [ ] I have described the situation in which the bug arose, including what code was executed, information about my environment, and any applicable data others will need to reproduce the problem.
- [ ] I have included available evidence of the unexpected behavior (including error messages, screenshots, and/or plots) as well as a description of what I expected instead.
- [x] If I have a solution in mind, I have provided an explanation and/or pseudocode and/or task list.
