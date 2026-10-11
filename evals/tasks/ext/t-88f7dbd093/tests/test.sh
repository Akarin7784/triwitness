#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_management_api.py::TestManagementApi::test_get_list_with_domains \
  tests/test_management_api.py::TestManagementApiSynced::test_get_list_with_domains \
  tests/test_management_api.py::TestManagementApi::test_get_list \
  tests/test_management_api.py::TestManagementApi::test_get_policy_api \
  tests/test_management_api.py::TestManagementApi::test_get_policy_matching_function \
  tests/test_management_api.py::TestManagementApi::test_get_policy_multiple_matching_functions \
  tests/test_management_api.py::TestManagementApi::test_modify_policy_api \
  tests/test_management_api.py::TestManagementApi::test_update_filtered_policies \
  tests/test_management_api.py::TestManagementApiSynced::test_get_list \
  tests/test_management_api.py::TestManagementApiSynced::test_get_policy_api \
  tests/test_management_api.py::TestManagementApiSynced::test_get_policy_matching_function \
  tests/test_management_api.py::TestManagementApiSynced::test_get_policy_multiple_matching_functions \
  tests/test_management_api.py::TestManagementApiSynced::test_modify_policy_api \
  tests/test_management_api.py::TestManagementApiSynced::test_update_filtered_policies \
  tests/test_management_api.py::TestManagementApiAsync::test_get_list \
  tests/test_management_api.py::TestManagementApiAsync::test_get_policy_api \
  tests/test_management_api.py::TestManagementApiAsync::test_get_policy_matching_function \
  tests/test_management_api.py::TestManagementApiAsync::test_get_policy_multiple_matching_functions \
  tests/test_management_api.py::TestManagementApiAsync::test_modify_policy_api \
  tests/test_management_api.py::TestManagementApiAsync::test_update_filtered_policies; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
