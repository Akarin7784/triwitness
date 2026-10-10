[Engineering task] Implement Claims API to Bypass Cache When Claims are Present in MSAL with Managed Identity
### MSAL client type

Confidential

### Problem Statement

**Task type**
Development

**Description**
Currently, MSAL with Managed Identity does not expose any API claims API. With CAE (Continuous Access Evaluation) being enabled by default, we need to implement a mechanism to bypass the cache if claims are detected in the token request.

**Steps to Reproduce:**
- Enable CAE by default in MSAL with Managed Identity.
- Make a token request with claims present.

Observe that the cache is not bypassed, leading to potential stale token usage.

**Expected Behavior:**
When claims are present in the token request, the cache should be bypassed to ensure that the latest token is used, in line with CAE requirements.

### Proposed solution

- Expose the claims API in MSAL for MI
- Expose Claims to MI Assertion Provider for FIC
- By-pass cache when claims are present

note : msi v1 endpoint is unchanged so there is no need to pass any claims to the endpoint itself, this feature is done so MSAL will bypass the cache.
