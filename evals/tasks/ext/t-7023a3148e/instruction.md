TokenAuth should raise AuthenticationError
In `TokenAuth`, catch `RequestException` the same way as it was done for [链接已移除] and redirect to an `AuthenticationError`
