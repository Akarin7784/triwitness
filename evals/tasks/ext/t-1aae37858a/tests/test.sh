#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  luaparser/tests/test_comments.py::CommentsTestCase::test_comment_in_table \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_array \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_mix_dict_array \
  luaparser/tests/test_comments.py::CommentsTestCase::test_comment_before_global_assign \
  luaparser/tests/test_comments.py::CommentsTestCase::test_comment_before_local_assign \
  luaparser/tests/test_comments.py::CommentsTestCase::test_comment_before_method \
  luaparser/tests/test_comments.py::CommentsTestCase::test_comment_in_table_2 \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_addition \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_bitwise_and \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_bitwise_exclusive_or \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_bitwise_left_shirt \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_bitwise_or \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_bitwise_right_shift \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_bitwise_unary_not \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_concatenation \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_dict \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_equal_than \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_exponentiation \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_float_division \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_floor_division \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_call_args \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_call_no_par_string \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_call_no_par_table \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_call_simple \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_def_anonymous \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_def_global \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_def_global_assign \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_def_indexed_name_global \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_def_local \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_invoke \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_function_nested_invoke \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_greater_or_eq_than \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_greater_than \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_index_function_call \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_length_op \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_less_or_eq_than \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_less_than \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_logic_and \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_logic_not \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_logic_or \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_mod \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_multiplication \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_nested_dict \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_not_equal_than \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_substraction \
  luaparser/tests/test_expressions.py::ExpressionsTestCase::test_unary_sub; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
