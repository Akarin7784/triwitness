Tweak SafetyNet check
SafetyNet-based attestation is on its way out for Android Keystore attestation via Play Integrity (if I'm understanding https://developer.android.com/privacy-and-security/safetynet/deprecation-timeline and https://android-developers.googleblog.com/2024/09/attestation-format-change-for-android-fido2-api.html correctly.) In this transition state it's possible for a device returning `"android-safetynet"` attestation to return responses with `"basicIntegrity": True` but `"ctsProfileMatch": False`.

Documentation on SafetyNet attestation verification is insufficient in the spec as the link it points to goes to that SafetyNet deprecation timeline. One proposed solution to make py_webauthn more flexible for use with passkeys is to change the requirement that `ctsProfileMatch` be true...

[链接已移除]

...to only require that `basicIntegrity` to be true. Adding a flag for this is probably a good idea, similar to what happened over here:

[链接已移除]
