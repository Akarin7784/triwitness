#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/integration/test_line_range_diagnostics.py::test_filter_diagnostics_by_range_uses_fullrange \
  tests/integration/test_line_range_diagnostics.py::test_is_line_range_complete_empty_processing \
  tests/integration/test_line_range_diagnostics.py::test_is_line_range_complete_basic \
  tests/integration/test_line_range_diagnostics.py::test_is_line_range_complete_single_line \
  tests/integration/test_line_range_diagnostics.py::test_is_line_range_complete_sequential \
  tests/integration/test_line_range_diagnostics.py::test_is_line_range_complete_parallel \
  tests/integration/test_line_range_diagnostics.py::test_filter_diagnostics_by_range_basic \
  tests/integration/test_line_range_diagnostics.py::test_filter_diagnostics_by_range_overlapping \
  tests/integration/test_line_range_diagnostics.py::test_filter_diagnostics_by_range_empty \
  tests/integration/test_line_range_diagnostics.py::test_get_diagnostics_invalid_range \
  tests/integration/test_line_range_diagnostics.py::test_get_diagnostics_backward_compatibility \
  tests/integration/test_line_range_diagnostics.py::test_get_diagnostics_fatal_error_no_diagnostics \
  tests/integration/test_line_range_diagnostics.py::test_get_diagnostics_with_range_filters; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
