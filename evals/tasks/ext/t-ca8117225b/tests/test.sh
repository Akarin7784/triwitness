#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_pagination_with_float_numeric_key_in_exclusive_start_key \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_range_comparison \
  tests/test_dynamodb/test_dynamodb_query.py::test_key_condition_expressions \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_returns_detached_items \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[string]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[number]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[binary]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[boolean]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[null]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[string_set]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[number_set]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[binary_set]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[list]' \
  'tests/test_dynamodb/test_dynamodb_query.py::test_dynamotype_deepcopy_all_types[map]' \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_pagination \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_string_range \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_string_gsi_range \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_opposite_pk_order \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_string_gsi_range_and_empty_gsi_pk \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_string_gsi_range_and_empty_gsi_sk \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_numeric_range \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_lsi_pagination \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_lsi_pagination_with_numerical_local_range_key \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_with_range_key \
  tests/test_dynamodb/test_dynamodb_query.py::test_sorted_query_with_numerical_sort_key \
  tests/test_dynamodb/test_dynamodb_query.py::test_gsi_verify_negative_number_order \
  tests/test_dynamodb/test_dynamodb_query.py::TestFilterExpression::test_query_filter \
  tests/test_dynamodb/test_dynamodb_query.py::TestFilterExpression::test_query_filter_overlapping_expression_prefixes \
  tests/test_dynamodb/test_dynamodb_query.py::test_query_gsi_pagination_with_string_gsi_range_no_sk \
  tests/test_dynamodb/test_dynamodb_query.py::test_key_condition_expression_with_brackets; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
