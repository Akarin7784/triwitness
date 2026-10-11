#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_altcha.py::TestALTCHA::test_verify_solution_expired \
  tests/test_altcha.py::TestALTCHA::test_verify_solution_malformed_expiry \
  tests/test_altcha.py::TestALTCHA::test_verify_solution_not_expired \
  tests/test_altcha.py::TestALTCHA::test_create_challenge \
  tests/test_altcha.py::TestALTCHA::test_expired_payload \
  tests/test_altcha.py::TestALTCHA::test_hash_hex \
  tests/test_altcha.py::TestALTCHA::test_hmac_hex \
  tests/test_altcha.py::TestALTCHA::test_invalid_signature \
  tests/test_altcha.py::TestALTCHA::test_solve_challenge \
  tests/test_altcha.py::TestALTCHA::test_valid_signature \
  tests/test_altcha.py::TestALTCHA::test_verify_solution_failure \
  tests/test_altcha.py::TestALTCHA::test_verify_solution_success; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
