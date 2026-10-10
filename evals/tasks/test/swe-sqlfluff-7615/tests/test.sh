#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_double_colon_cast]' \
  test/core/templaters/placeholder_test.py::test__templater_raw \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[no_changes]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_simple_substitution]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_accept_block_at_end]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_tuple_substitution]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_quoted]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_nospaces]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[colon_nospaces_double_colon_ignored]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[question_mark]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[numeric_colon]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[pyformat]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[dollar]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[numeric_dollar]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[numeric_dollar_with_braces]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[numeric_dollar_with_braces_and_string]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[dollar_surround]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[percent]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[ampersand]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[flyway_var0]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[flyway_var1]' \
  'test/core/templaters/placeholder_test.py::test__templater_param_style[params_not_specified]' \
  test/core/templaters/placeholder_test.py::test__templater_custom_regex \
  test/core/templaters/placeholder_test.py::test__templater_setup \
  test/core/templaters/placeholder_test.py::test__templater_styles; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
