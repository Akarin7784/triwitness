#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/client_test.py::ClientTest::test_access_private_spreadsheet \
  tests/client_test.py::ClientTest::test_access_non_existing_spreadsheet \
  tests/client_test.py::ClientTest::test_client_export_spreadsheet \
  tests/client_test.py::ClientTest::test_copy \
  tests/client_test.py::ClientTest::test_create \
  tests/client_test.py::ClientTest::test_import_csv \
  tests/client_test.py::ClientTest::test_list_spreadsheet_files \
  tests/client_test.py::ClientTest::test_no_found_exeption \
  tests/client_test.py::ClientTest::test_open_all_has_metadata \
  tests/client_test.py::ClientTest::test_open_by_key_has_metadata \
  tests/client_test.py::ClientTest::test_open_by_name_has_metadata \
  tests/client_test.py::ClientTest::test_openall; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
