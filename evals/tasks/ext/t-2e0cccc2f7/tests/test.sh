#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/utils/test_utils.py::test_sanitize_dataframe_arrow_columns \
  'tests/utils/test_core.py::test_infer_dtype[value0-integer]' \
  'tests/utils/test_core.py::test_infer_dtype[value1-floating]' \
  'tests/utils/test_core.py::test_infer_dtype[value2-mixed-integer-float]' \
  'tests/utils/test_core.py::test_infer_dtype[value3-string]' \
  'tests/utils/test_core.py::test_infer_dtype[value4-mixed]' \
  tests/utils/test_core.py::test_parse_shorthand \
  tests/utils/test_core.py::test_parse_shorthand_with_data \
  tests/utils/test_core.py::test_parse_shorthand_for_arrow_timestamp \
  tests/utils/test_core.py::test_parse_shorthand_all_aggregates \
  tests/utils/test_core.py::test_parse_shorthand_all_timeunits \
  tests/utils/test_core.py::test_parse_shorthand_window_count \
  tests/utils/test_core.py::test_parse_shorthand_all_window_ops \
  tests/utils/test_core.py::test_update_nested \
  tests/utils/test_core.py::test_infer_encoding_types \
  tests/utils/test_core.py::test_infer_encoding_types_with_condition \
  tests/utils/test_core.py::test_invalid_data_type \
  tests/utils/test_utils.py::test_infer_vegalite_type \
  tests/utils/test_utils.py::test_sanitize_dataframe \
  tests/utils/test_utils.py::test_sanitize_dataframe_colnames \
  tests/utils/test_utils.py::test_sanitize_dataframe_timedelta \
  tests/utils/test_utils.py::test_sanitize_dataframe_infs \
  tests/utils/test_utils.py::test_sanitize_nullable_integers \
  tests/utils/test_utils.py::test_sanitize_string_dtype \
  tests/utils/test_utils.py::test_sanitize_boolean_dtype; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
