Fix BackOffHTTPClient not returning error 403
Currently, we cannot reliably test raising of `PermissionError` (see #1244 #1245).

This is because for the tests, a [`BackOffHTTPClient`] is used, which has problems returning 403 errors.

[链接已移除]

[链接已移除]

[`BackOffHTTPClient`]: [链接已移除]

If this is fixed, the test can be un-skipped.

With the normal HTTP client, it works fine (returns `PermissionError` immediately)
