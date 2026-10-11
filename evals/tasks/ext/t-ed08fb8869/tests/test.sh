#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_verify_registration_response_android_safetynet.py::TestVerifyRegistrationResponseAndroidSafetyNet::test_verify_attestation_android_safetynet_basic_integrity_true_cts_profile_match_false \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_raises_exception_on_incorrect_public_key \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_raises_exception_on_uv_required_but_false \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_supports_already_parsed_credential \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_supports_dict_credential \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_supports_multiple_expected_origins \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_verify_authentication_response_with_EC2_public_key \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_verify_authentication_response_with_OKP_public_key \
  tests/test_verify_authentication_response.py::TestVerifyAuthenticationResponse::test_verify_authentication_response_with_RSA_public_key \
  tests/test_verify_registration_response_android_safetynet.py::TestVerifyRegistrationResponseAndroidSafetyNet::test_raise_attestation_android_safetynet_basic_integrity_false_cts_profile_match_false \
  tests/test_verify_registration_response_android_safetynet.py::TestVerifyRegistrationResponseAndroidSafetyNet::test_verify_attestation_android_safetynet; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
