#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  ccflow/tests/test_callable.py::TestCallableModel::test_signature \
  ccflow/tests/test_callable.py::TestContext::test_copy_on_validate \
  ccflow/tests/test_callable.py::TestContext::test_hashable \
  ccflow/tests/test_callable.py::TestContext::test_immutable \
  ccflow/tests/test_callable.py::TestContext::test_parse \
  ccflow/tests/test_callable.py::TestContext::test_registration \
  ccflow/tests/test_callable.py::TestCallableModel::test_callable \
  ccflow/tests/test_callable.py::TestCallableModel::test_copy_on_validate \
  ccflow/tests/test_callable.py::TestCallableModel::test_identity \
  ccflow/tests/test_callable.py::TestCallableModel::test_inheritance \
  ccflow/tests/test_callable.py::TestCallableModel::test_meta \
  ccflow/tests/test_callable.py::TestCallableModel::test_types \
  ccflow/tests/test_callable.py::TestWrapperModel::test_validate \
  ccflow/tests/test_callable.py::TestWrapperModel::test_wrapper \
  ccflow/tests/test_callable.py::TestCallableModelGenericType::test_wrapper \
  ccflow/tests/test_callable.py::TestCallableModelGenericType::test_wrapper_bad \
  ccflow/tests/test_callable.py::TestCallableModelGenericType::test_wrapper_reference \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_bad_annotation \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_bad_decorator \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_bad_deps_sig \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_basic \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_dep_context_validation \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_empty \
  ccflow/tests/test_callable.py::TestCallableModelDeps::test_multiple; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
