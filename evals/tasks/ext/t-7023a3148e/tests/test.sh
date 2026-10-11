#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_request_error \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_json_token_authenticate \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_text_token_authenticate \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_validate_credentials_empty \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_validate_credentials_format_url_missing \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_validate_credentials_format_url_ok \
  tests/units/test_auth_plugins.py::TestAuthPluginTokenAuth::test_plugins_auth_tokenauth_validate_credentials_ok; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
