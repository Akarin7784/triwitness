#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'test/unit/module/jsonschema/test_utils.py::test_find_additional_properties[instance3-schema3-functions3-expected3]' \
  'test/unit/module/jsonschema/test_utils.py::test_find_additional_properties[instance5-schema5-functions5-expected5]' \
  test/unit/module/jsonschema/test_utils.py::TestUtils::test_equal \
  test/unit/module/jsonschema/test_utils.py::TestUtils::test_uniq \
  test/unit/module/jsonschema/test_utils.py::TestUtils::test_uniq_keys \
  'test/unit/module/jsonschema/test_utils.py::test_find_additional_properties[instance0-schema0-functions0-expected0]' \
  'test/unit/module/jsonschema/test_utils.py::test_find_additional_properties[instance1-schema1-functions1-expected1]' \
  'test/unit/module/jsonschema/test_utils.py::test_find_additional_properties[instance2-schema2-functions2-expected2]' \
  'test/unit/module/jsonschema/test_utils.py::test_find_additional_properties[instance4-schema4-functions4-expected4]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
