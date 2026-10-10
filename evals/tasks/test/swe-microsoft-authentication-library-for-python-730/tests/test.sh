#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_mi.py::VmTestCase::test_happy_path \
  tests/test_mi.py::AppServiceTestCase::test_happy_path \
  tests/test_mi.py::MachineLearningTestCase::test_happy_path \
  tests/test_mi.py::ServiceFabricTestCase::test_happy_path \
  tests/test_mi.py::ServiceFabricTestCase::test_unified_api_service_should_ignore_unnecessary_client_id \
  tests/test_mi.py::ArcTestCase::test_happy_path \
  tests/test_mi.py::ManagedIdentityTestCase::test_helper_class_should_be_interchangable_with_dict_which_could_be_loaded_from_file_or_env_var \
  tests/test_mi.py::VmTestCase::test_vm_error_should_be_returned_as_is \
  tests/test_mi.py::AppServiceTestCase::test_app_service_error_should_be_normalized \
  tests/test_mi.py::MachineLearningTestCase::test_machine_learning_error_should_be_normalized \
  tests/test_mi.py::ServiceFabricTestCase::test_sf_error_should_be_normalized \
  tests/test_mi.py::ArcTestCase::test_arc_error_should_be_normalized \
  tests/test_mi.py::GetManagedIdentitySourceTestCase::test_app_service \
  tests/test_mi.py::GetManagedIdentitySourceTestCase::test_arc \
  tests/test_mi.py::GetManagedIdentitySourceTestCase::test_cloud_shell \
  tests/test_mi.py::GetManagedIdentitySourceTestCase::test_default_to_vm \
  tests/test_mi.py::GetManagedIdentitySourceTestCase::test_machine_learning \
  tests/test_mi.py::GetManagedIdentitySourceTestCase::test_service_fabric; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
