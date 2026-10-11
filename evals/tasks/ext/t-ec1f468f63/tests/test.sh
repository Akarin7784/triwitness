#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_fabric_workspace.py::test_empty_logical_id_validation \
  tests/test_fabric_workspace.py::test_whitespace_only_logical_id_validation \
  tests/test_fabric_workspace.py::test_empty_logical_id_validation_during_publish \
  tests/test_fabric_workspace.py::test_multiple_empty_logical_ids_validation \
  tests/test_fabric_workspace.py::test_single_empty_logical_id_validation_message \
  tests/test_fabric_workspace.py::test_parameter_file_with_utf8_chars \
  tests/test_fabric_workspace.py::test_platform_metadata_with_utf8_chars \
  tests/test_fabric_workspace.py::test_environment_param_with_utf8_chars \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_in_json \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_in_python \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_eventstream_json \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_yaml_format \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_mixed_formats \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_whitespace_variations \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_non_default_values_preserved \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_edge_cases \
  tests/test_fabric_workspace.py::test_workspace_id_replacement_comprehensive_item_types \
  tests/test_fabric_workspace.py::test_environment_parameter_replacement_issue \
  tests/test_fabric_workspace.py::test_valid_logical_id_works_correctly; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
