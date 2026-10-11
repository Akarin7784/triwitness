GetToken and asyncify: Algorithm not supported
### Checklist

- [X] I have looked into the [Readme](https://github.com/auth0/auth0-python#readme) and [Examples]([链接已移除]), and have not found a suitable solution or answer.
- [X] I have looked into the [API documentation](https://auth0-python.readthedocs.io/en/latest/) and have not found a suitable solution or answer.
- [X] I have searched the [issues](https://github.com/auth0/auth0-python/issues) and have not found a suitable solution or answer.
- [X] I have searched the [Auth0 Community](https://community.auth0.com) forums and have not found a suitable solution or answer.
- [X] I agree to the terms within the [Auth0 Code of Conduct]([链接已移除]).

### Description

When wrapping `GetToken` with `asyncify`, it passes the wrong arguments via the wrapper, and it fails with an exception 'Algorithm not supported'.

I believe the error resides [here]([链接已移除]). When I debug this piece of code, I see that it initializes the `AuthenticationBase` with `client_assertion_signing_alg = "https"`. That makes me believe that the order of the arguments passed onto `asyncify(GetToken)` -> `GetToken` ->`AuthenticationBase` is incorrect when using `asyncify`.


### Reproduction

This is what I basically do (I'm migrating from 3.x to 4.x):

```python
AsyncGetToken = asyncify(GetToken)

get_token = AsyncGetToken(domain, client_id)

# This fails with 'Algorithm not supported'.
response = await self.get_token.login_async(
    username=username,
    password=password,
    realm="Username-Password-Authentication",
    scope="openid profile email",
)
```

### Additional context

Stack trace:

```
Traceback (most recent call last):
  File "lib/python3.10/site-packages/jwt/api_jws.py", line 95, in get_algorithm_by_name
    return self._algorithms[alg_name]
KeyError: 'https'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "cli.py", line 178, in run
    sys.exit(asyncio.run(main(sys.argv)))
  File "/usr/local/Cellar/python@3.10/3.10.12/Frameworks/Python.framework/Versions/3.10/lib/python3.10/asyncio/runners.py", line 44, in run
    return loop.run_until_complete(main)
  File "/usr/local/Cellar/python@3.10/3.10.12/Frameworks/Python.framework/Versions/3.10/lib/python3.10/asyncio/base_events.py", line 649, in run_until_complete
    return future.result()
  File "cli.py", line 167, in main
    await command_devices(arguments)
  File "cli.py", line 55, in command_devices
    await account.update_devices()
  File "client.py", line 61, in update_devices
    device.id: device for device in await self.traccar_api.get_devices()
  File "api.py", line 49, in wrapper
    return await func(*args, **kwargs)
  File "api.py", line 217, in get_devices
    response = await self._get("devices")
  File "api.py", line 91, in wrapper
    return await func(*args, **kwargs)
  File "api.py", line 375, in _get
    await self.identity_api.login()
  File "api.py", line 154, in login
    response = await self.get_token.login_async(
  File "lib/python3.10/site-packages/auth0/asyncify.py", line 10, in closure
    return await m(*args, **kwargs)
  File "lib/python3.10/site-packages/auth0/authentication/get_token.py", line 156, in login
    return self.authenticated_post(
  File "lib/python3.10/site-packages/auth0/authentication/base.py", line 59, in authenticated_post
    url, data=self._add_client_authentication(data), headers=headers
  File "lib/python3.10/site-packages/auth0/authentication/base.py", line 45, in _add_client_authentication
    return add_client_authentication(
  File "lib/python3.10/site-packages/auth0/authentication/client_authentication.py", line 61, in add_client_authentication
    authenticated_payload["client_assertion"] = create_client_assertion_jwt(
  File "lib/python3.10/site-packages/auth0/authentication/client_authentication.py", line 23, in create_client_assertion_jwt
    return jwt.encode(
  File "lib/python3.10/site-packages/jwt/api_jwt.py", line 73, in encode
    return api_jws.encode(
  File "lib/python3.10/site-packages/jwt/api_jws.py", line 159, in encode
    alg_obj = self.get_algorithm_by_name(algorithm_)
  File "lib/python3.10/site-packages/jwt/api_jws.py", line 101, in get_algorithm_by_name
    raise NotImplementedError("Algorithm not supported") from e
NotImplementedError: Algorithm not supported
```

### auth0-python version

4.2.0

### Python version

3.10
