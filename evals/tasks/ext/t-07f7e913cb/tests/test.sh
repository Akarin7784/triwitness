#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_validation.py::TestValidateDataset::test_double_correlation \
  tests/test_validation.py::TestTests::test_consistent_datatypes \
  tests/test_validation.py::TestTests::test_correlation \
  tests/test_validation.py::TestTests::test_datatype \
  tests/test_validation.py::TestTests::test_enumeration \
  tests/test_validation.py::TestTests::test_enumeration_suggested_values \
  tests/test_validation.py::TestTests::test_outliers \
  tests/test_validation.py::TestTests::test_range \
  tests/test_validation.py::TestTests::test_regex \
  tests/test_validation.py::TestTests::test_required \
  tests/test_validation.py::TestTests::test_spelling_case_insensitive \
  tests/test_validation.py::TestTests::test_spelling_case_sensitive \
  tests/test_validation.py::TestTests::test_unique_row \
  tests/test_validation.py::TestTests::test_unique_value \
  tests/test_validation.py::TestTests::test_whitespace \
  tests/test_validation.py::TestRule::test_datatype \
  tests/test_validation.py::TestRule::test_range \
  tests/test_validation.py::TestRule::test_regex \
  tests/test_validation.py::TestRule::test_row_restrictions \
  tests/test_validation.py::TestRule::test_value_enumeration \
  tests/test_validation.py::TestRule::test_whitespace \
  tests/test_validation.py::TestValidateColumns::test_bad_value_url \
  tests/test_validation.py::TestValidateColumns::test_min_occurs \
  tests/test_validation.py::TestValidateColumns::test_required \
  tests/test_validation.py::TestValidateRow::test_date \
  tests/test_validation.py::TestValidateRow::test_email \
  tests/test_validation.py::TestValidateRow::test_minmax \
  tests/test_validation.py::TestValidateRow::test_number \
  tests/test_validation.py::TestValidateRow::test_url \
  tests/test_validation.py::TestValidateDataset::test_consistent_datatype \
  tests/test_validation.py::TestValidateDataset::test_correlation \
  tests/test_validation.py::TestValidateDataset::test_different_indicator_datatypes \
  tests/test_validation.py::TestValidateDataset::test_outliers \
  tests/test_validation.py::TestValidateDataset::test_spellings \
  tests/test_validation.py::TestValidateDataset::test_spellings_multiple \
  tests/test_validation.py::TestValidateDataset::test_suggested_value_correlation_key \
  tests/test_validation.py::TestValidateDataset::test_unique_compound \
  tests/test_validation.py::TestValidateDataset::test_unique_single \
  tests/test_validation.py::TestLoad::test_load_bad \
  tests/test_validation.py::TestLoad::test_load_good \
  tests/test_validation.py::TestJSONReport::test_errors; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
