#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/ast/test_function_simplifier.py::test_tuple_select_copy_made \
  tests/ast/test_function_simplifier.py::test_list_select_copy_made \
  tests/ast/test_function_simplifier.py::test_dict_is_different_attrib \
  tests/ast/test_function_simplifier.py::test_dict_is_different \
  tests/ast/test_function_simplifier.py::test_lambda_copy_simple \
  tests/ast/test_function_simplifier.py::test_lambda_copy_no_arg \
  tests/ast/test_function_simplifier.py::test_lambda_copy_nested \
  tests/ast/test_function_simplifier.py::test_lambda_copy_nested_same_arg_name \
  tests/ast/test_function_simplifier.py::test_lambda_copy_nested_captured \
  tests/ast/test_function_simplifier.py::test_function_replacement \
  tests/ast/test_function_simplifier.py::test_function_convolution_2deep \
  tests/ast/test_function_simplifier.py::test_function_convolution_2deep_same_names \
  tests/ast/test_function_simplifier.py::test_function_convolution_3deep \
  tests/ast/test_function_simplifier.py::test_select_simple \
  tests/ast/test_function_simplifier.py::test_select_select_convolution \
  tests/ast/test_function_simplifier.py::test_select_select_convolution_with_first \
  tests/ast/test_function_simplifier.py::test_select_identity \
  tests/ast/test_function_simplifier.py::test_where_simple \
  tests/ast/test_function_simplifier.py::test_where_always_true \
  tests/ast/test_function_simplifier.py::test_where_where \
  tests/ast/test_function_simplifier.py::test_where_select \
  tests/ast/test_function_simplifier.py::test_where_first \
  tests/ast/test_function_simplifier.py::test_selectmany_simple \
  tests/ast/test_function_simplifier.py::test_selectmany_where \
  tests/ast/test_function_simplifier.py::test_selectmany_select \
  tests/ast/test_function_simplifier.py::test_selectmany_selectmany \
  tests/ast/test_function_simplifier.py::test_tuple_select \
  tests/ast/test_function_simplifier.py::test_list_select \
  tests/ast/test_function_simplifier.py::test_tuple_select_past_end \
  tests/ast/test_function_simplifier.py::test_tuple_in_lambda \
  tests/ast/test_function_simplifier.py::test_tuple_in_lambda_2deep \
  tests/ast/test_function_simplifier.py::test_tuple_around_first \
  tests/ast/test_function_simplifier.py::test_tuple_in_SelectMany_Select \
  tests/ast/test_function_simplifier.py::test_tuple_with_lambda_args_duplication \
  tests/ast/test_function_simplifier.py::test_tuple_with_lambda_args_duplication_rename \
  tests/ast/test_function_simplifier.py::test_dict_select_reference \
  tests/ast/test_function_simplifier.py::test_dict_select_index \
  tests/ast/test_function_simplifier.py::test_dict_in_lambda \
  tests/ast/test_function_simplifier.py::test_dict_around_first; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
