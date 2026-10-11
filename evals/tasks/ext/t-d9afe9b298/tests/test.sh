#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_sendmail_client.py::test_security_ssl \
  tests/test_sendmail_client.py::test_ssl_error \
  tests/test_sendmail_client.py::test_smtp \
  tests/test_sendmail_client.py::test_dry_run \
  tests/test_sendmail_client.py::test_no_dry_run \
  tests/test_sendmail_client.py::test_bad_config_key \
  tests/test_sendmail_client.py::test_security_error \
  tests/test_sendmail_client.py::test_security_open \
  tests/test_sendmail_client.py::test_security_open_legacy \
  tests/test_sendmail_client.py::test_security_starttls \
  tests/test_sendmail_client.py::test_security_xoauth \
  tests/test_sendmail_client.py::test_security_xoauth_bad_username \
  tests/test_sendmail_client.py::test_security_plain \
  tests/test_sendmail_client.py::test_missing_username \
  tests/test_sendmail_client.py::test_smtp_login_error \
  tests/test_sendmail_client.py::test_smtp_sendmail_error \
  tests/test_sendmail_client.py::test_socket_error; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
