#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/dead_test.py::test_unused_positional_only_argument \
  'tests/dead_test.py::test_dead_disable_regex_matching[#dead:disable]' \
  tests/dead_test.py::test_deleted_file_dont_raise_error \
  tests/dead_test.py::test_setup_py_entrypoints_mark_as_used \
  tests/dead_test.py::test_setup_cfg_entry_points_marked_as_used \
  tests/dead_test.py::test_setup_cfg_without_entry_points \
  tests/dead_test.py::test_setup_cfg_without_attribute_entry_point \
  tests/dead_test.py::test_never_referenced \
  tests/dead_test.py::test_assignment_not_counted_as_reference \
  tests/dead_test.py::test_only_referenced_in_tests \
  tests/dead_test.py::test_unused_dead_disable_comment \
  tests/dead_test.py::test_partially_disabled \
  tests/dead_test.py::test_unused_argument \
  tests/dead_test.py::test_unused_argument_in_scope \
  tests/dead_test.py::test_using_an_argument \
  tests/dead_test.py::test_ignore_unused_arguments_stubs \
  tests/dead_test.py::test_ignored_arguments; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
