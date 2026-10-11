#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/test_getting_columns.py::test_double_inner_join \
  test/test_getting_columns.py::test_cast_and_convert_functions \
  test/test_getting_columns.py::test_queries_with_null_conditions \
  test/test_getting_columns.py::test_queries_with_distinct \
  test/test_getting_columns.py::test_joins \
  test/test_getting_columns.py::test_joins_using \
  test/test_getting_columns.py::test_getting_columns \
  test/test_getting_columns.py::test_columns_with_order_by \
  test/test_getting_columns.py::test_update_and_replace \
  test/test_getting_columns.py::test_complex_queries_columns \
  test/test_getting_columns.py::test_columns_with_comments \
  test/test_getting_columns.py::test_columns_with_keyword_aliases \
  test/test_getting_columns.py::test_columns_and_sql_functions \
  test/test_getting_columns.py::test_columns_starting_with_keywords \
  test/test_getting_columns.py::test_columns_as_unquoted_keywords \
  test/test_getting_columns.py::test_columns_with_keywords_parts \
  test/test_getting_columns.py::test_columns_with_complex_aliases_same_as_columns \
  test/test_getting_columns.py::test_columns_aliases_as_unqoted_keywords \
  test/test_getting_columns.py::test_columns_with_aliases_same_as_columns \
  test/test_getting_columns.py::test_columns_with_distinct \
  test/test_getting_columns.py::test_getting_columns_dict_with_distinct \
  test/test_getting_columns.py::test_aliases_switching_column_names \
  test/test_getting_columns.py::test_having_columns \
  test/test_getting_columns.py::test_nested_queries; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
