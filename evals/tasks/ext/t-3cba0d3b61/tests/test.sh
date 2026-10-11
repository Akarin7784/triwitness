#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_post_auth \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_delete \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_file_post \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_get \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_patch \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_post \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_put \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_rate_limit \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_shared_session \
  auth0/test_async/test_asyncify.py::TestAsyncify::test_timeout; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
