#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_reduce \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_nestedframe_construction \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_nestedseries_construction \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_html_repr \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_all_columns \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_nested_columns \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_is_known_hierarchical_column \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_is_known_column \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_get_nested_column \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_get_nested_columns \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_get_nested_columns_errors \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_set_or_replace_nested_col \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_set_new_nested_col \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_set_item_combine_nested \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_set_list_struct_col \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_get_dot_names \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_nesting_limit \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_add_nested_with_flat_df \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_add_nested_with_flat_df_and_mismatched_index \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_add_nested_with_series \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_add_nested_with_series_and_mismatched_index \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_add_nested_for_empty_df \
  'tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat[None-False]' \
  'tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat[None-True]' \
  'tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat[a-False]' \
  'tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat[a-True]' \
  'tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat[c-False]' \
  'tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat[c-True]' \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_recover_from_flat \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_flat_omitting_columns \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_from_lists \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_query \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_query_on_non_identifier_columns \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_dropna \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_dropna_layer_as_base_column \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_dropna_inplace_base \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_dropna_inplace_nested \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_dropna_errors \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_sort_values \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_sort_values_ascension \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_reduce_duplicated_cols \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_reduce_infer_nesting \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_reduce_arg_errors \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_scientific_notation \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_drop \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_eval \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_eval_funcs \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_mixed_eval_funcs \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_eval_assignment \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_access_non_existing_column \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_issue193 \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_issue235 \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_nest_lists \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_delitem_base_and_nested \
  tests/nested_pandas/nestedframe/test_nestedframe.py::test_auto_nest_on_dataframe_assignment; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
