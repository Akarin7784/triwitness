#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/auth_test.py::ClientFromTokenFileTest::test_json_loads \
  tests/auth_test.py::ClientFromTokenFileTest::test_token_updater_updates_token \
  tests/auth_test.py::ClientFromLoginFlow::test_no_token_file_http \
  tests/auth_test.py::ClientFromLoginFlow::test_no_token_file_http_redirected_to_https \
  tests/auth_test.py::ClientFromLoginFlow::test_no_token_file_https \
  tests/auth_test.py::ClientFromTokenFileTest::test_api_key_is_normalized \
  tests/auth_test.py::ClientFromTokenFileTest::test_no_such_file \
  tests/auth_test.py::ClientFromTokenFileTest::test_pickle_loads \
  tests/auth_test.py::ClientFromAccessFunctionsTest::test_success_no_write_func \
  tests/auth_test.py::ClientFromAccessFunctionsTest::test_success_with_write_func \
  tests/auth_test.py::ClientFromLoginFlow::test_normalize_api_key \
  tests/auth_test.py::ClientFromLoginFlow::test_unexpected_redirect_url \
  tests/auth_test.py::EasyClientTest::test_no_token_file_no_wd_func \
  tests/auth_test.py::EasyClientTest::test_no_token_file_with_wd_func \
  tests/auth_test.py::EasyClientTest::test_token_file; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
