#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/test_model.py::test_entity_as_mapping \
  test/test_model.py::test_dereferencing \
  'test/test_model.py::test_dereferencing_equivalent_id[.foo]' \
  'test/test_model.py::test_dereferencing_equivalent_id[foo.]' \
  'test/test_model.py::test_dereferencing_equivalent_id[.foo/]' \
  'test/test_model.py::test_dereferencing_equivalent_id[foo./]' \
  test/test_model.py::test_data_entities \
  test/test_model.py::test_data_entities_perf \
  test/test_model.py::test_remote_data_entities \
  test/test_model.py::test_bad_data_entities \
  test/test_model.py::test_contextual_entities \
  test/test_model.py::test_contextual_entities_hash \
  test/test_model.py::test_properties \
  test/test_model.py::test_uuid \
  test/test_model.py::test_update \
  test/test_model.py::test_delete \
  test/test_model.py::test_delete_refs \
  test/test_model.py::test_delete_by_id \
  test/test_model.py::test_self_delete \
  test/test_model.py::test_wf_types \
  'test/test_model.py::test_append_to[False]' \
  'test/test_model.py::test_append_to[True]' \
  test/test_model.py::test_get_by_type \
  test/test_model.py::test_context \
  test/test_model.py::test_add_no_duplicates \
  test/test_model.py::test_immutable_id \
  test/test_model.py::test_entity_in_properties; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
