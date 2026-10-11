#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/astpretty_test.py::test_pformat_integer_indent \
  'tests/astpretty_test.py::test_is_leaf_true[x]' \
  'tests/astpretty_test.py::test_is_leaf_true["y"]' \
  'tests/astpretty_test.py::test_is_leaf_true[5]' \
  'tests/astpretty_test.py::test_is_leaf_true[[]]' \
  tests/astpretty_test.py::test_is_leaf_has_attr_with_list_of_primitives \
  'tests/astpretty_test.py::test_is_leaf_false[a.b]' \
  'tests/astpretty_test.py::test_is_leaf_false[[4]]' \
  'tests/astpretty_test.py::test_is_leaf_false[x()]' \
  tests/astpretty_test.py::test_pformat_py35_regression \
  tests/astpretty_test.py::test_pformat_node \
  tests/astpretty_test.py::test_pformat_nested_with_offsets \
  tests/astpretty_test.py::test_pformat_nested_attr_empty_list \
  tests/astpretty_test.py::test_pformat_mixed_sub_nodes_and_primitives \
  tests/astpretty_test.py::test_pformat_nested_multiple_elements \
  tests/astpretty_test.py::test_pformat_custom_indent \
  tests/astpretty_test.py::test_pformat_leaf_node_with_list \
  tests/astpretty_test.py::test_pprint \
  tests/astpretty_test.py::test_main_with_offsets \
  tests/astpretty_test.py::test_main_hide_offsets \
  tests/astpretty_test.py::test_pformat_py38_type_comments; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
